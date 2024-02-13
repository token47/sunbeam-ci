#!/usr/bin/python3 -u

import utils


utils.debug("started testing")

config = utils.read_config()
user = config["user"]
nodes = list(filter(lambda x: 'control' in x["roles"], config["nodes"]))
#nodes += list(filter(lambda x: 'control' not in x["roles"], config["nodes"]))
primary_node = nodes.pop(0)

p_host_name_int = primary_node["host-name-int"]
p_host_name_ext = primary_node["host-name-ext"]
p_host_ip_int = primary_node["host-ip-int"]
p_host_ip_ext = primary_node["host-ip-ext"]

# this is a basic test, there will be better ones later
# but we keep this one as it is on the documentation
# and the user will likely execute exactly this
cmd = "sunbeam launch ubuntu --name test"
rc = utils.ssh_filtered(user, p_host_ip_ext, cmd)
if rc > 0:
    utils.die("creating test vm failed, aborting")
