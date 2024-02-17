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
        cat config.yaml; echo
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
        """), f"artifacts/system-info-{host_name_int}.txt")

    utils.write_file(utils.ssh_capture(
        user, host_ip_ext,
        """ set -x
            journalctl -x --no-tail --no-pager
        """), f"artifacts/journalctl-{host_name_int}.txt")

    utils.scp_get(user, host_ip_ext,
        "/var/log/syslog", f"artifacts/syslog-{host_name_int}.txt")

    #############################################
    # Juju
    #############################################
    juju_status_text = ""

    juju_models_text = utils.ssh_capture(user, host_ip_ext,
        'set -x; juju models')
    utils.write_file(juju_models_text,
        f"artifacts/juju-models-{host_name_int}.txt")

    juju_models_yaml = utils.ssh_capture(user, host_ip_ext,
        "juju models --format=yaml")
    utils.write_file(juju_models_yaml,
        f"artifacts/juju-models-{host_name_int}.yaml.txt")
    juju_models_dict = yaml.safe_load(juju_models_yaml)

    for model in [ x["name"] for x in juju_models_dict["models"] ]:

        juju_status_text = utils.ssh_capture(user, host_ip_ext,
            f'set -x; juju status -m {model}')
        utils.write_file(juju_status_text,
            f"artifacts/juju-status-{model.replace('/', '%')}-{host_name_int}.txt")

        juju_status_yaml = utils.ssh_capture(user, host_ip_ext,
            f"juju status -m {model} --format=yaml")
        utils.write_file(juju_status_yaml,
            f"artifacts/juju-status-{model.replace('/', '%')}-{host_name_int}.yaml.txt")
        juju_status_dict = yaml.safe_load(juju_status_yaml)

        # we do debug-log per model (and not per unit or app) because k8s-operators 
        # are too temperamental with exact unit/app names that can be specified
        utils.write_file(utils.ssh_capture(user, host_ip_ext,
            f"set -x; juju debug-log -m {model} --replay --no-tail"),
            f"artifacts/juju-debuglog-{model.replace('/', '%')}-{host_name_int}.txt")

        for app_key, app_val in juju_status_dict.get("applications", {}).items():
            for unit_key, unit_val in app_val.get("units", {}).items():
                utils.write_file(utils.ssh_capture(user, host_ip_ext,
                    f"set -x; juju show-unit -m {model} {unit_key}"),
                    f"artifacts/juju-showunit-{unit_key.replace('/', '%')}-{host_name_int}.txt")

        # maybe scp juju logs (/var/log/juju/*.log) from nodes?

    #############################################
    # Microk8s
    #############################################
    utils.write_file(utils.ssh_capture(user, host_ip_ext,
        """ set -x
            sudo microk8s.kubectl get nodes; echo
            sudo microk8s.kubectl get all -A; echo
            sudo microk8s.kubectl get pod -A -o yaml
        """), f"artifacts/microk8s-{host_name_int}.txt")

    #############################################
    # Microceph
    #############################################
    utils.write_file(utils.ssh_capture(user, host_ip_ext,
        """ set -x
            sudo timeout -k10 30 microceph status; echo
            sudo timeout -k10 30 ceph -s
        """), f"artifacts/microceph-{host_name_int}.txt")

    #############################################
    # Sunbeam
    #############################################
    utils.write_file(utils.ssh_capture(user, host_ip_ext,
        """ set -x
            sunbeam cluster list
        """), f"artifacts/sunbeam-cluster-{host_name_int}.txt")

    utils.scp_get(user, host_ip_ext,
        "~/snap/openstack/common/logs/*", "artifacts/")
    for fn in glob.glob("artifacts/sunbeam-202?????-??????.??????.log"):
        os.rename(fn, re.sub("sunbeam-", f"sunbeam-logs-{host_name_int}-", fn))

    #############################################
    # Openstack
    #############################################
    # get most openstack resources servers, networks, subnets, routers, images, flavors
