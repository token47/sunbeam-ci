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

# local info (from the build itself, not from the nodes)
cmd = """set -x
    cat config.yaml
"""
utils.write_file(utils.exec_cmd_capture(cmd), "artifacts/build-info.txt")

user = config["user"]
for node in config["nodes"]:
    host_name_int = node["host-name-int"]
    host_name_ext = node["host-name-ext"]
    host_ip_int = node["host-ip-int"]
    host_ip_ext = node["host-ip-ext"]

    utils.debug(f"collecting artifacts from node {host_name_int}")

    sshclient = SSHClient(user, host_ip_ext)

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
    utils.write_file(out, f"artifacts/system-info_{host_name_int}.txt")

    cmd = "set -x; SYSTEMD_COLORS=false journalctl -x --no-tail --no-pager"
    out, rc = sshclient.execute(
        cmd, verbose=False, get_pty=False, combine_stderr=True, filtered=False)
    utils.write_file(out, f"artifacts/journalctl_{host_name_int}.txt")

    sshclient.file_get("/var/log/syslog", f"artifacts/syslog_{host_name_int}.txt")

    #############################################
    # Juju
    #############################################
    # capture models, in text and yaml
    cmd = "set -x; juju models"
    out, rc = sshclient.execute(
        cmd, verbose=False, get_pty=False, combine_stderr=True, filtered=False)
    utils.write_file(out, f"artifacts/juju-models_{host_name_int}.txt")
    cmd = "juju models --format=yaml"
    out, rc = sshclient.execute(
        cmd, verbose=False, get_pty=False, combine_stderr=False, filtered=False)
    utils.write_file(out, f"artifacts/juju-models_{host_name_int}.yaml.txt")
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
        utils.write_file(out, f"artifacts/juju-debuglog_{model_r}_{host_name_int}.txt")

        # go for juju status of the model, in text and yaml
        cmd = f"set -x; juju status -m {model}"
        out, rc = sshclient.execute(
            cmd, verbose=False, get_pty=False, combine_stderr=True, filtered=False)
        utils.write_file(out, f"artifacts/juju-status_{model_r}_{host_name_int}.txt")
        cmd = f"juju status -m {model} --format=yaml"
        out, rc = sshclient.execute(
            cmd, verbose=False, get_pty=False, combine_stderr=False, filtered=False)
        utils.write_file(out, f"artifacts/juju-status_{model_r}_{host_name_int}.yaml.txt")
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
                    out, f"artifacts/juju-showunit_{unit_key_r}_{host_name_int}.txt")

        # maybe get juju logs (/var/log/juju/*.log) from nodes (rename or subdir)?

    #############################################
    # Microk8s
    #############################################
    cmd = """set -x
        sudo microk8s.kubectl get nodes; echo
        sudo microk8s.kubectl get all -A; echo
        sudo microk8s.kubectl get pod -A -o yaml
    """
    out, rc = sshclient.execute(
        cmd, verbose=False, get_pty=False, combine_stderr=True, filtered=False)
    utils.write_file(out, f"artifacts/microk8s_{host_name_int}.txt")

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
    utils.write_file(out, f"artifacts/microceph_{host_name_int}.txt")

    #############################################
    # Sunbeam
    #############################################
    cmd = """set -x
        sunbeam cluster list
        sunbeam --help
        sunbeam enable --help
    """
    out, rc = sshclient.execute(
        cmd, verbose=False, get_pty=False, combine_stderr=True, filtered=False)
    utils.write_file(out, f"artifacts/sunbeam-cluster_{host_name_int}.txt")

    try:
        sshclient.file_get_glob("snap/openstack/common/logs/", "*", "artifacts/")
        for fn in glob.glob("artifacts/sunbeam-202?????-??????.??????.log"):
            os.rename(fn, re.sub("sunbeam-", f"sunbeam-logs_{host_name_int}_", fn))
    except FileNotFoundError:
        pass

    try:
        sshclient.file_get_glob(".", "sunbeam-plugin-*", "artifacts/")
    except FileNotFoundError:
        pass

    #############################################
    # Openstack
    #############################################
    cmd = """set -xe
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
    utils.write_file(out, f"artifacts/openstack_{host_name_int}.txt")

    sshclient.close()
