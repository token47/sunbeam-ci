#!/usr/bin/python3

# This script deploys sunbeam on a substrate that has already been prepared for it.

import yaml
import re
import subprocess
import sys


def ssh(user, host, cmd):
    cmd = f"ssh -o StrictHostKeyChecking=no -t {user}@{host} 'set -x; {cmd}'"
    print(f"DEBUG SSH: {user}@{host}")
    result = subprocess.run(cmd, shell=True)


def ssh_clean(host):
    cmd = f"ssh-keygen -f ~/.ssh/known_hosts -R {host}"
    result = subprocess.run(cmd, shell=True)


def ssh_capture(user, host, cmd):
    cmd = f"ssh -o StrictHostKeyChecking=no -t {user}@{host} '{cmd}'"
    print(f"DEBUG SSH-CAPTURE: {cmd}")
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout.decode()


def put(user, host, file, content):
    cmd = f"ssh -o StrictHostKeyChecking=no {user}@{host} 'tee {file}'"
    print(f"DEBUG PUT: {user}@{host} {file}")
    result = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE)
    result.stdin.write(content.encode())
    result.stdin.close()
    result.wait()


def token_extract(text):
    try:
        match = re.search("Token for the Node [^ ]+: ([^ \\r\\n]+)", text)
    except:
        print("RE for host add token did not match")
        print(text)
        sys.exit(1)
    return match.group(1)


with open("config.yaml", "r") as stream:
    config = yaml.safe_load(stream)

# order hosts to have control nodes first, then separete primary node from others
nodes = list(filter(lambda x: 'control' in x["roles"], config["nodes"]))
control_count = len(nodes)
nodes += list(filter(lambda x: 'control' not in x["roles"], config["nodes"]))
print(f"DEBUG: detected control nodes count is {control_count}")
print(f"DEBUG: total nodes count is {len(nodes)}")
print(f"DEBUG: complete list of nodes: {nodes}")
primary_node = nodes.pop(0)

### Primary node / bootstrap

p_user = primary_node["user"]
p_host_int = primary_node["host-int"]
p_host_ext = primary_node["host-ext"]

print("DEBUG: installing primary node {} / {}".format(p_host_int, p_host_ext))

ssh_clean(p_host_ext)

cmd = "sudo snap install openstack --channel {}".format(config['channel'])
ssh(p_user, p_host_ext, cmd)

cmd = "sunbeam prepare-node-script | grep -v newgrp | bash -x"
ssh(p_user, p_host_ext, cmd)

put(p_user, p_host_ext, "~/preseed.yaml", yaml.dump(config["preseed"]))

cmd = "time sunbeam cluster bootstrap -p ~/preseed.yaml"
for role in primary_node["roles"]: cmd += f" --role {role}"
ssh(p_user, p_host_ext, cmd)

ssh(p_user, p_host_ext, "sunbeam cluster list")

### Other nodes

for node in nodes:
    s_user = node["user"]
    s_host_int = node["host-int"]
    s_host_ext = node["host-ext"]

    print("DEBUG: installing secondary node {} / {}".format(s_host_int, s_host_ext))

    ssh_clean(s_host_ext)

    cmd = "sudo snap install openstack --channel {}\n".format(config['channel'])
    cmd += "sunbeam prepare-node-script | grep -v newgrp | bash -x"
    ssh(s_user, s_host_ext, cmd)

    put(s_user, s_host_ext, "~/preseed.yaml", yaml.dump(config["preseed"]))

    cmd = f"sunbeam cluster add --name {s_host_int}"
    token = token_extract(ssh_capture(p_user, p_host_ext, cmd))

    cmd = "time sunbeam cluster join -p ~/preseed.yaml"
    for role in primary_node["roles"]: cmd += f" --role {role}"
    cmd += f" --token {token}"
    ssh(s_user, s_host_ext, cmd)

    # get some status
    ssh(p_user, p_host_ext, "sunbeam cluster list")

if control_count >= 3:
    cmd = "time sunbeam cluster resize"
    ssh(p_user, p_host_ext, cmd)

cmd = "time sunbeam configure -p ~/preseed.yaml --openrc ~/demo-openrc; echo > ~/demo-openrc"
ssh(p_user, p_host_ext, cmd)

cmd = "sunbeam openrc > ~/admin-openrc"
ssh(p_user, p_host_ext, cmd)

cmd = "sunbeam launch ubuntu --name test"
ssh(p_user, p_host_ext, cmd)
