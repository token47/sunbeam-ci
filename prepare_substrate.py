#!/usr/bin/python3 -u

# this script will deploy nodes and prepare the environemnt before sunbeam deployment

import json
import os
from utils import *
import yaml


def get_input_config_json_defaults():
    return """
    { "substrate": "ob76",
      "channel": "2023.2/edge",
      "roles": [ "control", "storage,compute", "storage,compute" ]
    }
    """


def write_config(config):
    debug("writing config:\n{}".format(config))
    with open("config.yaml", "w") as fd:
        fd.write(yaml.dump(config))


def substrate_ob76(input_config):
    debug("Starting ob76 substrate preparation")

    apikey = os.environ.get("JENKINS_API_KEY")
    if not apikey:
        die("JENKINS_API_KEY not set, terraform will fail, aborting")
    # use env so that api key does not show in debug log
    os.environ['TF_VAR_maas_api_key'] = apikey

    preseed = {
        "bootstrap": { "management_cidr": "172.27.76.0/23", },
        "addons": { "metallb": "172.27.76.21-172.27.76.50", },
        "user": {
            "remote_access_location": "remote",
            "run_demo_setup": "True",
            "username": "demo",
            "password": "password123",
            "cidr": "192.168.122.0/24",
            "nameservers": "172.27.79.254",
            "security_group_rules": "True",
        },
        "external_network": {
            "cidr": "172.27.78.0/23",
            "gateway": "172.27.79.254",
            "start": "172.27.78.1",
            "end": "172.27.78.50",
            "network_type": "flat",
            "segmentation_id": "0",
            "nic": "usb-nic",
        },
        "microceph_config": {}
    }

    hosts_qty = len(input_config["roles"])
    debug(f"allocating {hosts_qty} hosts in maas")

    rc = exec("terraform -chdir=terraform/maas init -no-color")
    if rc > 0: die("could not run terraform init") 
    rc = exec("time terraform -chdir=terraform/maas apply -auto-approve -no-color" \
              f" -var='maas_hosts_qty={hosts_qty}'" \
              " -var='maas_api_url=http://ob76-node0.maas:5240/MAAS'")
    if rc > 0: die("could not run terraform apply") 
    maas_hosts = json.loads(
        exec_capture("terraform -chdir=terraform/maas output -no-color -json maas_hosts"))
    debug(f"captured 'maas_hosts' terraform output: {maas_hosts}")

    nodes = []
    nodes_roles = dict(zip(maas_hosts, input_config["roles"]))
    for node in maas_hosts:
        newnode = {}
        newnode["host-int"] = node
        newnode["host-ext"] = node
        newnode["roles"] = nodes_roles[node].split(",")
        nodes.append(newnode)
        preseed["microceph_config"][node] = {}
        preseed["microceph_config"][node]["osd_devices"] = "/dev/sdb"

    output_config = {}
    output_config["nodes"] = nodes
    output_config["user"] = "ubuntu"
    output_config["channel"] = input_config["channel"]
    output_config["preseed"] = preseed

    write_config(output_config)


# we expect a JSON config in a environment variable from jenkins
# also have a default to ease manual testing
input_config_json = os.environ.get("JENKINS_JSON_CONFIG")
if not input_config_json:
    debug("JENKINS_JSON_CONFIG was not set, loading defaults")
    input_config_json = get_input_config_json_defaults()
input_config = json.loads(input_config_json)
debug(f"input_config set to {input_config}")

if input_config["substrate"] == "ob76":
    substrate_ob76(input_config)
elif input_config["substrate"] == "equinix":
    pass
else:
    die("substrate {} not valid, aborting".format(input_config["substrate"]))
