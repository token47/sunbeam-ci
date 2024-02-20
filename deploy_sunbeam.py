#!/usr/bin/python3 -u

"""
This script deploys sunbeam on a substrate that has already been prepared for it.
"""

import utils
from sshclient import SSHClient


config = utils.read_config()

# manifest software override options
#config["manifest"]["software"].update({
#    #"juju": {
#    #    "bootstrap_args": [ "--debug" ],
#    #},
#    #"charms": {
#    #    "mysql-k8s": { "channel": "8.0/edge", },
#    #    "mysql-router-k8s": { "channel": "8.0/edge", },
#    #    "microk8s": { config: { containerd_env: "..."}, custom_registries: [ { url: "...", host: "...", } ], },
#    #},
#})

# order hosts to have control nodes first, then separete primary node from others
nodes = list(filter(lambda x: 'control' in x["roles"], config["nodes"]))
control_count = len(nodes)
nodes += list(filter(lambda x: 'control' not in x["roles"], config["nodes"]))
utils.debug(f"detected count of control nodes is {control_count}")
utils.debug(f"detected count of total nodes is {len(nodes)}")
utils.debug(f"complete list of nodes: {nodes}")
primary_node = nodes.pop(0)
utils.debug(f"selected primary node: {primary_node}")
utils.debug(f"secondary nodes list: {nodes}")

### Primary node / bootstrap

user = config["user"]
p_host_name_int = primary_node["host-name-int"]
p_host_name_ext = primary_node["host-name-ext"]
p_host_ip_int = primary_node["host-ip-int"]
p_host_ip_ext = primary_node["host-ip-ext"]

utils.debug(f"installing primary node {p_host_name_ext} / {p_host_ip_ext} " \
            f"/ {p_host_name_int} / {p_host_ip_int}")

p_sshclient = SSHClient(user, p_host_ip_ext)

if not p_sshclient.server_available():
    utils.die("Aborting")

cmd = f"sudo snap install openstack --channel {config['channel']}"
out, err, rc = p_sshclient.execute(
    cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
if rc > 0:
    utils.die("installing openstack snap failed, aborting")

cmd = "sunbeam prepare-node-script | grep -v newgrp | bash -x"
out, err, rc = p_sshclient.execute(
    cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
if rc > 0:
    utils.die("running prepare-node-script failed, aborting")

utils.debug("Force new SSH connection to activate new groups on remote user")
p_sshclient.close()

m = utils.yaml_dump(config["manifest"])
p_sshclient.file_write("manifest.yaml", m)
utils.debug(f"Manifest contents are:\n{m}")

cmd = "FORCE_COLOR=1 sunbeam cluster bootstrap -m ~/manifest.yaml"
for role in primary_node["roles"]:
    cmd += f" --role {role}"
out, err, rc = p_sshclient.execute(
    cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
#if rc == 1001:
#    utils.debug("Retrying because of websocker error")
#    out, err, rc = p_sshclient.execute(
#        cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
if rc > 0:
    utils.die("bootstrapping sunbeam failed, aborting")

cmd = "sunbeam cluster list"
out, err, rc = p_sshclient.execute(
    cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)

### Other nodes

for node in nodes:
    s_host_name_int = node["host-name-int"]
    s_host_name_ext = node["host-name-ext"]
    s_host_ip_int = node["host-ip-int"]
    s_host_ip_ext = node["host-ip-ext"]

    utils.debug(f"installing seconday node {s_host_name_ext} / {s_host_ip_ext} " \
                f"/ {s_host_name_int} / {s_host_ip_int}")

    s_sshclient = SSHClient(user, s_host_ip_ext)

    if not s_sshclient.server_available():
        utils.die("Aborting")

    cmd = f"sudo snap install openstack --channel {config['channel']}\n"
    out, err, rc = s_sshclient.execute(
        cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
    if rc > 0:
        utils.die("installing openstack snap failed, aborting")

    cmd = "sunbeam prepare-node-script | grep -v newgrp | bash -x"
    out, err, rc = s_sshclient.execute(
        cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
    if rc > 0:
        utils.die("running prepare-node-script failed, aborting")

    utils.die("Force new SSH connection to activate new groups on remote user")
    s_sshclient.close()

    cmd = f"sunbeam cluster add --name {s_host_name_int}"
    out, err, rc = p_sshclient.execute(
        cmd, verbose=False, get_pty=True, combine_stderr=False, filtered=False)
    token = utils.token_extract(out)
    utils.debug(f"Got token: {token}")
    utils.debug(f"Decoded token: {utils.b64decode(token)}")

    cmd = "sunbeam cluster join"
    for role in node["roles"]:
        cmd += f" --role {role}"
    cmd += f" --token {token}"
    out, err, rc = s_sshclient.execute(
        cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
    if rc > 0:
        utils.die("joining node failed, aborting")

    cmd = "sunbeam cluster list"
    out, err, rc = p_sshclient.execute(
        cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)

    s_sshclient.close()

if control_count < 3:
    utils.debug("Skipping 'resize' because there's not enough control nodes")
else:
    cmd = "FORCE_COLOR=1 sunbeam cluster resize"
    out, err, rc = p_sshclient.execute(
        cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
    if rc > 0:
        utils.die("resizing cluster failed, aborting")

cmd = "FORCE_COLOR=1 sunbeam configure --openrc ~/demo-openrc && echo > ~/demo-openrc"
out, err, rc = p_sshclient.execute(
    cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
if rc > 0:
    utils.die("configuring demo project failed, aborting")

cmd = "FORCE_COLOR=1 sunbeam openrc > ~/admin-openrc"
out, err, rc = p_sshclient.execute(
    cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
if rc > 0:
    utils.die("exporting admin credentials failed, aborting")

p_sshclient.close()
