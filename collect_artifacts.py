#!/usr/bin/python3 -u

import glob
import os
import re
import utils
import yaml


utils.debug("collecting common build artifacts")

try:
    os.mkdir('artifacts')
except FileExistsError:
    pass

try:
    config = utils.read_config()
except IOError:
    utils.die("Config file does not exist, aborting artifacts collection")

# local info (from the build itself, not from the nodes)
utils.write_file(utils.exec_cmd_capture(
    """ set -x
        cat config.yaml
    """), "artifacts/build-info.txt")

user = config["user"]
for node in config["nodes"]:
    host_name_int = node["host-name-int"]
    host_name_ext = node["host-name-ext"]
    host_ip_int = node["host-ip-int"]
    host_ip_ext = node["host-ip-ext"]

    utils.debug(f"collecting artifacts from node {host_name_int}")

    #############################################
    # System
    #############################################
    utils.write_file(utils.ssh_capture(
        user, host_ip_ext,
        """ set -x
            hostname -f; echo
            hostname -s; echo
            cat /etc/hosts; echo
            ip addr list; echo
            free -h; echo
            lscpu; echo
            lsblk; echo
            df -h; echo
            snap list
        """), f"artifacts/system-info_{host_name_int}.txt")

    utils.write_file(utils.ssh_capture(
        user, host_ip_ext,
        "set -x; SYSTEMD_COLORS=false journalctl -x --no-tail --no-pager"),
        f"artifacts/journalctl_{host_name_int}.txt")

    utils.scp_get(user, host_ip_ext,
        "/var/log/syslog", f"artifacts/syslog_{host_name_int}.txt")

    #############################################
    # Juju
    #############################################
    juju_status_text = ""

    juju_models_text = utils.ssh_capture(user, host_ip_ext,
        'set -x; juju models')
    juju_models_yaml = utils.ssh_capture(user, host_ip_ext,
        "juju models --format=yaml")
    juju_models_dict = yaml.safe_load(juju_models_yaml)
    utils.write_file(juju_models_text,
        f"artifacts/juju-models_{host_name_int}.txt")
    utils.write_file(juju_models_yaml,
        f"artifacts/juju-models_{host_name_int}.yaml.txt")

    for model in [ x["name"] for x in juju_models_dict["models"] ]:

        juju_status_text = utils.ssh_capture(user, host_ip_ext,
            f'set -x; juju status -m {model}')
        juju_status_yaml = utils.ssh_capture(user, host_ip_ext,
            f"juju status -m {model} --format=yaml")
        juju_status_dict = yaml.safe_load(juju_status_yaml)
        utils.write_file(juju_status_text,
            f"artifacts/juju-status_{model.replace('/', '%')}_{host_name_int}.txt")
        utils.write_file(juju_status_yaml,
            f"artifacts/juju-status_{model.replace('/', '%')}_{host_name_int}.yaml.txt")

        # we do debug-log per model (and not per unit or app) because k8s-operators 
        # are too temperamental with exact unit/app names that can be specified
        utils.write_file(utils.ssh_capture(user, host_ip_ext,
            f"set -x; juju debug-log -m {model} --replay --no-tail"),
            f"artifacts/juju-debuglog_{model.replace('/', '%')}_{host_name_int}.txt")

        for app_key, app_val in juju_status_dict.get("applications", {}).items():
            for unit_key, unit_val in app_val.get("units", {}).items():
                utils.write_file(utils.ssh_capture(user, host_ip_ext,
                    f"set -x; juju show-unit -m {model} {unit_key}"),
                    f"artifacts/juju-showunit_{unit_key.replace('/', '%')}_{host_name_int}.txt")

        # maybe scp juju logs (/var/log/juju/*.log) from nodes + rename or subdir?

    #############################################
    # Microk8s
    #############################################
    utils.write_file(utils.ssh_capture(user, host_ip_ext,
        """ set -xe
            sudo microk8s.kubectl get nodes; echo
            sudo microk8s.kubectl get all -A; echo
            sudo microk8s.kubectl get pod -A -o yaml
        """), f"artifacts/microk8s_{host_name_int}.txt")

    #############################################
    # Microceph
    #############################################
    utils.write_file(utils.ssh_capture(user, host_ip_ext,
        """ set -x
            sudo timeout -k10 30 microceph status; echo
            sudo timeout -k10 30 ceph -s
        """), f"artifacts/microceph_{host_name_int}.txt")

    #############################################
    # Sunbeam
    #############################################
    utils.write_file(utils.ssh_capture(user, host_ip_ext,
        """ set -x
            sunbeam cluster list
        """), f"artifacts/sunbeam-cluster_{host_name_int}.txt")

    utils.scp_get(user, host_ip_ext,
        "~/snap/openstack/common/logs/*", "artifacts/")
    for fn in glob.glob("artifacts/sunbeam-202?????-??????.??????.log"):
        os.rename(fn, re.sub("sunbeam-", f"sunbeam-logs_{host_name_int}_", fn))

    #############################################
    # Openstack
    #############################################
    utils.write_file(utils.ssh_capture(user, host_ip_ext,
        """ set -xe
            source admin-openrc
            openstack server list --all-projects --long; echo
            openstack network list --long; echo
            openstack subnet list --long; echo
            openstack router list --long; echo
            openstack image list --long; echo
            openstack flavor list --all --long; echo
        """), f"artifacts/openstack_{host_name_int}.txt")
