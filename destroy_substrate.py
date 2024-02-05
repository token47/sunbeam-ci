#!/usr/bin/python3 -u

# Clean up substrate

from utils import *


def substrate_ob76(input_config):
    hosts_qty = len(input_config["roles"])
    rc = exec("terraform -chdir=terraform/maas destroy --auto-approve" \
              f" -var='maas_hosts_qty={hosts_qty}'" \
              " -var='maas_api_url=http://ob76-node0.maas:5240/MAAS'")
    if rc > 0: die("could not run terraform destroy") 


input_config_json = os.environ.get("JENKINS_JSON_CONFIG")
input_config = json.loads(input_config_json)
if input_config["substrate"] == "ob76":
    substrate_ob76(input_config)
elif input_config["substrate"] == "equinix":
    pass