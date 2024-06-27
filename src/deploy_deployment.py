#!/usr/bin/python3 -u

"""
This script deploys sunbeam on a previously prepared maas substrate, using
'deployments' feature where sunbeam drives maas directly.
"""

import utils
from sshclient import SSHClient


config = utils.read_config()
user = config["user"]
sunbeam_client = config["sunbeam_client"]
channel = config["channel"]
channelcp = config.get("channelcp", "")
deployment_name = config["deployment_name"]
api_url = config["api_url"]
api_key = config["api_key"]
resource_pool = config["resource_pool"]
spaces_mapping = config["spaces_mapping"]
manifest = config["manifest"]

utils.debug(f"starting MAAS Deployment, using sunbeam-client at {sunbeam_client}")

p_sshclient = SSHClient(user, sunbeam_client)

cmd = f"sudo snap install openstack --channel {channel}"
out, rc = p_sshclient.execute(
    cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
utils.debug(f"execute return code is {rc}")
if rc > 0:
    utils.die("installing openstack snap failed, aborting")

cmd = "sunbeam prepare-node-script --client | bash -x"
out, rc = p_sshclient.execute(
    cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
utils.debug(f"execute return code is {rc}")
if rc > 0:
    utils.die("running prepare-node-script failed, aborting")

# register deployment itself
cmd = f"""
    sunbeam deployment add maas \
        --name {deployment_name} \
        --url {api_url} \
        --token {api_key} \
        --resource-pool {resource_pool}
"""
out, rc = p_sshclient.execute(
    cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
utils.debug(f"execute return code is {rc}")
if rc > 0:
    utils.die("running prepare-node-script failed, aborting")

# map spaces
for network, space in spaces_mapping.items():
    cmd = f"sunbeam deployment space map {space} {network}"
    out, rc = p_sshclient.execute(
        cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
    utils.debug(f"execute return code is {rc}")
    if rc > 0:
        utils.die(f"mapping network '{network}' to space '{space}' failed, aborting")

# validate the deployment before starting
# this will not block or prevent deployment, it will just generate a report
# at /home/ubuntu/snap/openstack/common/reports/validate-deployment-*.yaml
cmd = "sunbeam deployment validate"
out, rc = p_sshclient.execute(
    cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=False)
utils.debug(f"execute return code is {rc}")
# this is about failure of running the command, not about the result of the validation
if rc > 0:
    utils.die("validating the deployment failed, aborting")

# The snap carries a few manifest override files that you can use
# to force candidate, edge, etc for the control plane (default is
# stable channel for CP even for non-stable openstack snaps)
snap_manifest_file = f"/snap/openstack/current/etc/manifests/{channelcp}.yml"
if channelcp == "stable":
    # for stable, we just do nothing, it's the default
    utils.debug("deploying control plane with 'stable' channels, no snap manifest needed")
elif channelcp in ("candidate", "edge"):
    # for others we merge default manifest from snap with ours
    utils.debug(f"deploying control plane with {channelcp} channels, loading snap manifest")
    manifest_temp = utils.yaml_safe_load(p_sshclient.file_read(snap_manifest_file))
    # Get a merged manifest using the snap one for defaults
    manifest = utils.merge_dicts(manifest_temp, manifest)
else:
    utils.die("Missing or invalid 'channelcp' value")

manifest_dump = utils.yaml_dump(manifest)
utils.debug(f"Manifest contents are:\n{manifest_dump.rstrip()}")
p_sshclient.file_write("manifest.yaml", manifest_dump)

cmd = "sunbeam cluster bootstrap -m ~/manifest.yaml"
out, rc = p_sshclient.execute(
    cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
utils.debug(f"execute return code is {rc}")
# hack for websocket error
if rc == 1001:
    utils.debug("Retrying because of websocker error")
    out, rc = p_sshclient.execute(
        cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
    utils.debug(f"execute return code is {rc}")
if rc > 0:
    utils.die("bootstrapping sunbeam failed, aborting")

#cmd = "sunbeam cluster list"
#out, rc = p_sshclient.execute(
#    cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
#utils.debug(f"execute return code is {rc}")
#if rc > 0:
#    utils.die("listing sunbeam cluster nodes failed, aborting")

cmd = "sunbeam cluster deploy"
out, rc = p_sshclient.execute(
    cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
utils.debug(f"execute return code is {rc}")
if rc > 0:
    utils.die("running cluster deploy failed, aborting")

cmd = "sunbeam configure --openrc ~/demo-openrc && echo >> ~/demo-openrc"
out, rc = p_sshclient.execute(
    cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
utils.debug(f"execute return code is {rc}")
if rc > 0:
    utils.die("configuring demo project failed, aborting")

cmd = "sunbeam openrc > ~/admin-openrc"
out, rc = p_sshclient.execute(
    cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
utils.debug(f"execute return code is {rc}")
if rc > 0:
    utils.die("exporting admin credentials failed, aborting")

p_sshclient.close()
