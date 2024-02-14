#!/bin/false

import os
import json
import utils

"""
    Config examples:

    input_config:
    {
        "substrate": "equinix",
        "channel": "2023.2/edge",
        "roles": [
            "storage,compute,control",
            "storage,compute",
            "storage,compute"
        ]
    }

    creds:
    {
        "project_id": "xxx",
        "api_key": "xxx"
    }
"""


def execute(config, creds, action):
    # use env so that sensitive info does not show in debug log
    os.environ["TF_VAR_equinix_project_id"] = creds["project_id"]
    os.environ["TF_VAR_equinix_api_key"] = creds["api_key"]

    if action == "build":
        build(config)
    elif action == "destroy":
        destroy(config)
    else:
        utils.die("Invalid action parameter")


def build(input_config):
    manifest = {
        "deployment": {
            "bootstrap": { "management_cidr": "10.0.1.0/24", },
            "addons": { "metallb": "10.0.1.20-10.0.1.29", },
            "user": {
                "remote_access_location": "remote",
                "run_demo_setup": True, # don't quote
                "username": "demo",
                "password": "password123",
                "cidr": "192.168.122.0/24",
                "nameservers": "8.8.8.8",
                "security_group_rules": True, # don't quote
            },
            "external_network": {
                "cidr": "10.0.2.0/24",
                "gateway": "10.0.2.1",
                "start": "10.0.2.11",
                "end": "10.0.2.254",
                "network_type": "flat",
                "segmentation_id": "0",
                "nic": "bond0.1002",
            },
            "microceph_config": {}, # to be filled later
        },
        "software": {}, # to be filled later
    }

    hosts_qty = len(input_config["roles"])
    utils.debug(f"allocating {hosts_qty} hosts in equinix")

    rc = utils.exec_cmd("terraform -chdir=terraform/equinix init -no-color")
    if rc > 0:
        utils.die("could not run terraform init")

    rc = utils.exec_cmd("terraform -chdir=terraform/equinix apply -auto-approve -no-color" \
                  f" -var='equinix_hosts_qty={hosts_qty}'")
    if rc > 0:
        utils.die("could not run terraform apply")

    rc = utils.exec_cmd("terraform -chdir=terraform/equinix show -no-color")
    if rc > 0:
        utils.die("could not run terraform show")

    equinix_vlans = json.loads(
        utils.exec_cmd_capture("terraform -chdir=terraform/equinix output -no-color -json equinix_vlans"))
    utils.debug(f"captured 'equinix_vlans' terraform output: {equinix_vlans}")

    equinix_hosts = json.loads(
        utils.exec_cmd_capture("terraform -chdir=terraform/equinix output -no-color -json equinix_hosts"))
    utils.debug(f"captured 'equinix_hosts' terraform output: {equinix_hosts}")

    nodes = []
    nodes_roles = dict(zip(equinix_hosts.keys(), input_config["roles"]))
    sunbeam_hostname_generator = utils.hostname_generator(prefix="10.0.1.", start=11, domain="mydomain")
    for nodename, ipaddress in equinix_hosts.items():
        s = next(sunbeam_hostname_generator)
        nodes.append({
            "host-name-ext": nodename,
            "host-name-int": s["fqdn"],
            "host-ip-ext": ipaddress,
            "host-ip-int": s["ip"],
            "roles": nodes_roles[nodename].split(","),
        })
        manifest["deployment"]["microceph_config"][s["fqdn"]] = { "osd_devices": "/dev/sdb" }

    output_config = {}
    output_config["nodes"] = nodes
    output_config["user"] = "ubuntu" # we use root to configre but deployment uses ubuntu
    output_config["channel"] = input_config["channel"]
    output_config["manifest"] = manifest

    utils.write_config(output_config)

    # this substrate needs extra steps preparing the OS to be on par with maas substrate
    configure_hosts(output_config, equinix_vlans)


def destroy(input_config):
    hosts_qty = len(input_config["roles"])
    rc = utils.exec_cmd("terraform -chdir=terraform/equinix destroy -auto-approve -no-color" \
                        f" -var='equinix_hosts_qty={hosts_qty}'")
    if rc > 0:
        utils.die("could not run terraform destroy")


def configure_hosts(config, vlans):
    vlan_oam = vlans["oam"]
    vlan_ovn = vlans["ovn"]

    # we need to collect all hostnames first (to use in /etc/hosts), then loop again later
    etc_hosts_snippet = ""
    for node in config["nodes"]:
        host_name_int = node["host-name-int"]
        host_ip_int = node["host-ip-int"]
        etc_hosts_snippet += f"{host_ip_int}\t{host_name_int} {host_name_int.split('.')[0]}\n"

    for node in config["nodes"]:
        host_name_ext = node["host-name-ext"]
        host_name_int = node["host-name-int"]
        host_ip_ext = node["host-ip-ext"]
        host_ip_int = node["host-ip-int"]

        utils.debug(f"Starting configuration for host '{host_name_ext}'")

        utils.ssh_clean(host_ip_ext)
        utils.test_ssh("root", host_ip_ext)

        cmd = "apt -q update && DEBIAN_FRONTEND=noninteractive apt -q -o " \
            "Dpkg::Progress-Fancy=0 -o APT::Color=0 -o Dpkg::Use-Pty=0 upgrade -y"
        rc = utils.ssh_filtered("root", host_ip_ext, cmd)
        if rc > 0:
            utils.die("running apt update/upgrade failed, aborting")        

        cmd = \
            'echo "\n' \
            f'auto bond0.{vlan_oam}\n' \
            f'iface bond0.{vlan_oam} inet static\n' \
            '    vlan-raw-device bond0\n' \
            f'    address {host_ip_int}\n' \
            '    netmask 255.255.255.0\n' \
            '    #post-up ip route add 10.0.2.0/24 via 10.0.1.1\n' \
            '\n' \
            f'auto bond0.{vlan_ovn}\n' \
            f'iface bond0.{vlan_ovn} inet manual\n' \
            '    vlan-raw-device bond0\n' \
            '" >> /etc/network/interfaces && \\\n' \
            'echo "\\\n' \
            '::1 localhost ip6-localhost ip6-loopback\n' \
            'ff02::1 ip6-allnodes\n' \
            'ff02::2 ip6-allrouters\n' \
            '127.0.0.1   localhost\n' \
            '#10.0.1.1    sunbeamgw.mydomain sunbeamgw\n' \
            f'{etc_hosts_snippet}' \
            '" > /etc/hosts && \\\n' \
            f'hostnamectl set-hostname {host_name_int} && \\\n' \
            'systemctl restart networking\n'
        rc = utils.ssh("root", host_ip_ext, cmd)
        if rc > 0:
            utils.die("error updating network configs, aborting")        

        cmd = """ set -e
            useradd -m ubuntu
            adduser ubuntu adm
            adduser ubuntu admin
            chsh -s /bin/bash ubuntu
            echo "ubuntu:ubuntu" | chpasswd ubuntu
            echo "ubuntu ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers
            mkdir /home/ubuntu/.ssh
            chmod 700 /home/ubuntu/.ssh
            touch /home/ubuntu/.ssh/authorized_keys
            chmod 600 /home/ubuntu/.ssh/authorized_keys
            chown -R ubuntu:ubuntu /home/ubuntu/.ssh
            cat /root/.ssh/authorized_keys >> /home/ubuntu/.ssh/authorized_keys
        """
        rc = utils.ssh("root", host_ip_ext, cmd)
        if rc > 0:
            utils.die("error configuring ubuntu user, aborting")        
