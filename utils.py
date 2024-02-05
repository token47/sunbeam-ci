#!/bin/false

# not to be executed

import subprocess
import sys


def debug(msg):
    print(f"DEBUG: {msg}")


def die(msg):
    debug("DIE: {}".format(msg))
    sys.exit(1)


def exec(cmd):
    debug(f"EXEC: {cmd}")
    result = subprocess.run(f"set -x; {cmd}", shell=True)
    return result.returncode


def exec_capture(cmd):
    debug(f"EXEC-CAPTURE: {cmd}")
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout.decode()


def ssh(user, host, cmd):
    cmd = f"ssh -o StrictHostKeyChecking=no -tt {user}@{host} 'set -x; {cmd}'"
    print(f"DEBUG SSH: {user}@{host}")
    result = subprocess.run(cmd, shell=True)


def ssh_clean(host):
    cmd = f"ssh-keygen -f ~/.ssh/known_hosts -R {host}"
    result = subprocess.run(cmd, shell=True)


def ssh_capture(user, host, cmd):
    cmd = f"ssh -o StrictHostKeyChecking=no {user}@{host} '{cmd}'"
    print(f"DEBUG SSH-CAPTURE: {cmd}")
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout.decode()


def put(user, host, file, content):
    cmd = f"ssh -o StrictHostKeyChecking=no {user}@{host} 'tee {file}'"
    print(f"DEBUG PUT: {user}@{host} {file}")
    result = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE)
    result.stdin.write(content.encode())
    result.stdin.close()
    result.wait()
