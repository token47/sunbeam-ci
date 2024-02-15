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

# minimum info, even without a config
utils.write_file(utils.exec_cmd_capture(
    """ set -x
        cat config.yaml
    """), "artifacts/build-info.txt")

try:
    config = utils.read_config()
except IOError:
    utils.die("Config file does not exist, aborting artifacts collection")

user = config["user"]
for node in config["nodes"]:
    host_name_int = node["host-name-int"]
    host_name_ext = node["host-name-ext"]
    host_ip_int = node["host-ip-int"]
    host_ip_ext = node["host-ip-ext"]

    utils.debug(f"collecting artifacts from node {host_name_int}")

    #############################################
    # Software
    #############################################
    utils.write_file(utils.ssh_capture(
        user, host_ip_ext,
        """ set -x
            sudo snap list
        """), f"artifacts/software-{host_name_int}.txt")

    #############################################
    # Network
    #############################################
    utils.write_file(utils.ssh_capture(
        user, host_ip_ext,
        """ set -x
            hostname -f
            hostname -s
            ip addr list
            cat /etc/hosts
        """), f"artifacts/network-{host_name_int}.txt")

    #############################################
    # Juju
    #############################################
    juju_status_text = ""

    juju_status_text = utils.ssh_capture(user, host_ip_ext,
        'set -x; juju models; echo "--------"')

    # juju models in yaml format is for iterating over models
    juju_models_yaml = utils.ssh_capture(user, host_ip_ext,
        "juju models --format=yaml")
    juju_models_dict = yaml.safe_load(juju_models_yaml)

    for model in [ x["name"] for x in juju_models_dict["models"] ]:

        # store all juju status in single buffer to write later
        juju_status_text += utils.ssh_capture(user, host_ip_ext,
            f'set -x; juju status -m {model}; echo "--------"')

        # juju debug-status goes one per file right away
        utils.write_file(utils.ssh_capture(user, host_ip_ext,
            f"set -x; juju debug-log -m {model} --replay --no-tail"),
            f"artifacts/juju-debuglog-{model.replace('/', '!')}-{host_name_int}.txt")

        # juju status in yaml format is for iterating over applications
        juju_status_yaml = utils.ssh_capture(user, host_ip_ext,
            f"juju status -m {model} --format=yaml")
        juju_status_dict = yaml.safe_load(juju_status_yaml)

        # get show-unit for all units of all apps in all models
        for application_key, application_values in juju_status_dict.get("applications", {}):
            for unit_key, unit_values in application_values.get("units", {}):
                utils.write_file(utils.ssh_capture(user, host_ip_ext,
                    f"set -x; juju show-unit -m {model} {unit_key}"),
                    f"artifacts/juju-showunit-{unit_key.replace('/', '!')}-{host_name_int}.txt")
                # again debug-log, now separate per unit
                utils.write_file(utils.ssh_capture(user, host_ip_ext,
                    f"set -x; juju debug-log -m {model} --include {unit_key} --replay --no-tail"),
                    f"artifacts/juju-debuglog-{unit_key.replace('/', '!')}-{host_name_int}.txt")

    utils.write_file(juju_status_text, f"artifacts/juju-status-{host_name_int}.txt")


    #############################################
    # Microk8s
    #############################################
    utils.write_file(utils.ssh_capture(user, host_ip_ext,
        """ set -x
            sudo microk8s.kubectl get nodes
            echo "--------"
            sudo microk8s.kubectl get all -A
            echo "--------"
            sudo microk8s.kubectl get pod -A -o yaml
        """), f"artifacts/microk8s-{host_name_int}.txt")

    #############################################
    # Microceph
    #############################################
    utils.write_file(utils.ssh_capture(user, host_ip_ext,
        """ set -x
            sudo timeout -k10 30 microceph status
            sudo timeout -k10 30 ceph -s
        """), f"artifacts/microceph-{host_name_int}.txt")

    #############################################
    # Sunbeam
    #############################################
    utils.write_file(utils.ssh_capture(user, host_ip_ext,
        """ set -x
            sunbeam cluster list
        """), f"artifacts/cluster-{host_name_int}.txt")

    utils.scp_get(user, host_ip_ext,
        "/var/log/syslog", f"artifacts/syslog-{host_name_int}.txt")

    utils.scp_get(user, host_ip_ext,
        "~/snap/openstack/common/logs/*", "artifacts/")
    for fn in glob.glob("artifacts/sunbeam-202?????-??????.??????.log"):
        os.rename(fn, re.sub("sunbeam-", f"sunbeam-logs-{host_name_int}-", fn))

    #############################################
    # Openstack
    #############################################
    # get most openstack resources servers, networks, subnets, routers, images, flavors
