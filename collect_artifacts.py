#!/usr/bin/python3

import os
import utils

config = utils.read_config()

# Create temporary dir inside workspace
os.mkdir('artifacts')

utils.debug("collecting common build artifacts")

#utils.write_file(
#    "<BUILD-INFO>",
#    "artifacts/build-info.txt"
#)

user = config["user"]
for node in config["nodes"]:
    host_name_int = node["host-name-int"]
    host_name_ext = node["host-name-ext"]
    host_ip_int = node["host-ip-int"]
    host_ip_ext = node["host-ip-ext"]

    utils.debug(f"collecting artifacts from node {host_name_ext} / {host_ip_ext} " \
                f"/ {host_name_int} / {host_ip_int}")

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
            juju debug-log --replay --no-tail
        """), f"artifacts/juju-{host_name_int}.txt")

    utils.write_file(utils.ssh_capture(
        user, host_ip_ext,
        """ set -x
            sudo microk8s.kubectl get all -A
            sudo microk8s.kubectl get nodes
        """), f"artifacts/microk8s-{host_name_int}.txt")

    utils.write_file(utils.ssh_capture(
        user, host_ip_ext,
        """ set -x
            sudo microceph status
            sudo ceph -s
        """), f"artifacts/microceph-{host_name_int}.txt")

    utils.write_file(utils.ssh_capture(
        user, host_ip_ext,
        """ set -x
            sunbeam cluster list
        """), f"artifacts/sunbeam-{host_name_int}.txt")

    utils.write_file(utils.ssh_capture(
        user, host_ip_ext,
        """ set -x
            sunbeam inspect
        """), f"artifacts/sunbeam-inspect-{host_name_int}.txt")

    utils.scp_get(user, host_ip_ext,
        "~/snap/openstack/common/logs/*",
        "artifacts/")
    # rename "s/^sunbeam-/inspection-{host_name_int}/" sunbeam-202.....-......\.......\.log 

    #most openstack resources servers, networks, subnets, routers, images, flavors
