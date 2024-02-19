#!/bin/false

import base64
import re
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


def ssh_clean(host):
    """Clear previous entries of hosts in ssh known hosts file"""
    cmd = f"ssh-keygen -f ~/.ssh/known_hosts -R {host}"
    exec_cmd(cmd)


def ssh_master_stop(user, host):
    """Kills the current ssh master so that new master comes up next connection"""
    cmd = f"ssh -o ControlPath=/tmp/ssh-master-%r@%h:%p -O exit '{user}@{host}'"
    exec_cmd(cmd)


def ssh(user, host, cmd):
    """Run an ssh command using system ssh executable"""
    cmd = ("ssh -o StrictHostKeyChecking=no -o ControlMaster=auto "
        "-o ControlPath=/tmp/ssh-master-%r@%h:%p -o ControlPersist=5m -tt "
        f"'{user}@{host}' 'set -x; {cmd}'")
    debug(f"SSH: {user}@{host}")
    result = subprocess.run(cmd, shell=True, check=False)
    return result.returncode


def ssh_filtered(user, host, cmd):
    """Same as ssh() but tries to suppress repeated lines in output"""
    stripgarbage1 = re.compile(r"\x1b\[\??[0-9;]*[hlmAGKHF]|\r|\n| *$")
    stripgarbage2 = re.compile("[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏] *")
    detecttwolines = re.compile(
        r"> Deploying OpenStack Control Plane to Kubernetes \(this may take a while\) \.\.\.|"
        r"> Resizing OpenStack Control Plane to match appropriate topology \.\.\.|"
        r"> No sunbeam key found in OpenStack\. Creating SSH key at")
    cmd = ("ssh -o StrictHostKeyChecking=no -o ControlMaster=auto "
        "-o ControlPath=/tmp/ssh-master-%r@%h:%p -o ControlPersist=5m -tt "
        f"'{user}@{host}' 'set -x; {cmd}'")
    debug(f"SSH-FILTERED: {user}@{host}")
    result = subprocess.Popen(cmd, shell=True, encoding="utf-8",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    delayed = None
    lastline = ""
    websocket_error = False
    while len(line := result.stdout.readline()) > 0:
        line = stripgarbage1.sub('', line)
        line = stripgarbage2.sub('> ', line)
        if r"(Reading database ..." in line: # hack
            line = ""
        if line:
            if delayed:
                line = f"{delayed} {line}"
                delayed = None
            elif detecttwolines.search(line):
                delayed = line
                continue
            if line != lastline:
                print(f"{line}") # \r is needed here if at console
                lastline = line
                if "Error: Unable to connect to websocket" in line: # hack
                    websocket_error = True
    result.wait()
    if result.returncode > 0 and websocket_error:
        return 1001
    return result.returncode


def ssh_capture(user, host, cmd):
    """Run an ssh command and captures the output"""
    cmd = ("ssh -o StrictHostKeyChecking=no -o ControlMaster=auto "
        "-o ControlPath=/tmp/ssh-master-%r@%h:%p -o ControlPersist=5m "
        f"'{user}@{host}' '{cmd}'")
    debug(f"SSH-CAPTURE: {cmd}")
    result = subprocess.run(cmd, shell=True, check=False,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return result.stdout.decode()


def put(user, host, file, content):
    """Uploads a text file to a remote server via ssh"""
    cmd = ("ssh -o StrictHostKeyChecking=no -o ControlMaster=auto "
        "-o ControlPath=/tmp/ssh-master-%r@%h:%p -o ControlPersist=5m "
        f"'{user}@{host}' 'tee {file}'")
    debug(f"PUT: {user}@{host} {file}")
    result = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE)
    result.stdin.write(content.encode())
    result.stdin.close()
    result.wait()


def scp_get(user, host, src, dst):
    """Copies files from remote to local system using scp"""
    cmd = ("scp -o StrictHostKeyChecking=no -o ControlMaster=auto "
        "-o ControlPath=/tmp/ssh-master-%r@%h:%p -o ControlPersist=5m "
        f"'{user}@{host}:{src}' '{dst}'")
    debug(f"SCP-GET: {user}@{host}:{src} {dst}")
    result = subprocess.run(cmd, shell=True, check=False)
    return result.returncode


def test_ssh(user, host):
    """Tests if am ssh connection is available before proceeding, with a timeout"""
    start = time.time()
    while True:
        debug(f"testing ssh connection to host {host}")
        rc = ssh(user, host, "true")
        if rc == 0:
            debug("ssh connection is working, continuing")
            break
        if time.time() - start > 60:
            die("giving up on ssh connection, aborting")
        debug("ssh connection not working, retrying in a few seconds")
        time.sleep(5)


def read_config():
    with open("config.yaml", "r", encoding='ascii') as stream:
        return yaml.safe_load(stream)


def write_config(config):
    """Write a config to config.yaml file"""
    debug(f"writing config:\n{config}")
    with open("config.yaml", "w", encoding='ascii') as fd:
        fd.write(yaml.dump(config))


def write_file(content, filename):
    """Write arbitraty data to a file"""
    debug(f"writing file {filename}")
    with open(filename, "w", encoding='utf-8') as fd:
        fd.write(content)


def hostname_generator(prefix, start, domain): 
    num = start
    while True:
        yield {
            "fqdn": f"sunbeam{num}.{domain}",
            "ip": f"{prefix}{num}", }
        num += 1


def token_extract(text):
    # there are better ways of doing this (i.e. using -f yaml), but you also
    # need to strip garbage from the start of the actual data or you need
    # to redirect output (which is not done with the ssh-capture function)
    # to suppress it, and in the end you need to extract the yaml which
    # ends up being more code than this quick hack. TODO: improve
    match = re.search("Token for the Node [^ ]+: ([^ \\r\\n]+)", text)
    if match is None:
        debug("RE for add host token did not match")
        debug(text)
        die("aborting")
    return match.group(1)


def sleep(seconds):
    time.sleep(seconds)


def b64decode(coded_string):
    return base64.b64decode(coded_string)
