#!/usr/bin/python3

# This script parses the console output and possibly some other sources of information
# to construct a file which contents will be used to set the build description in
# Jenkins (via JenkinsFile currentBuild.setDescription()) or later manually.
# This is separate from collect_artifacts to make it more flexible and less impacted
# by errors in that script.

import argparse
import re
import textwrap
import utils

parser = argparse.ArgumentParser()
# Get these values from outside instead of trying to get them from environment of current
# run so that the script is generic enough for it to be run later retroactively
parser.add_argument("-j", "--job-name", required=True)
parser.add_argument("-b", "--build-number", required=True)
parser.add_argument("-n", "--dry-run", action="store_true")
args = parser.parse_args()

# Construct some paths
BUILD_DIR = f"../../jobs/{args.job_name}/builds/{args.build_number}" # relative to workspace dir
CONSOLE_LOG_FILE = f"{BUILD_DIR}/log" # this is a file with console logs
ARCHIVE_DIR = f"{BUILD_DIR}/archive" # this is a directory that holds artifacts

EXTRA_INFO_RE = [
    [
        'juju-operator-refresh-arch',
        '(?s)Error: Client Error.*refresh arch not valid.*Error configuring cloud'
    ], [
        'ubuntu-image-timeout',
        '(?s)Gateway Timeout.*openstack_images_image_v2'
    ], [
        'microceph-unit-timeout',
        'Timed out while waiting for units microceph/. to be ready'
    ], [
        'hypervisor-unit-timeout',
        'Timed out while waiting for units openstack-hypervisor/. to be ready'
    ], [
        'model-openstack-timeout',
        'Timed out while waiting for model .openstack. to be ready'
    ], [
        'terraform-temporary-overload',
        'The service is currently unable .* temporary overloading or maintenance.'
    ], [
        'microceph-unable-list-disks',
        'Error: Unable to list disks'
    ]
]

#HACKS_RE = [
#    [
#        # TODO: add websocket and ceph hacks
#        'hack-name',
#        'hack-string-to-search-for'
#    ]
#]

utils.debug(f"Creating description for job_name={args.job_name} build_number={args.build_number}")

console_log = utils.read_file(CONSOLE_LOG_FILE) # read whole file as one string

# Get the basic information (snap release, die message, etc.)

groups = re.findall('Download snap "openstack" \((.*)\) from channel "(.*)"', console_log)
groups = re.findall(
    "snap_output='openstack +([^ ]+) +([^ ]+) +([^ ]+) +canonical\*\* +-'",
    console_log)
os_snap_release = groups[0][1] if groups else "n/a"
os_snap_channel = groups[0][2] if groups else "n/a"
groups = re.findall(' DIE: (.*)$', console_log, re.MULTILINE)
die_message = groups[0] if groups else "n/a"

# Try to add some more info on fail reason
for item in EXTRA_INFO_RE:
    if re.search(item[1], console_log):
        extra_info = item[0]
        break
else:
    extra_info = "n/a"

## Try to list all hacks needed, TODO: make them cumulative
#for item in HACKS_RE:
#    if re.search(item[1], console_log):
#        hacks_needed = item[0]
#        break
#else:
#    hacks_needed = "n/a"

rendered_template = textwrap.dedent(f"""\
    openstack_snap: {os_snap_channel} ({os_snap_release})
    die_message: {die_message}
    extra_info: {extra_info}
""")
    #hacks_needed: {hacks_needed}

utils.debug(f"Rendered template: \n{rendered_template.rstrip()}")

# Instead of saving description file in workspace/artifacts and let it be copied to the
# archive, point directly to the archive dir so that this is script is generic enough
# to be executed outside of a build env. THIS MUST COME AFTER archiveArtifacts in JenkinsFile.
if not args.dry_run:
    utils.write_file(rendered_template, f"{ARCHIVE_DIR}/build-description.txt")
