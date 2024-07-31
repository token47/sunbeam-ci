#!/usr/bin/python3 -u

import glob
import os
import re
import utils
from sshclient import SSHClient


utils.debug("collecting common build artifacts")

try:
    os.mkdir('artifacts')
except FileExistsError:
    pass

utils.write_file(
    "# placeholder to avoid empty directory, you can ignore this file",
    "artifacts/dirkeep.txt")

try:
    config = utils.read_config()
except IOError:
    utils.die("Config file does not exist, aborting artifacts collection")

# local info (from the build itself, not from the remote nodes)
cmd = """set -x
    cat config.yaml
"""
utils.write_file(utils.exec_cmd_capture(cmd), "artifacts/build-info.txt")

user = config["user"]

substrate = config["substrate"]
if substrate in ("equinix", "maas"):
    target_node_list = []
    for node in config["nodes"]:
        target_node_list.append({
            "host-name": node["host-name-int"],
            "host-ip": node["host-ip-ext"]})
elif substrate == "maasdeployment":
    target_node_list = [{
        "host-name": "client",
        "host-ip": config["sunbeam_client"],
    }]
    # just open a separate ssh connection for this temporarily
    sshclient = SSHClient(user, config["sunbeam_client"])
    # add keys to machines to let ourselves in directly
    for key in utils.get_all_pub_keys():
        cmd = ("juju add-ssh-key "
            f"-m {config['deployment_name']}-controller:admin/openstack-machines '{key}'")
        out, rc = sshclient.execute(
            cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=False)

    # Adding machines could not be possible if ssh keys were not added correctly
    # or even if models do not exist at all. In this case, just ignore it so we
    # can at least collect logs from sunbeam-client machine.
    try:
        cmd = ("juju machines "
            f"-m {config['deployment_name']}-controller:admin/openstack-machines --format=yaml")
        out, rc = sshclient.execute(
            cmd, verbose=False, get_pty=False, combine_stderr=False, filtered=False)
        juju_machines_dict = utils.yaml_safe_load(out)
        for machine_id, machine_details in juju_machines_dict["machines"].items():
            target_node_list.append({
                "host-name": machine_details["hostname"],
                "host-ip": machine_details["dns-name"],
            })
    except TypeError:
        pass
    sshclient.close()
else:
    utils.die(f"Invalid substrate '{substrate}' in config, aborting")


# TODO: Add collection for validaiton log in client machine
#       and verify if tempest log gets copied to client on maas deployment


utils.debug(f"list of nodes for artifacts collection is {target_node_list}")

for node in target_node_list:
    host_name = node["host-name"]
    host_ip = node["host-ip"]

    utils.debug(f"collecting artifacts from node {host_name}")
    try:
        os.mkdir(f"artifacts/{host_name}")
    except FileExistsError:
        pass

    sshclient = SSHClient(user, host_ip)

    #############################################
    # System
    #############################################
    cmd = """set -x
        hostname -f; echo
        hostname -s; echo
        cat /etc/hosts; echo
        ip -o -4 addr list; echo
        ip addr list; echo
        free -h; echo
        lscpu; echo
        lsblk; echo
        df -h; echo
        snap list
    """
    out, rc = sshclient.execute(
        cmd, verbose=False, get_pty=False, combine_stderr=True, filtered=False)
    utils.write_file(out, f"artifacts/{host_name}/system-info.txt")

    cmd = "set -x; SYSTEMD_COLORS=false journalctl -x --no-tail --no-pager"
    out, rc = sshclient.execute(
        cmd, verbose=False, get_pty=False, combine_stderr=True, filtered=False)
    utils.write_file(out, f"artifacts/{host_name}/journalctl.txt")

    sshclient.file_get("/var/log/syslog", f"artifacts/{host_name}/syslog.txt")

    sshclient.file_get("/var/log/kern.log", f"artifacts/{host_name}/kern.log")

    #############################################
    # Juju
    #############################################
    # capture models, in text and yaml
    cmd = "set -x; juju models"
    out, rc = sshclient.execute(
        cmd, verbose=False, get_pty=False, combine_stderr=True, filtered=False)
    utils.write_file(out, f"artifacts/{host_name}/juju-models.txt")
    cmd = "juju models --format=yaml"
    out, rc = sshclient.execute(
        cmd, verbose=False, get_pty=False, combine_stderr=False, filtered=False)
    utils.write_file(out, f"artifacts/{host_name}/juju-models.yaml.txt")
    try:
        t = None
        t = utils.yaml_safe_load(out) # Returns None if string is empty, no error
    except Exception:
        utils.debug("Could not load yaml from juju models, ignoring juju logs for this host")
    juju_models_dict = t or {}

    for model in [ x["name"] for x in juju_models_dict.get("models", []) ]:
        model_r = model.replace('/', '%')

        # we do debug-log per model (and not per unit or app) because k8s-operators 
        # are too temperamental with exact unit/app names that can be specified
        cmd = f"set -x; juju debug-log -m {model} --replay --no-tail"
        out, rc = sshclient.execute(
            cmd, verbose=False, get_pty=False, combine_stderr=True, filtered=False)
        utils.write_file(out, f"artifacts/{host_name}/juju-debuglog_{model_r}.txt")

        # go for juju status of the model, in text and yaml
        cmd = f"set -x; juju status -m {model}"
        out, rc = sshclient.execute(
            cmd, verbose=False, get_pty=False, combine_stderr=True, filtered=False)
        utils.write_file(out, f"artifacts/{host_name}/juju-status_{model_r}.txt")
        cmd = f"juju status -m {model} --format=yaml"
        out, rc = sshclient.execute(
            cmd, verbose=False, get_pty=False, combine_stderr=False, filtered=False)
        utils.write_file(out, f"artifacts/{host_name}/juju-status_{model_r}.yaml.txt")
        try:
            juju_status_dict = utils.yaml_safe_load(out)
        except Exception:
            utils.debug(f"Could not load yaml from juju status -m {model}, ignoring this model")
            juju_status_dict = {}

        for app_key, app_val in juju_status_dict.get("applications", {}).items():
            for unit_key, unit_val in app_val.get("units", {}).items():
                unit_key_r = unit_key.replace('/', '%')
                cmd = f"set -x; juju show-unit -m {model} {unit_key}"
                out, rc = sshclient.execute(
                    cmd, verbose=False, get_pty=False, combine_stderr=True, filtered=False)
                utils.write_file(
                    out, f"artifacts/{host_name}/juju-showunit_{unit_key_r}.txt")

    #############################################
    # Microk8s
    #############################################
    cmd = """set -x
        sudo microk8s.kubectl get nodes; echo
        sudo microk8s.kubectl get all -A; echo
        sudo microk8s.kubectl get pod -A -o yaml
        cat ~/config || :
    """
    out, rc = sshclient.execute(
        cmd, verbose=False, get_pty=False, combine_stderr=True, filtered=False)
    utils.write_file(out, f"artifacts/{host_name}/microk8s-all.txt")

    # also get logs for all pods (and all containers in them)
    cmd = "sudo microk8s.kubectl get pods -n openstack --no-headers " \
        "-o custom-columns=\":metadata.name\""
    out, rc = sshclient.execute(
        cmd, verbose=False, get_pty=False, combine_stderr=False, filtered=False)
    pods = out.split()
    for pod in pods:
        cmd = f"sudo microk8s.kubectl logs --ignore-errors -n openstack --all-containers {pod}"
        out, rc = sshclient.execute(
            cmd, verbose=False, get_pty=False, combine_stderr=True, filtered=False)
        utils.write_file(out, f"artifacts/{host_name}/microk8s-pod-log_{pod}.txt")

    #############################################
    # Microceph
    #############################################
    # a few times this run got stuck so I added timeouts to all of them just in case
    cmd = """set -x
        sudo timeout -k10 30 microceph status; echo
        sudo timeout -k10 30 ceph -s; echo
        sudo timeout -k10 30 ceph health detail; echo
        sudo timeout -k10 30 ceph osd pool ls; echo
        sudo timeout -k10 30 ceph osd pool ls detail; echo
        sudo timeout -k10 30 ceph df; echo
        sudo timeout -k10 30 ceph osd df; echo
        sudo timeout -k10 30 ceph osd tree; echo
        sudo timeout -k10 30 ceph osd crush rule ls; echo
        sudo timeout -k10 30 ceph osd crush tree; echo
        sudo timeout -k10 30 ceph osd crush class ls; echo
        sudo timeout -k10 30 ceph osd blocked-by; echo
        sudo timeout -k10 30 ceph config dump; echo
        sudo timeout -k10 30 ceph pg ls; echo
    """
    out, rc = sshclient.execute(
        cmd, verbose=False, get_pty=False, combine_stderr=True, filtered=False)
    utils.write_file(out, f"artifacts/{host_name}/microceph.txt")

    #############################################
    # Sunbeam
    #############################################
    cmd = """set -x
        sunbeam cluster list
        sunbeam --help
        sunbeam enable --help
    """
    out, rc = sshclient.execute(
        cmd, verbose=False, get_pty=False, combine_stderr=True, filtered=True)
    utils.write_file(out, f"artifacts/{host_name}/sunbeam-cluster.txt")

    try:
        sshclient.file_get_glob("snap/openstack/common/logs/",
                                "*.log",
                                f"artifacts/{host_name}/")
    except FileNotFoundError:
        pass

    try:
        sshclient.file_get_glob("./", "plugin-*", f"artifacts/{host_name}/")
    except FileNotFoundError:
        pass

    #############################################
    # Openstack
    #############################################
    cmd = """set -xe
        cat ~/admin-openrc || :
        cat ~/demo-openrc || :
        source admin-openrc
        openstack server list --all-projects --long; echo
        openstack network list --long; echo
        openstack subnet list --long; echo
        openstack router list --long; echo
        openstack image list --long; echo
        openstack flavor list --all --long; echo
    """
    out, rc = sshclient.execute(
        cmd, verbose=False, get_pty=False, combine_stderr=True, filtered=False)
    utils.write_file(out, f"artifacts/{host_name}/openstack.txt")

    #############################################
    # Terraform deployments
    #############################################
    try:
        sshclient.file_get_glob("snap/openstack/common/etc/local/demo-setup/",
                                "terraform-*-202???????????.log",
                                f"artifacts/{host_name}/")
        for fn in glob.glob(f"artifacts/{host_name}/terraform-*-202???????????.log"):
            newfn = re.sub("terraform-", "terraform_demo-setup-", fn)
            utils.debug(f"renaming '{fn}' -> '{newfn}'")
            os.rename(fn, newfn)
    except FileNotFoundError:
        pass
    
    try:
        sshclient.file_get_glob("snap/openstack/common/etc/local/deploy-openstack-hypervisor/",
                                "terraform-*-202???????????.log",
                                f"artifacts/{host_name}/")
        for fn in glob.glob(f"artifacts/{host_name}/terraform-*-202???????????.log"):
            newfn = re.sub("terraform-", "terraform_deploy-openstack-hypervisor-", fn)
            utils.debug(f"renaming '{fn}' -> '{newfn}'")
            os.rename(fn, newfn)
    except FileNotFoundError:
        pass

    try:
        sshclient.file_get_glob("snap/openstack/common/etc/local/deploy-microceph/",
                                "terraform-*-202???????????.log",
                                f"artifacts/{host_name}/")
        for fn in glob.glob(f"artifacts/{host_name}/terraform-*-202???????????.log"):
            newfn = re.sub("terraform-", "terraform_deploy-microceph-", fn)
            utils.debug(f"renaming '{fn}' -> '{newfn}'")
            os.rename(fn, newfn)
    except FileNotFoundError:
        pass

    #############################################
    # OpenVSwitch / OVN / Neutron / libvirt
    #############################################
    try:
        sshclient.file_get("/var/snap/openstack-hypervisor/common/log/neutron.log",
                           f"artifacts/{host_name}/neutron.log")
    except FileNotFoundError:
        pass
    # These next files are only readable by root so I'm using 'sudo cat' instead of
    # trying to copy the files using a separate root ssh session
    cmd = "sudo cat /var/snap/openstack-hypervisor/common/log/openvswitch/ovs-vswitchd.log"
    out, rc = sshclient.execute(
        cmd, verbose=False, get_pty=False, combine_stderr=True, filtered=False)
    utils.write_file(out, f"artifacts/{host_name}/ovs-vswitchd.log")
    cmd = "sudo cat /var/snap/openstack-hypervisor/common/log/openvswitch/ovsdb-server.log"
    out, rc = sshclient.execute(
        cmd, verbose=False, get_pty=False, combine_stderr=True, filtered=False)
    utils.write_file(out, f"artifacts/{host_name}/ovsdb-server.log")
    cmd = "sudo cat /var/snap/openstack-hypervisor/common/log/ovn/ovn-controller.log"
    out, rc = sshclient.execute(
        cmd, verbose=False, get_pty=False, combine_stderr=True, filtered=False)
    utils.write_file(out, f"artifacts/{host_name}/ovn-controller.log")
    cmd = "sudo grep -H . /var/snap/openstack-hypervisor/common/log/libvirt/qemu/*.log"
    out, rc = sshclient.execute(
        cmd, verbose=False, get_pty=False, combine_stderr=True, filtered=False)
    utils.write_file(out, f"artifacts/{host_name}/libvirt-instances.txt")

    sshclient.close()
