#!/usr/bin/python3 -u

import json
import os
import substrate_equinix
import substrate_maas
import sys
import utils


# first parameter must be the action (i.e. 'build', 'destroy', ...)
if len(sys.argv) < 2: # ($0 + $1)
    utils.die("You need to pass the action as first parameter")
action = sys.argv[1]

# we expect a JSON config in a environment variable from jenkins
if not (jenkins_config_json := os.environ.get("JENKINS_JSON_CONFIG")):
    utils.die("JENKINS_JSON_CONFIG not set, aborting")

# and another variable with credentials
if not (jenkins_creds_json := os.environ.get("JENKINS_JSON_CREDS")):
    utils.die("JENKINS_JSON_CREDS not set, aborting")

# we don't catch errors here because we want it to break and stop
jenkins_config = json.loads(jenkins_config_json)
jenkins_creds = json.loads(jenkins_creds_json)

# now load the profile
profiles = utils.read_profiles()
profile_name = jenkins_config["profile"]
profile_data = profiles.get(profile_name, None)
if not profile_data:
    utils.die("Invalid profile, please check Jenkins config and/or profiles.yaml")

utils.debug(f"input_config (from Jenkins) set to {jenkins_config}")
utils.debug(f"profile set to {profile_name} = {profile_data}")

substrate = profile_data["substrate"]
utils.debug(f"Starting substrate {substrate}, with action '{action}' for profile {profile_name}")
if substrate == "equinix":
    substrate_equinix.execute(jenkins_config, jenkins_creds, profile_data, action)
elif substrate == "maas":
    substrate_maas.execute(jenkins_config, jenkins_creds, profile_data, action)
else:
    utils.die(f"Invalid substrate '{substrate}' used in profile '{profile_name}', aborting")
