#!/bin/false

import os
import utils
import textwrap
from sshclient import SSHClient


def execute(jenkins_config, jenkins_creds, profile_data, action):
    # use env so that sensitive info does not show in debug log
    os.environ["TF_VAR_equinix_project_id"] = jenkins_creds["project_id"]
    os.environ["TF_VAR_equinix_api_key"] = jenkins_creds["api_key"]

    if action == "build":
        build(jenkins_config, jenkins_creds, profile_data)
        utils.sleep(profile_data["sleep_after"])
    elif action == "destroy":
        destroy(jenkins_config, jenkins_creds, profile_data)
    else:
        utils.die("Invalid action parameter")


def build(jenkins_config, jenkins_creds, profile_data):
    manifest = profile_data["manifest"]

    hosts_qty = len(jenkins_config["roles"])
    utils.debug(f"allocating {hosts_qty} hosts in equinix")

    rc = utils.exec_cmd("terraform -chdir=terraform/equinix init -no-color")
    if rc != 0:
        utils.die("could not run terraform init")

    rc = utils.exec_cmd("terraform -chdir=terraform/equinix apply -auto-approve -no-color" \
                  f" -var='equinix_hosts_qty={hosts_qty}'")
    if rc != 0:
        utils.die("could not run terraform apply")

    rc = utils.exec_cmd("terraform -chdir=terraform/equinix show -no-color")
    if rc != 0:
        utils.die("could not run terraform show")

    equinix_vlans = utils.json_loads(
        utils.exec_cmd_capture("terraform -chdir=terraform/equinix output "
                               "-no-color -json equinix_vlans"))
    utils.debug(f"captured 'equinix_vlans' terraform output: {equinix_vlans}")

    equinix_hosts = utils.json_loads(
        utils.exec_cmd_capture("terraform -chdir=terraform/equinix output "
                               "-no-color -json equinix_hosts"))
    utils.debug(f"captured 'equinix_hosts' terraform output: {equinix_hosts}")

    nodes = []
    nodes_roles = dict(zip(equinix_hosts.keys(), jenkins_config["roles"]))
    sunbeam_hostname_generator = utils.hostname_generator(
        prefix="10.0.1.", start=11, domain="mydomain")
    for nodename, ipaddress in equinix_hosts.items():
        s = next(sunbeam_hostname_generator)
        nodes.append({
            "host-name-ext": nodename,
            "host-name-int": s["fqdn"],
            "host-ip-ext": ipaddress,
            "host-ip-int": s["ip"],
            "roles": nodes_roles[nodename].split(","),
        })
        manifest["core"]["config"]["microceph_config"][s["fqdn"]] = \
            { "osd_devices": profile_data["ceph_disks"] }

    output_config = {}
    output_config["substrate"] = profile_data["substrate"]
    output_config["nodes"] = nodes
    output_config["user"] = "ubuntu" # we use root to configre but deployment uses ubuntu
    output_config["channel"] = jenkins_config["channel"]
    output_config["channelcp"] = jenkins_config["channelcp"]
    output_config["manifest"] = manifest

    utils.write_config(output_config)

    # this substrate needs extra steps preparing the OS to be on par with maas substrate
    configure_hosts(output_config, equinix_vlans)


def destroy(jenkins_config, jenkins_creds, profile_data):
    hosts_qty = len(jenkins_config["roles"])
    rc = utils.exec_cmd("terraform -chdir=terraform/equinix destroy -auto-approve -no-color" \
                        f" -var='equinix_hosts_qty={hosts_qty}'")
    if rc != 0:
        utils.die("could not run terraform destroy")


def configure_hosts(output_config, vlans):
    vlan_oam = vlans["oam"]
    vlan_ovn = vlans["ovn"]

    # we need to collect all hostnames first (to use in /etc/hosts), then loop again later
    etc_hosts_snippet = ""
    for node in output_config["nodes"]:
        host_name_int = node["host-name-int"]
        host_ip_int = node["host-ip-int"]
        etc_hosts_snippet += f"{host_ip_int}\t{host_name_int} {host_name_int.split('.')[0]}\n"

    for node in output_config["nodes"]:
        host_name_ext = node["host-name-ext"]
        host_name_int = node["host-name-int"]
        host_ip_ext = node["host-ip-ext"]
        host_ip_int = node["host-ip-int"]

        utils.debug(f"Starting configuration for host '{host_name_ext}'")

        sshclient = SSHClient("root", host_ip_ext)

        cmd = """set -xe
            apt -q update
            DEBIAN_FRONTEND=noninteractive apt -q -o Dpkg::Progress-Fancy=0 \
                -o APT::Color=0 -o Dpkg::Use-Pty=0 -o Dpkg::Options::=--force-confdef \
                -o Dpkg::Options::=--force-confold \
                upgrade -y
            apt install -y bridge-utils
            """
        out, rc = sshclient.execute(
            cmd, verbose=True, get_pty=False, combine_stderr=True, filtered=True)
        if rc != 0:
            utils.die("running apt update/upgrade failed, aborting")

        cmd = textwrap.dedent(f"""\
            set -xe
            echo "
            auto bond0.{vlan_oam}
            iface bond0.{vlan_oam} inet static
                address {host_ip_int}
                netmask 255.255.255.0
                #post-up ip route add 10.0.2.0/24 via 10.0.1.1
            
            auto bond0.{vlan_ovn}
            iface bond0.{vlan_ovn} inet manual

            auto br-ovn
            iface br-ovn inet manual
                bridge_ports bond0.{vlan_ovn}
            " >> /etc/network/interfaces
            echo "\\
            ::1 localhost ip6-localhost ip6-loopback
            ff02::1 ip6-allnodes
            ff02::2 ip6-allrouters
            127.0.0.1   localhost
            #10.0.1.1    sunbeamgw.mydomain sunbeamgw
            {etc_hosts_snippet}
            " > /etc/hosts
            hostnamectl set-hostname {host_name_int}
            systemctl restart networking
            """)
        out, rc = sshclient.execute(
            cmd, verbose=True, get_pty=False, combine_stderr=True, filtered=False)
        if rc != 0:
            utils.die("error updating network configs, aborting")

        cmd = """set -xe
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
        out, rc = sshclient.execute(
            cmd, verbose=True, get_pty=False, combine_stderr=True, filtered=False)
        if rc != 0:
            utils.die("error configuring ubuntu user, aborting")

        sshclient.close()
