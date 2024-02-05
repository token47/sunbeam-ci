#!/usr/bin/python3 -u

# pylint: disable=wildcard-import,unused-wildcard-import
# pylint: disable=invalid-name

"""
This script deploys sunbeam on a substrate that has already been prepared for it.
"""

import re
import yaml
from utils import *


def token_extract(text):
    """Extracts the token from the sunbeam node add command output"""
    match = re.search("Token for the Node [^ ]+: ([^ \\r\\n]+)", text)
    if match is None:
        debug("RE for host add token did not match")
        debug(text)
        die("aborting")
    return match.group(1)


with open("config.yaml", "r", encoding='ascii') as stream:
    config = yaml.safe_load(stream)

# order hosts to have control nodes first, then separete primary node from others
nodes = list(filter(lambda x: 'control' in x["roles"], config["nodes"]))
control_count = len(nodes)
nodes += list(filter(lambda x: 'control' not in x["roles"], config["nodes"]))
debug(f"detected control nodes / total nodes count is {control_count} / {len(nodes)}")
debug(f"complete list of nodes: {nodes}")
primary_node = nodes.pop(0)

### Primary node / bootstrap

user = config["user"]

p_host_int = primary_node["host-int"]
p_host_ext = primary_node["host-ext"]

debug(f"installing primary node {p_host_int} / {p_host_ext}")

ssh_clean(p_host_ext)
test_ssh(user, p_host_ext)

cmd = f"sudo snap install openstack --channel {config['channel']}"
rc = ssh(user, p_host_ext, cmd)
if rc > 0:
    die("installing openstack snap failed, aborting")

cmd = "sunbeam prepare-node-script | grep -v newgrp | bash -x"
rc = ssh(user, p_host_ext, cmd)
if rc > 0:
    die("running prepare-node-script failed, aborting")

put(user, p_host_ext, "~/preseed.yaml", yaml.dump(config["preseed"]))

cmd = "sunbeam cluster bootstrap -p ~/preseed.yaml"
for role in primary_node["roles"]:
    cmd += f" --role {role}"
rc = ssh(user, p_host_ext, cmd)
if rc > 0:
    die("bootstrapping sunbeam failed, aborting")

ssh(user, p_host_ext, "sunbeam cluster list")

### Other nodes

for node in nodes:
    s_host_int = node["host-int"]
    s_host_ext = node["host-ext"]

    debug(f"installing secondary node {s_host_int} / {s_host_ext}")

    ssh_clean(s_host_ext)
    test_ssh(user, s_host_ext)

    cmd = f"sudo snap install openstack --channel {config['channel']}\n"
    rc = ssh(user, s_host_ext, cmd)
    if rc > 0:
        die("installing openstack snap failed, aborting")

    cmd = "sunbeam prepare-node-script | grep -v newgrp | bash -x"
    rc = ssh(user, s_host_ext, cmd)
    if rc > 0:
        die("running prepare-node-script failed, aborting")

    put(user, s_host_ext, "~/preseed.yaml", yaml.dump(config["preseed"]))

    cmd = f"sunbeam cluster add --name {s_host_int}"
    token = token_extract(ssh_capture(user, p_host_ext, cmd))

    cmd = "sunbeam cluster join -p ~/preseed.yaml"
    for role in primary_node["roles"]:
        cmd += f" --role {role}"
    cmd += f" --token {token}"
    rc = ssh(user, s_host_ext, cmd)
    if rc > 0:
        die("joining node failed, aborting")

    # get some status
    ssh(user, p_host_ext, "sunbeam cluster list")

if control_count < 3:
    debug("Skipping 'resize' because there's not enough control nodes")
else:
    cmd = "sunbeam cluster resize"
    rc = ssh(user, p_host_ext, cmd)
    if rc > 0:
        die("resizing cluster failed, aborting")

cmd = "sunbeam configure -p ~/preseed.yaml --openrc ~/demo-openrc && echo > ~/demo-openrc"
rc = ssh(user, p_host_ext, cmd)
if rc > 0:
    die("configuring demo project failed, aborting")

cmd = "sunbeam openrc > ~/admin-openrc"
rc = ssh(user, p_host_ext, cmd)
if rc > 0:
    die("exporting admin credentials failed, aborting")

cmd = "sunbeam launch ubuntu --name test"
rc = ssh(user, p_host_ext, cmd)
if rc > 0:
    die("creating test vm failed, aborting")
