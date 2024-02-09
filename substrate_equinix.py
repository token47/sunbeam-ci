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
    #preseed = {
    #    "bootstrap": { "management_cidr": "172.27.76.0/23", },
    #    "addons": { "metallb": "172.27.76.21-172.27.76.50", },
    #    "user": {
    #        "remote_access_location": "remote",
    #        "run_demo_setup": True, # don't quote
    #        "username": "demo",
    #        "password": "password123",
    #        "cidr": "192.168.122.0/24",
    #        "nameservers": "172.27.79.254",
    #        "security_group_rules": True, # don't quote
    #    },
    #    "external_network": {
    #        "cidr": "172.27.78.0/23",
    #        "gateway": "172.27.79.254",
    #        "start": "172.27.78.1",
    #        "end": "172.27.78.50",
    #        "network_type": "flat",
    #        "segmentation_id": "0",
    #        "nic": "usb-nic",
    #    },
    #    "microceph_config": {}, # to be filled later
    #}

    hosts_qty = len(input_config["roles"])
    utils.debug(f"allocating {hosts_qty} hosts in equinix")

    rc = utils.exec_cmd("terraform -chdir=terraform/equinix init -no-color")
    if rc > 0:
        utils.die("could not run terraform init")
    rc = utils.exec_cmd("time terraform -chdir=terraform/equinix apply -auto-approve -no-color" \
                  f" -var='maas_hosts_qty={hosts_qty}'")
    if rc > 0:
        utils.die("could not run terraform apply")
    equinix_hosts = json.loads(
        utils.exec_cmd_capture("terraform -chdir=terraform/equinix output -no-color -json equinix_hosts"))
    utils.debug(f"captured 'equinix_hosts' terraform output: {equinix_hosts}")

    #nodes = []
    #nodes_roles = dict(zip(equinix_hosts, input_config["roles"]))
    #for nodename, ipaddress in equinix_hosts.items():
    #    newnode = {}
    #    newnode["host-int"] = nodename
    #    newnode["host-ext"] = nodename
    #    newnode["roles"] = nodes_roles[nodename].split(",")
    #    nodes.append(newnode)
    #    preseed["microceph_config"][nodename] = {}
    #    preseed["microceph_config"][nodename]["osd_devices"] = "/dev/sdb"

    output_config = {}
    output_config["nodes"] = nodes
    output_config["user"] = "ubuntu"
    output_config["channel"] = input_config["channel"]
    output_config["preseed"] = preseed

    utils.write_config(output_config)


def destroy(input_config):
    hosts_qty = len(input_config["roles"])
    rc = utils.exec_cmd("terraform -chdir=terraform/equinix destroy -auto-approve -no-color" \
                        f" -var='maas_hosts_qty={hosts_qty}'")
    if rc > 0:
        utils.die("could not run terraform destroy")