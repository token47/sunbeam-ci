#!/usr/bin/python3 -u

import utils
from sshclient import SSHClient


utils.debug("started testing")

config = utils.read_config()
user = config["user"]

# Target different hosts depending on the substrate
substrate = config["substrate"]
if substrate in ("equinix", "maas"):
    # we actually only need the first control node
    nodes = list(filter(lambda x: 'control' in x["roles"], config["nodes"]))
    primary_node = nodes.pop(0)
    target_host = primary_node["host-ip-ext"]
elif substrate == "maasdeployment":
    target_host = config["sunbeam_client"]
else:
    utils.die(f"Invalid substrate '{substrate}' in config, aborting")

sshclient = SSHClient(user, target_host)

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

# Just enabling observability, not specific tests executed
cmd = """set -xe
    sunbeam enable observability
"""
out, rc = sshclient.execute(
    cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
if rc > 0:
    utils.debug("TEST FAIL: observability plugin enable failed")
    tests_failed = True

# this is a tempest test using the embedded validation plugin in sunbeam
# "quick" ≃ 24 tests, "reftest" ≃ 150 tests, "smoke" ≃ 184 tests, "all" = all tests
cmd = """set -xe
    sunbeam enable validation
    sunbeam validation profiles
    sunbeam validation run quick
    sunbeam validation get-last-result --output ~/plugin-validation.log
"""
out, rc = sshclient.execute(
    cmd, verbose=True, get_pty=True, combine_stderr=True, filtered=True)
if rc > 0:
    # This is relative to running the command itself, not to the tests results
    # You should have a successful run even with failed tests
    # TODO: parse failed tests output and use that as another failure condition
    # NOTE: Some backends do not have the gateway in place to actually pass traffic
    # to the VMs so some tests can be false negative
    utils.debug("TEST FAIL: validation plugin enable or run failed")
    tests_failed = True

# End of tests
sshclient.close()

if tests_failed:
    utils.die("At least one test failed, exiting with error")
