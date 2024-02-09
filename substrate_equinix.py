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
        #"software": {
        #    "juju": { "bootstrap_args": [ "--debug" ], },
        #    "charms": { "mysql-k8s": { "channel": "8.0/edge", }, "mysql-router-k8s": { "channel": "8.0/edge", },
        #    },
        #}
    }

    hosts_qty = len(input_config["roles"])
    utils.debug(f"allocating {hosts_qty} hosts in equinix")

    rc = utils.exec_cmd("terraform -chdir=terraform/equinix init -no-color")
    if rc > 0:
        utils.die("could not run terraform init")

    rc = utils.exec_cmd("time terraform -chdir=terraform/equinix apply -auto-approve -no-color" \
                  f" -var='equinix_hosts_qty={hosts_qty}'")
    if rc > 0:
        utils.die("could not run terraform apply")

    equinix_vlans = json.loads(
        utils.exec_cmd_capture("terraform -chdir=terraform/equinix output -no-color -json equinix_vlans"))
    utils.debug(f"captured 'equinix_vlans' terraform output: {equinix_vlans}")

    equinix_hosts = json.loads(
        utils.exec_cmd_capture("terraform -chdir=terraform/equinix output -no-color -json equinix_hosts"))
    utils.debug(f"captured 'equinix_hosts' terraform output: {equinix_hosts}")

    nodes = []
    nodes_roles = dict(zip(equinix_hosts.keys(), input_config["roles"]))
    ip = utils.internal_ip_generator(prefix="10.0.1.", start=11)
    for nodename, ipaddress in equinix_hosts.items():
        newnode = {}
        newnode["host-int"] = next(ip)
        newnode["host-ext"] = ipaddress
        newnode["roles"] = nodes_roles[nodename].split(",")
        nodes.append(newnode)
        manifest["deployment"]["microceph_config"][nodename] = {}
        manifest["deployment"]["microceph_config"][nodename]["osd_devices"] = "/dev/sdb"

    output_config = {}
    output_config["nodes"] = nodes
    output_config["user"] = "ubuntu" # we use root to configre but deployment uses ubuntu
    output_config["channel"] = input_config["channel"]
    output_config["manifest"] = manifest

    utils.write_config(output_config)


def destroy(input_config):
    hosts_qty = len(input_config["roles"])
    rc = utils.exec_cmd("terraform -chdir=terraform/equinix destroy -auto-approve -no-color" \
                        f" -var='equinix_hosts_qty={hosts_qty}'")
    if rc > 0:
        utils.die("could not run terraform destroy")