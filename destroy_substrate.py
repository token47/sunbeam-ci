#!/usr/bin/python3 -u

# pylint: disable=wildcard-import,unused-wildcard-import

"""
Clean up deployed substrate
"""

import json
import os
from utils import *


def substrate_ob76(input_config): # pylint: disable=redefined-outer-name
    """Implements the ob76 substrate destroy"""
    hosts_qty = len(input_config["roles"])
    rc = exec_cmd("terraform -chdir=terraform/maas destroy -auto-approve -no-color" \
                  f" -var='maas_hosts_qty={hosts_qty}'")
    if rc > 0:
        die("could not run terraform destroy")


os.environ['TF_VAR_maas_api_key'] = os.environ.get("JENKINS_API_KEY")
os.environ["TF_VAR_maas_api_url"] = "http://ob76-node0.maas:5240/MAAS"

input_config_json = os.environ.get("JENKINS_JSON_CONFIG")
input_config = json.loads(input_config_json)
if input_config["substrate"] == "ob76":
    substrate_ob76(input_config)
elif input_config["substrate"] == "equinix":
    pass
