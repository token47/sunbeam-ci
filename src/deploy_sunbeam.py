#!/usr/bin/python3 -u

"""
This script deploys sunbeam on a substrate that has already been prepared for it.
"""

import utils
from sshclient import SSHClient


config = utils.read_config()

# manifest software override options
# TODO: implement importing edge.yaml file from snap instead of hardcoding these versions
#       making this flexible (easy to chose between stable, candidate, edge, etc.)
#       actually taking this as a parameter from the profile or from jenkins
#       (make it possible to override specifics from the profile -- apply it AFTER this)
config["manifest"]["software"].update({
    #"juju": {
    #    "bootstrap_args": [ "--debug" ],
    #},
    "charms": {
    #    "microk8s": { config: { containerd_env: "..."}, custom_registries: [ { url: "...", host: "...", } ], },
        "aodh-k8s":                 { "channel": "2023.2/edge" },
        "barbican-k8s":             { "channel": "2023.2/edge" },
        "ceilometer-k8s":           { "channel": "2023.2/edge" },
        "cinder-ceph-k8s":          { "channel": "2023.2/edge" },
        "cinder-k8s":               { "channel": "2023.2/edge" },
        "designate-bind-k8s":       { "channel": "9/edge" },
        "designate-k8s":            { "channel": "2023.2/edge" },
        "glance-k8s":               { "channel": "2023.2/edge" },
        "gnocchi-k8s":              { "channel": "2023.2/edge" },
        "heat-k8s":                 { "channel": "2023.2/edge" },
        "horizon-k8s":              { "channel": "2023.2/edge" },
        "keystone-k8s":             { "channel": "2023.2/edge" },
        "keystone-ldap-k8s":        { "channel": "2023.2/edge" },
        "magnum-k8s":               { "channel": "2023.2/edge" },
        "neutron-k8s":              { "channel": "2023.2/edge" },
        "nova-k8s":                 { "channel": "2023.2/edge" },
        "octavia-k8s":              { "channel": "2023.2/edge" },
        "openstack-exporter-k8s":   { "channel": "2023.2/edge" },
        "openstack-hypervisor":     { "channel": "2023.2/edge", "config": { "snap-channel": "2023.2/edge" } },
        "ovn-central-k8s":          { "channel": "23.09/edge" },
        "ovn-relay-k8s":            { "channel": "23.09/edge" },
        "placement-k8s":            { "channel": "2023.2/edge" },
        "sunbeam-clusterd":         { "channel": "2023.2/edge", "config": { "snap-channel": "2023.2/edge" } },
        "sunbeam-machine":          { "channel": "2023.2/edge" },
        "tempest-k8s":              { "channel": "2023.2/edge" },
        "microceph":                { "channel": "reef/edge" },
    },
})

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

cmd = f"sudo snap install openstack --channel {config['channel']}"
out, rc = p_sshclient.execute(
    cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
if rc > 0:
    utils.die("installing openstack snap failed, aborting")

cmd = "sunbeam prepare-node-script | grep -v newgrp | bash -x"
out, rc = p_sshclient.execute(
    cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
if rc > 0:
    utils.die("running prepare-node-script failed, aborting")

utils.debug("Force new SSH connection to activate new groups on remote user")
p_sshclient.close()

m = utils.yaml_dump(config["manifest"])
p_sshclient.file_write("manifest.yaml", m)
utils.debug(f"Manifest contents are:\n{m.rstrip()}")

cmd = "sunbeam cluster bootstrap -m ~/manifest.yaml"
for role in primary_node["roles"]:
    cmd += f" --role {role}"
out, rc = p_sshclient.execute(
    cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
# hack for websocket error
if rc == 1001:
    utils.debug("Retrying because of websocker error")
    out, rc = p_sshclient.execute(
        cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
if rc > 0:
    utils.die("bootstrapping sunbeam failed, aborting")

cmd = "sunbeam cluster list"
out, rc = p_sshclient.execute(
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

    cmd = f"sudo snap install openstack --channel {config['channel']}\n"
    out, rc = s_sshclient.execute(
        cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
    if rc > 0:
        utils.die("installing openstack snap failed, aborting")

    cmd = "sunbeam prepare-node-script | grep -v newgrp | bash -x"
    out, rc = s_sshclient.execute(
        cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
    if rc > 0:
        utils.die("running prepare-node-script failed, aborting")

    utils.debug("Force new SSH connection to activate new groups on remote user")
    s_sshclient.close()

    cmd = f"sunbeam cluster add --format yaml --name {s_host_name_int}"
    out, rc = p_sshclient.execute(
        cmd, verbose=False, get_pty=False, combine_stderr=False, filtered=False)
    token = utils.yaml_safe_load(out)["token"]
    utils.debug(f"Got token: {token}")
    token_decoded = utils.b64decode(token).decode("utf-8")
    utils.debug(f"Decoded token: {token_decoded}")

    cmd = "sunbeam cluster join"
    for role in node["roles"]:
        cmd += f" --role {role}"
    cmd += f" --token {token}"
    out, rc = s_sshclient.execute(
        cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
    if rc > 0:
        utils.die("joining node failed, aborting")

    cmd = "sunbeam cluster list"
    out, rc = p_sshclient.execute(
        cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)

    s_sshclient.close()

if control_count < 3:
    utils.debug("Skipping 'resize' because there's not enough control nodes")
else:
    cmd = "sunbeam cluster resize"
    out, rc = p_sshclient.execute(
        cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
    if rc > 0:
        utils.die("resizing cluster failed, aborting")

cmd = "sunbeam configure --openrc ~/demo-openrc && echo > ~/demo-openrc"
out, rc = p_sshclient.execute(
    cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
if rc > 0:
    # START OF HACK -- workaround for ceph size/min_size bug (temporary):
    # in case configure fails and the node has storage role, try this workaround
    # this is considering first node is storage (as mentioned, just a quick hack)
    if "storage" in primary_node["roles"]:
        utils.debug("Applying HACK for ceph size/min_size 3 issue, retrying configure")
        cmd = """set -x
            sudo ceph osd pool set glance min_size 1
            sudo ceph osd pool set glance size 1 --yes-i-really-mean-it
            sudo ceph osd pool set cinder-ceph min_size 1
            sudo ceph osd pool set cinder-ceph size 1 --yes-i-really-mean-it
        """
        out, rc = p_sshclient.execute(
            cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
        if rc > 0:
            utils.die("error applying hack for ceph size/min_size issue, aborting")
    # and then try the configure one more time and update rc vaule
    cmd = "sunbeam configure --openrc ~/demo-openrc && echo > ~/demo-openrc"
    out, rc = p_sshclient.execute(
        cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
    if rc > 0:
    # END OF HACK
        utils.die("configuring demo project failed, aborting")

cmd = "sunbeam openrc > ~/admin-openrc"
out, rc = p_sshclient.execute(
    cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
if rc > 0:
    utils.die("exporting admin credentials failed, aborting")

p_sshclient.close()
