#!/usr/bin/python3 -u

# This script deploys sunbeam on a substrate that has already been prepared for it.

import yaml
import re


def token_extract(text):
    try:
        match = re.search("Token for the Node [^ ]+: ([^ \\r\\n]+)", text)
    except:
        debug("RE for host add token did not match")
        debug(text)
        die("aborting")
    return match.group(1)


with open("config.yaml", "r") as stream:
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

debug("installing primary node {} / {}".format(p_host_int, p_host_ext))

ssh_clean(p_host_ext)

cmd = "sudo snap install openstack --channel {}".format(config['channel'])
ssh(user, p_host_ext, cmd)

cmd = "sunbeam prepare-node-script | grep -v newgrp | bash -x"
ssh(user, p_host_ext, cmd)

put(user, p_host_ext, "~/preseed.yaml", yaml.dump(config["preseed"]))

cmd = "time sunbeam cluster bootstrap -p ~/preseed.yaml"
for role in primary_node["roles"]: cmd += f" --role {role}"
ssh(user, p_host_ext, cmd)

ssh(user, p_host_ext, "sunbeam cluster list")

### Other nodes


for node in nodes:
    s_host_int = node["host-int"]
    s_host_ext = node["host-ext"]

    debug("installing secondary node {} / {}".format(s_host_int, s_host_ext))

    ssh_clean(s_host_ext)

    cmd = "sudo snap install openstack --channel {}\n".format(config['channel'])
    cmd += "sunbeam prepare-node-script | grep -v newgrp | bash -x"
    ssh(user, s_host_ext, cmd)

    put(user, s_host_ext, "~/preseed.yaml", yaml.dump(config["preseed"]))

    cmd = f"sunbeam cluster add --name {s_host_int}"
    token = token_extract(ssh_capture(user, p_host_ext, cmd))

    cmd = "time sunbeam cluster join -p ~/preseed.yaml"
    for role in primary_node["roles"]: cmd += f" --role {role}"
    cmd += f" --token {token}"
    ssh(user, s_host_ext, cmd)

    # get some status
    ssh(user, p_host_ext, "sunbeam cluster list")

if control_count < 3:
    debug("Skipping 'resize' because there's not enough control nodes")
else:
    cmd = "time sunbeam cluster resize"
    ssh(user, p_host_ext, cmd)

cmd = "time sunbeam configure -p ~/preseed.yaml --openrc ~/demo-openrc; echo > ~/demo-openrc"
ssh(user, p_host_ext, cmd)

cmd = "sunbeam openrc > ~/admin-openrc"
ssh(user, p_host_ext, cmd)

cmd = "sunbeam launch ubuntu --name test"
ssh(user, p_host_ext, cmd)
