#!/bin/false

import base64
import json
import mergedeep
import subprocess
import sys
import time
import yaml


def debug(msg):
    """Print debug messages on stdout"""
    print(f"DEBUG: {msg}")


def die(msg):
    """Kills program execution and exit with error"""
    debug(f"DIE: {msg}")
    sys.exit(1)


def exec_cmd(cmd):
    """Exec code locally using shell"""
    debug(f"EXEC: {cmd}")
    result = subprocess.run(f"set -x; {cmd}", shell=True, check=False)
    return result.returncode


def exec_cmd_capture(cmd):
    """Execute a shell command and grab the output"""
    debug(f"EXEC-CAPTURE: {cmd}")
    result = subprocess.run(cmd, shell=True, check=False,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout.decode()


def hostname_generator(prefix, start, domain): 
    octets = prefix.split(".")
    # if start is None, use last octet as first
    num = start if start else octets[3]
    while True:
        yield {
            "fqdn": f"sunbeam{num}.{domain}",
            "ip": f"{octets[0]}.{octets[1]}.{octets[2]}.{num}", }
        num += 1


def sleep(seconds):
    time.sleep(seconds)


def b64encode(plain_string):
    return base64.b64encode(plain_string)


def b64decode(coded_string):
    return base64.b64decode(coded_string)


def read_file(filename, encoding='utf-8'):
    with open(filename, "r", encoding=encoding) as fd:
        return fd.read()


def read_file_lines(filename, encoding='utf-8'):
    with open(filename, "r", encoding=encoding) as fd:
        return fd.readlines()


def read_profiles():
    return yaml.safe_load(read_file("profiles.yaml"))


def read_config():
    return yaml.safe_load(read_file("config.yaml"))


def write_config(config):
    debug(f"config to be written:\n{config}")
    write_file(yaml.dump(config), "config.yaml")


def write_file(content, filename, encoding='utf-8'):
    debug(f"writing file {filename}")
    with open(filename, "w", encoding=encoding) as fd:
        fd.write(content)


def yaml_safe_load(yamlinput):
    return yaml.safe_load(yamlinput)


def yaml_dump(stringinput):
    return yaml.dump(stringinput)


def json_loads(jsoninput):
    return json.loads(jsoninput)


def json_dumps(dictinput):
    return json.dumps(dictinput)


def merge_dicts(dict1, dict2):
    return mergedeep.merge({}, dict1, dict2, strategy=mergedeep.Strategy.ADDITIVE)
