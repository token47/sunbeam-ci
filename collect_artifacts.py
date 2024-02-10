#!/usr/bin/python3

import os
import utils

ARTIFACTS_DIR = 'artifacts'

config = utils.read_config()

# Create temporary dir inside workspace
os.mkdir('artifacts')

user = config["user"]
for node in config["nodes"]:
    host_name_int = node["host-name-int"]
    host_name_ext = node["host-name-ext"]
    host_ip_int = node["host-ip-int"]
    host_ip_ext = node["host-ip-ext"]

    utils.debug(f"collecting artifacts from node {host_name_ext} / {host_ip_ext} " \
                f"/ {host_name_int} / {host_ip_int}")

    cmd = """set -e
        juju models
        juju status -m admin/controller
        juju status -m openstack
    """
    utils.write_file(utils.ssh_capture(user, host_ip_ext, cmd),
                     "artifacts/juju-status-{host_name_int}.txt")
