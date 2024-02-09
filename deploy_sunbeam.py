#!/usr/bin/python3 -u

"""
This script deploys sunbeam on a substrate that has already been prepared for it.
"""

import re
import utils
import yaml


def token_extract(text):
    match = re.search("Token for the Node [^ ]+: ([^ \\r\\n]+)", text)
    if match is None:
        utils.debug("RE for add host token did not match")
        utils.debug(text)
        utils.die("aborting")
    return match.group(1)


config = utils.read_config()

# order hosts to have control nodes first, then separete primary node from others
nodes = list(filter(lambda x: 'control' in x["roles"], config["nodes"]))
control_count = len(nodes)
nodes += list(filter(lambda x: 'control' not in x["roles"], config["nodes"]))
utils.debug(f"detected control nodes / total nodes count is {control_count} / {len(nodes)}")
utils.debug(f"complete list of nodes: {nodes}")
primary_node = nodes.pop(0)

### Primary node / bootstrap

user = config["user"]
p_host_int = primary_node["host-int"]
p_host_ext = primary_node["host-ext"]

utils.debug(f"installing primary node {p_host_int} / {p_host_ext}")

utils.ssh_clean(p_host_ext)
utils.test_ssh(user, p_host_ext)

cmd = f"sudo snap install openstack --channel {config['channel']}"
rc = utils.ssh_filtered(user, p_host_ext, cmd)
if rc > 0:
    utils.die("installing openstack snap failed, aborting")

cmd = "sunbeam prepare-node-script | grep -v newgrp | bash -x"
rc = utils.ssh(user, p_host_ext, cmd)
if rc > 0:
    utils.die("running prepare-node-script failed, aborting")

utils.put(user, p_host_ext, "~/manifest.yaml", yaml.dump(config["manifest"]))

cmd = "sunbeam cluster bootstrap -m ~/manifest.yaml"
for role in primary_node["roles"]:
    cmd += f" --role {role}"
rc = utils.ssh_filtered(user, p_host_ext, cmd)
if rc > 0:
    utils.die("bootstrapping sunbeam failed, aborting")

utils.ssh(user, p_host_ext, "sunbeam cluster list")

### Other nodes

for node in nodes:
    s_host_int = node["host-int"]
    s_host_ext = node["host-ext"]

    utils.debug(f"installing secondary node {s_host_int} / {s_host_ext}")

    utils.ssh_clean(s_host_ext)
    utils.test_ssh(user, s_host_ext)

    cmd = f"sudo snap install openstack --channel {config['channel']}\n"
    rc = utils.ssh_filtered(user, s_host_ext, cmd)
    if rc > 0:
        utils.die("installing openstack snap failed, aborting")

    cmd = "sunbeam prepare-node-script | grep -v newgrp | bash -x"
    rc = utils.ssh(user, s_host_ext, cmd)
    if rc > 0:
        utils.die("running prepare-node-script failed, aborting")

    utils.put(user, s_host_ext, "~/manifest.yaml", yaml.dump(config["manifest"]))

    cmd = f"sunbeam cluster add --name {s_host_int}"
    token = token_extract(utils.ssh_capture(user, p_host_ext, cmd))

    cmd = "sunbeam cluster join -m ~/manifest.yaml"
    for role in node["roles"]:
        cmd += f" --role {role}"
    cmd += f" --token {token}"
    rc = utils.ssh_filtered(user, s_host_ext, cmd)
    if rc > 0:
        utils.die("joining node failed, aborting")

    # get some status
    utils.ssh(user, p_host_ext, "sunbeam cluster list")

if control_count < 3:
    utils.debug("Skipping 'resize' because there's not enough control nodes")
else:
    cmd = "sunbeam cluster resize"
    rc = utils.ssh_filtered(user, p_host_ext, cmd)
    if rc > 0:
        utils.die("resizing cluster failed, aborting")

cmd = "sunbeam configure -m ~/manifest.yaml --openrc ~/demo-openrc && echo > ~/demo-openrc"
rc = utils.ssh_filtered(user, p_host_ext, cmd)
if rc > 0:
    utils.die("configuring demo project failed, aborting")

cmd = "sunbeam openrc > ~/admin-openrc"
rc = utils.ssh(user, p_host_ext, cmd)
if rc > 0:
    utils.die("exporting admin credentials failed, aborting")

cmd = "sunbeam launch ubuntu --name test"
rc = utils.ssh(user, p_host_ext, cmd)
if rc > 0:
    utils.die("creating test vm failed, aborting")