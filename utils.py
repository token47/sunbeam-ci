#!/bin/false

# pylint: disable=invalid-name

"""
This module contains auxiliary functions for the other modules.
It is supposed to be imported and not executed directly.
"""

import re
import subprocess
import sys
import time


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
    subprocess.run(cmd, shell=True, check=False)


def ssh(user, host, cmd):
    """Run an ssh command using system ssh executable"""
    cmd = f"ssh -o StrictHostKeyChecking=no -tt {user}@{host} 'set -x; {cmd}'"
    debug(f"SSH: {user}@{host}")
    result = subprocess.run(cmd, shell=True, check=False)
    return result.returncode


def ssh_filtered(user, host, cmd):
    """Same as ssh() but tries to suppress repeated lines in output"""
    stripgarbage1 = re.compile(r"\x1b\[\??[0-9;]*[hlmAGKHF]|\r|\n| *$")
    stripgarbage2 = re.compile("[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏] *")
    detecttwolines = re.compile("> Deploying.*Control Plane.*may take a while")
    cmd = f"ssh -o StrictHostKeyChecking=no -tt {user}@{host} 'set -x; {cmd}'"
    debug(f"SSH-FILTERED: {user}@{host}")
    result = subprocess.Popen(cmd, shell=True, encoding="utf-8",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    delayed = None
    lastline = ""
    while len(line := result.stdout.readline()) > 0:
        line = stripgarbage1.sub('', line)
        line = stripgarbage2.sub('> ', line)
        if line:
            if delayed:
                line = f"{delayed} {line}"
                delayed = None
            elif detecttwolines.search(line):
                delayed = line
                continue
            if line != lastline:
                print(f"{line}\r") # \r is needed here, not sure why
                lastline = line
    result.wait()
    return result.returncode


def ssh_capture(user, host, cmd):
    """Run an ssh command and captures the output"""
    cmd = f"ssh -o StrictHostKeyChecking=no {user}@{host} '{cmd}'"
    debug(f"SSH-CAPTURE: {cmd}")
    result = subprocess.run(cmd, shell=True, check=False,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout.decode()


def put(user, host, file, content):
    """Uploads a text file to a remote server via ssh"""
    cmd = f"ssh -o StrictHostKeyChecking=no {user}@{host} 'tee {file}'"
    debug(f"PUT: {user}@{host} {file}")
    result = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE)
    result.stdin.write(content.encode())
    result.stdin.close()
    result.wait()


def test_ssh(user, host):
    """Tests if am ssh connection is available before proceeding, with a timeout"""
    start = time.time()
    while True:
        debug(f"testing ssh connection to host {host}")
        rc = ssh(user, host, "true")
        if rc == 0:
            debug("ssh connection is working, continuing")
            break
        if time.time() - start > 30:
            die("giving up on ssh connection, aborting")
        debug("ssh connection not working, retrying in a few seconds")
        time.sleep(5)
