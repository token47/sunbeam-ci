#!/usr/bin/python3 -u

import json
import os
import substrate_equinix
import substrate_ob76
import substrate_tokenlabs
import sys
import utils


# we expect a JSON config in a environment variable from jenkins
if not (config_json := os.environ.get("JENKINS_JSON_CONFIG")):
    utils.die("JENKINS_JSON_CONFIG not set, aborting")

# and another variable with credentials
if not (creds_json := os.environ.get("JENKINS_JSON_CREDS")):
    utils.die("JENKINS_JSON_CREDS not set, aborting")

# we don't catch errors here because we want it to break and stop
config = json.loads(config_json)
creds = json.loads(creds_json)

utils.debug(f"input_config (from Jenkins) set to {config}")

# first parameter must be the action (i.e. 'build', 'destroy', ...)
action = sys.argv[1]

utils.debug(f"Starting '{config['substrate']}' substrate with action '{action}'")
if config["substrate"] == "ob76":
    substrate_ob76.execute(config, creds, action)
elif config["substrate"] == "equinix":
    substrate_equinix.execute(config, creds, action)
elif config["substrate"] == "tokenlabs":
    substrate_tokenlabs.execute(config, creds, action)
else:
    utils.die(f"substrate {config['substrate']} not valid, aborting")
