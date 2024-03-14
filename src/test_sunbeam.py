#!/usr/bin/python3 -u

import utils
from sshclient import SSHClient


utils.debug("started testing")

config = utils.read_config()
user = config["user"]
# we actually only need the first control node
nodes = list(filter(lambda x: 'control' in x["roles"], config["nodes"]))
primary_node = nodes.pop(0)

p_host_name_int = primary_node["host-name-int"]
p_host_name_ext = primary_node["host-name-ext"]
p_host_ip_int = primary_node["host-ip-int"]
p_host_ip_ext = primary_node["host-ip-ext"]

sshclient = SSHClient(user, p_host_ip_ext)

tests_failed = False

# this is a basic test, there will be better ones later
# but we keep this one as it is on the documentation
# and the user will likely execute exactly this
cmd = "sunbeam launch ubuntu --name test"
out, rc = sshclient.execute(
    cmd, verbose=True, get_pty=False, combine_stderr=True, filtered=True)
if rc > 0:
    utils.debug("TEST FAIL: creating test vm failed (launch command)")
    tests_failed = True

# this is a tempest test using the embedded validation plugin in sunbeam
# reftest ≃ 150 tests, quick ≃ 24 tests, smoke ≃ 184 tests
cmd = """set -x
    sunbeam enable validation
    sunbeam validation profiles
    sunbeam validation run quick
    sunbeam validation get-last-result --output ~/sunbeam-plugin-validation-smoke.log
"""
out, rc = sshclient.execute(
    cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)

# End of tests
sshclient.close()

if tests_failed:
    utils.die("At least one test failed, exiting with error")
