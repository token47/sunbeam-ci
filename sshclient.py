
import fnmatch
import os
import paramiko
#import re
import time
import utils

KEY_FILES = [
    (paramiko.RSAKey, "rsa"),
    (paramiko.DSSKey, "dsa"),
    (paramiko.ECDSAKey, "ecdsa"),
    (paramiko.Ed25519Key, "ed25519"),
]

class SSHClient:

    def __init__(self, user, host):
        self.user = user
        self.host = host
        self.transport = None
        self.ssh_agent = paramiko.Agent()
        self.sftp_channel = None


    def __is_connected(self):
        if self.transport:
            # this is better than 'is_active()' because it tests both
            return self.transport.is_authenticated()
        else:
            return False


    def __connect(self):
        if self.__is_connected():
            return

        utils.debug(f"Starting SSH connection to {self.user}@{self.host}")
        self.transport = paramiko.Transport((self.host, 22))
        self.transport.start_client()
        # try keys from ssh_agent and from files (if unencrypted)
        for key in self.ssh_agent.get_keys():
            # in case the key does not succeed authenticating
            try:
                self.transport.auth_publickey(self.user, key)
            except paramiko.AuthenticationException:
                pass
            if self.transport.is_authenticated():
                break
        else:
            for keytype, name in KEY_FILES:
                if os.path.isfile(path := os.path.expanduser(f"~/.ssh/id_{name}")):
                    # in case the key file is passphrase protected
                    try:
                        key = keytype.from_private_key_file(path)
                    except paramiko.PasswordRequiredException:
                        pass
                    # in case the key does not succeed authenticating
                    try:
                        self.transport.auth_publickey(self.user, key)
                    except paramiko.AuthenticationException:
                        pass
                    if self.transport.is_authenticated():
                        break
        
        if not self.transport.is_authenticated():
            utils.die("Could not find a suitable ssh key to authenticate")

        # start a new long standing sftp channel
        self.sftp_channel = paramiko.SFTPClient.from_transport(self.transport)


    def close(self):
        utils.debug(f"Closing SSH connection to {self.user}@{self.host}")
        self.transport.close()


    def server_available(self):
        start_time = time.time()
        while True:
            utils.debug(f"Testing ssh connection to host {self.host}")
            self.__connect()
            if self.__is_connected():
                utils.debug("SSH connection is working, continuing")
                return True
            if time.time() - start_time > 60:
                utils.debug("Timed out waiting on ssh server, giving up")
                return False
            utils.debug("SSH connection not working, retrying shortly")
            time.sleep(5)


    def execute(
        self,
        cmd,
        verbose=False,
        get_pty=False,
        combine_stderr=False,
        filtered=False # ignored for now
    ):
        self.__connect()
        utils.debug(f"SSH-EXECUTE: starting new execute at host {self.host}:\n{cmd}")
        # different from sftp, exec needs a new channel every time
        channel = self.transport.open_channel("session")
        if get_pty:
            channel.get_pty(term="xterm-256color")
        channel.set_combine_stderr(combine_stderr)
        channel.exec_command(cmd)

        stdout = channel.makefile("r", 1)
        stderr = channel.makefile_stderr("r", 1)
        stdout_buffer = ""
        stderr_buffer = ""
        # hacks to detect websocket error and retry and to join separate lines that repeat as a pair
        # unfortunately these are easier to do here and not in a function because it is too much
        # context to pass out and in again (and hopefully they are temporary)
        websocket_error = False
        websocket_message = "Error: Unable to connect to websocket"
        #delayed_line = None
        #last_line = ""
        #detect_two_lines = re.compile(
        #    r"> Deploying OpenStack Control Plane to Kubernetes \(this may take a while\) \.\.\.|"
        #    r"> Resizing OpenStack Control Plane to match appropriate topology \.\.\.|"
        #    r"> No sunbeam key found in OpenStack\. Creating SSH key at")
        # hack b/c of paramiko weirdness (detecting rc before all data sent)
        # this is a potential race condition but best solution so far
        can_exit = False
        while not can_exit:
            if (stderr_r := stderr.readline()):
                stderr_buffer += stderr_r if not filtered else utils.strip_garbage(stderr_r)
                if verbose:
                    print(stderr_r, end="")
            if (stdout_r := stdout.readline()):
                stdout_buffer += stdout_r if not filtered else utils.strip_garbage(stdout_r)
                if verbose:
                    print(stdout_r, end="")
            if not stdout_r and not stderr_r:
                if channel.exit_status_ready():
                    can_exit = True
                time.sleep(0.001) # some releaf to polling
            if websocket_message in stderr_r or websocket_message in stdout_r:
                websocket_error = True

        rc = channel.recv_exit_status()

        if rc > 0 and websocket_error:
            rc = 1001

        return stdout_buffer, stderr_buffer, rc

    #    if delayed_line:
    #        line = f"{delayed} {line}"
    #        delayed = None
    #    elif detect_two_lines.search(line):
    #        delayed_line = line
    #        continue
    #    if line != last_line:
    #        print(f"{line}")
    #        last_line = line


    def file_put(self, localpath, remotepath):
        self.__connect()
        utils.debug(f"SSH-FILE-PUT: uploading local path '{localpath}' to remote path '{remotepath}'")
        self.sftp_channel.put(localpath, remotepath)


    def file_get(self, remotepath, localpath):
        """both remote and local paths need to be exact files (no globs, not any other epansions)"""
        self.__connect()
        utils.debug(f"SSH-FILE-GET: downloading remote path '{remotepath}' to local path '{localpath}'")
        self.sftp_channel.get(remotepath, localpath)


    def file_get_glob(self, remotepath, pattern, localpath):
        """remotepath must be dir/, pattern is a glob, destination must be dir/ (ending in slash)"""
        self.__connect()
        utils.debug(f"SSH-FILE-GET-GLOB: downloading remote path '{remotepath}' "
            f"glob: '{pattern}', to local dir '{localpath}'")
        for remotefile in self.sftp_channel.listdir(remotepath):
            print(remotefile)
            if fnmatch.fnmatch(remotefile, pattern):
                self.file_get(f"{remotepath}{remotefile}", f"{localpath}{remotefile}")


    def file_read(self, remotepath):
        self.__connect()
        utils.debug(f"SSH-FILE-READ: reading remote path '{self.host}:{remotepath}'")
        fd = self.sftp_channel.open(remotepath, mode='r')
        return fd.read()


    def file_write(self, remotepath, contents):
        self.__connect()
        utils.debug(f"SSH-FILE-WRITE: writing remote path '{self.host}:{remotepath}'")
        fd = self.sftp_channel.open(remotepath, mode='w')
        fd.write(contents)
