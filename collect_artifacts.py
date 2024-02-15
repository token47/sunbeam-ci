#!/usr/bin/python3 -u

import glob
import os
import re
import utils

utils.debug("collecting common build artifacts")

os.mkdir('artifacts')

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

    utils.write_file(utils.ssh_capture(
        user, host_ip_ext,
        """ set -x
            sudo snap list
        """), f"artifacts/software-{host_name_int}.txt")

    utils.write_file(utils.ssh_capture(
        user, host_ip_ext,
        """ set -x
            hostname -f
            hostname -s
            ip addr list
            cat /etc/hosts
        """), f"artifacts/network-{host_name_int}.txt")

    utils.write_file(utils.ssh_capture(
        user, host_ip_ext,
        """ set -x
            juju models
            juju status -m admin/controller
            juju status -m openstack
        """), f"artifacts/juju-status-{host_name_int}.txt")

    utils.write_file(utils.ssh_capture(
        user, host_ip_ext,
        """ set -x
            juju debug-log -m admin/controller --replay --no-tail
            juju debug-log -m openstack --replay --no-tail
        """), f"artifacts/juju-debuglog-{host_name_int}.txt")

    utils.write_file(utils.ssh_capture(
        user, host_ip_ext,
        """ set -x
            sudo microk8s.kubectl get all -A
            sudo microk8s.kubectl get nodes
        """), f"artifacts/microk8s-{host_name_int}.txt")

    utils.write_file(utils.ssh_capture(
        user, host_ip_ext,
        """ set -x
            sudo timeout -k10 30 microceph status
            sudo timeout -k10 30 ceph -s
        """), f"artifacts/microceph-{host_name_int}.txt")

    utils.write_file(utils.ssh_capture(
        user, host_ip_ext,
        """ set -x
            sunbeam cluster list
        """), f"artifacts/cluster-{host_name_int}.txt")

    utils.scp_get(user, host_ip_ext,
        "/var/log/syslog", f"artifacts/syslog-{host_name_int}")

    utils.scp_get(user, host_ip_ext,
        "~/snap/openstack/common/logs/*", "artifacts/")
    for f in glob.glob("artifacts/sunbeam-202?????-??????.??????.log"):
        os.rename(f, re.sub("sunbeam-", f"sunbeam-logs-{host_name_int}-", f))

    # algo get most openstack resources servers, networks, subnets, routers, images, flavors
