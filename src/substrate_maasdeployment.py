#!/bin/false

import utils
from sshclient import SSHClient

# This substrate is simpler to deploy than others because it does not deal with
# terraform or any other actual deployment, since sunbeam will talk to maas
# directly later in the deploy script.
#
# Ideally here we should configure maas itself:
# - preparing an isolated resource-group with only machines for this deployment
# - add tags to machines (juju-controller, compute, control, storage, ...)
# - add tags to disks of the machines (tag:ceph)
# - add tags to nics of the machines (tag:compute)
# - add reserved ranges to spaces
# - any other requisite on maas side
#
# But this is a lot of work and currently I adopted a simpler startegy. The maas
# environment should be manually configured to meet all those criterias. This
# can be done in a way that those machines can still be used for other deployments
# since those tags will not affect other uses. The machines, disks and nics should
# all be already tagged (they can be VMs -- eg. for juju -- sunbeam does not care).
# Also, you need an extra machine for a sunbeam client, from where all installation
# commands will be executed. This machine is necessary so that the client is not
# run inside the jenkins CI itself, and dinamically creating a VM or a LXD container
# somewhere should be ok but unnecessarily complicated since it's easy enough for
# you to just pre-create one and give its name in the profile.
# Note: This machine MUST BE ON at all times. Scripts will just ssh into it without
# trying to turn it on first. It does not need anything special and can be recycled
# at any moment if it's trashed by the scripts, it just need to be on.

USER = "ubuntu" # for ssh'ing into sunbeam-client

def execute(jenkins_config, jenkins_creds, profile_data, action):
    if action == "build":
        build(jenkins_config, jenkins_creds, profile_data)
        utils.sleep(profile_data["sleep_after"])
    elif action == "destroy":
        destroy(jenkins_config, jenkins_creds, profile_data)
    else:
        utils.die("Invalid action parameter")


def build(jenkins_config, jenkins_creds, profile_data):
    output_config = {}
    output_config["substrate"] = profile_data["substrate"]
    output_config["user"] = USER
    output_config["api_url"] = profile_data["api_url"]
    output_config["api_key"] = jenkins_creds["api_key"]
    output_config["deployment_name"] = profile_data["deployment_name"]
    output_config["resource_pool"] = profile_data["resource_pool"]
    output_config["sunbeam_client"] = profile_data["sunbeam_client"]
    output_config["spaces_mapping"] = profile_data["spaces_mapping"]
    output_config["channel"] = jenkins_config["channel"]
    output_config["channelcp"] = jenkins_config["channelcp"]
    output_config["manifest"] = profile_data["manifest"]

    utils.write_config(output_config)

    # remove a possible left over install before starting
    remove_current_installation(jenkins_config, jenkins_creds, profile_data)


def destroy(jenkins_config, jenkins_creds, profile_data):
    if profile_data["destroy_after"]:
        utils.debug("Removing deployment to free up resources")
        remove_current_installation(jenkins_config, jenkins_creds, profile_data)
    else:
        utils.debug("Keeping deployment up so it can be used later")


def remove_current_installation(jenkins_config, jenkins_creds, profile_data):
    sshclient = SSHClient(USER, profile_data["sunbeam_client"])

    # FIXME: improve this cleanup, iterate through all models or maybe destroy controller directly?
    cmd = """set -xe
        juju destroy-model --destroy-storage --no-prompt --force --no-wait openstack && sleep 5
        juju destroy-model --destroy-storage --no-prompt --force --no-wait openstack-machines && sleep 5
        juju destroy-controller --no-prompt --destroy-storage --force  sunbeamci-controller && sleep 5
        sudo snap remove --purge juju
        sudo snap remove --purge openstack
        rm -rf ~/.local/share/juju
        rm -rf ~/.local/share/openstack
        """
    out, rc = sshclient.execute(
        cmd, verbose=True, get_pty=False, combine_stderr=True, filtered=False)
    if rc > 0:
        utils.die("cleaning current maas deployment failed, aborting")
    
    sshclient.close()
