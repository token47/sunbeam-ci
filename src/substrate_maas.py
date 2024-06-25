#!/bin/false

import os
import utils


def execute(jenkins_config, jenkins_creds, profile_data, action):
    # use env so that sensitive info does not show in debug log
    os.environ["TF_VAR_maas_api_url"] = profile_data["api_url"]
    os.environ["TF_VAR_maas_api_key"] = jenkins_creds["api_key"]

    if action == "build":
        build(jenkins_config, jenkins_creds, profile_data)
        utils.sleep(profile_data["sleep_after"])
    elif action == "destroy":
        destroy(jenkins_config, jenkins_creds, profile_data)
    else:
        utils.die("Invalid action parameter")


def build(jenkins_config, jenkins_creds, profile):

    manifest = profile["manifest"]

    hosts_qty = len(jenkins_config["roles"])
    utils.debug(f"allocating {hosts_qty} hosts in maas")

    rc = utils.exec_cmd("terraform -chdir=terraform/maas init -no-color")
    if rc > 0:
        utils.die("could not run terraform init")

    rc = utils.exec_cmd("terraform -chdir=terraform/maas apply -auto-approve -no-color" \
                  f" -var='maas_hosts_qty={hosts_qty}'")
    if rc > 0:
        utils.die("could not run terraform apply")

    rc = utils.exec_cmd("terraform -chdir=terraform/maas show -no-color")
    if rc > 0:
        utils.die("could not run terraform show")

    maas_hosts = utils.json_loads(
        utils.exec_cmd_capture("terraform -chdir=terraform/maas output -no-color -json maas_hosts"))
    utils.debug(f"captured 'maas_hosts' terraform output: {maas_hosts}")

    nodes = []
    nodes_roles = dict(zip(maas_hosts.keys(), jenkins_config["roles"]))
    for nodename, ipaddress in maas_hosts.items():
        nodes.append({
            "host-name-ext": nodename,
            "host-name-int": nodename,
            "host-ip-ext": ipaddress[0], # remember maas terraform provider returns a LIST of ips
            "host-ip-int": ipaddress[0], # let's take the first one now, TODO: find the OAM one
            "roles": nodes_roles[nodename].split(","),
        })
        manifest["deployment"]["microceph_config"][nodename] = \
            { "osd_devices": "/dev/sdb" }

    output_config = {}
    output_config["nodes"] = nodes
    output_config["user"] = "ubuntu"
    output_config["channel"] = jenkins_config["channel"]
    output_config["channelcp"] = jenkins_config["channelcp"]
    output_config["manifest"] = manifest

    utils.write_config(output_config)


def destroy(jenkins_config, jenkins_creds, profile_data):
    hosts_qty = len(jenkins_config["roles"])
    rc = utils.exec_cmd("terraform -chdir=terraform/maas destroy -auto-approve -no-color" \
                        f" -var='maas_hosts_qty={hosts_qty}'")
    if rc > 0:
        utils.die("could not run terraform destroy")
