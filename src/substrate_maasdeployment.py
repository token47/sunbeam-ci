#!/bin/false

import json
import utils
import os
from sshclient import SSHClient

# This substrate is simpler to deploy than others because it does not deal with
# terraform or any other actual deployment, since sunbeam will talk to maas
# directly later in the deploy script.
#
# TODO:
# - Support HA infra
# - Allow cloud_nodes to have different roles


USER = "ubuntu"  # for ssh'ing into sunbeam-client
tf_cmd = "terraform -chdir=terraform/maas_deployment"
destroy_cmd_options = "--destroy-storage --no-prompt --force --no-wait"


def generate_terraform_cmd(profile_data, action="apply"):
    distro_series = profile_data["distro_series"]
    infra_host = profile_data["infra_host"]
    deployment_name = profile_data["deployment_name"]
    cloud_nodes = json.dumps(
        profile_data["cloud_nodes"], separators=(", ", " = ")
    )
    api_ranges = json.dumps(
        profile_data["api_ranges"], separators=(", ", " = ")
    )
    if action == "apply":
        utils.debug(f"Using {infra_host} as an LXD host in MAAS")
        utils.debug(f"Using {cloud_nodes} for OpenStack cloud")
        utils.debug(f"API ranges: {api_ranges}")
    return (
        f"{tf_cmd} {action} -auto-approve -no-color"
        f" -var='cloud_nodes={cloud_nodes}'"
        f" -var='distro_series={distro_series}'"
        f" -var='infra_host={infra_host}'"
        f" -var='deployment_name={deployment_name}'"
        f" -var='api_ranges={api_ranges}'"
    )


def get_sunbeam_client():
    return utils.exec_cmd_capture(
        f"{tf_cmd} output -no-color -raw sunbeam_client"
    )


def execute(jenkins_config, jenkins_creds, profile_data, action):
    # use env so that sensitive info does not show in debug log
    os.environ["TF_VAR_maas_api_url"] = profile_data["api_url"]
    os.environ["TF_VAR_maas_api_key"] = jenkins_creds["api_key"]
    if action == "build":
        build(jenkins_config, jenkins_creds, profile_data)
        utils.sleep(profile_data["sleep_after"])
    elif action == "destroy":
        destroy(jenkins_config, jenkins_creds, profile_data, action)
    else:
        utils.die("Invalid action parameter")


def build(jenkins_config, jenkins_creds, profile_data):
    rc = utils.exec_cmd(f"{tf_cmd} init -no-color")
    if rc != 0:
        utils.die("could not run terraform init")

    # remove a possible left over install before starting
    utils.debug("Removing any old deployment left over")
    destroy(jenkins_config, jenkins_creds, profile_data, "destroy")

    rc = utils.exec_cmd(generate_terraform_cmd(profile_data, action="apply"))
    if rc != 0:
        utils.die("could not run terraform apply")

    rc = utils.exec_cmd(f"{tf_cmd} show -no-color")
    if rc != 0:
        utils.die("could not run terraform show")

    sunbeam_client = get_sunbeam_client()

    output_config = {}
    output_config["substrate"] = profile_data["substrate"]
    output_config["user"] = USER
    output_config["api_url"] = profile_data["api_url"]
    output_config["api_key"] = jenkins_creds["api_key"]
    output_config["deployment_name"] = profile_data["deployment_name"]
    output_config["sunbeam_client"] = sunbeam_client
    try:
        output_config["default_space"] = profile_data["default_space"]
    except KeyError:
        output_config["spaces_mapping"] = profile_data["spaces_mapping"]
    output_config["channel"] = jenkins_config["channel"]
    output_config["channelcp"] = jenkins_config["channelcp"]
    output_config["manifest"] = profile_data["manifest"]

    utils.write_config(output_config)


def destroy(jenkins_config, jenkins_creds, profile_data, action):
    if profile_data["destroy_after"] or action == "destroy":
        utils.debug("Removing deployment to free up resources")
        remove_current_installation(
            jenkins_config, jenkins_creds, profile_data
        )
        rc = utils.exec_cmd(
            generate_terraform_cmd(profile_data, action="destroy")
        )
        if rc != 0:
            utils.die("could not run terraform destroy")
    else:
        utils.debug("Keeping deployment up so it can be used later")


def remove_current_installation(jenkins_config, jenkins_creds, profile_data):
    sunbeam_client = get_sunbeam_client()
    if sunbeam_client.startswith("\nWarning"):
        return

    sshclient = SSHClient(USER, sunbeam_client)

    deployment_name = profile_data["deployment_name"]

    # FIXME: improve this cleanup, iterate through all models or maybe destroy
    #        controller directly? also find a better way to not fail the whole
    #        script if individual commands fail when we are cleaning an already
    #        cleaned environment (or detect it early and exit)
    cmd = f"""set -xe
        models=$(timeout 5 juju models --format json | jq -r '.models[].name' \
            | grep -v controller || :)
        if [ -n "$models" ]; then
            for model in $models; do
                juju destroy-model {destroy_cmd_options} $model || :
            done
            juju destroy-controller {destroy_cmd_options} \
                --destroy-all-models {deployment_name}-controller || :
        fi
        juju unregister {deployment_name}-controller --no-prompt | :
        sudo snap remove --purge juju || :
        sudo snap remove --purge openstack || :
        rm -rf ~/.local/share/juju
        rm -rf ~/.local/share/openstack
        sudo journalctl --vacuum-size=10M
        """
    out, rc = sshclient.execute(
        cmd, verbose=True, get_pty=False, combine_stderr=True, filtered=False)
    if rc != 0:
        utils.die("cleaning current maas deployment failed, aborting")

    sshclient.close()
