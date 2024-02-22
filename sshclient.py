
import fnmatch
import os
import paramiko
import re
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

        # grab a new transport layer that will last for this connection
        # it can be re-used but that was unstable last time I tried
        self.transport = paramiko.Transport((self.host, 22))
        
        # just make sure last used transport is closed and thread released
        self.transport.close()

        # actually try to connect (and retry a few times before giving up)
        for t in range(1,11):
            try:
                self.transport.start_client()
                break
            except paramiko.SSHException:
                utils.debug(f"SSH Connection failed (#{t}), retrying")
                time.sleep(5)
        else:
            utils.die("SSH connection failed too many times, aborting")

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


    def close(self):
        utils.debug(f"Closing SSH connection to {self.user}@{self.host}")
        self.transport.close()


    def execute(self, cmd, verbose=False, get_pty=False, combine_stderr=False, filtered=False):

        def strip_garbage(line):
            # ANSI Codes, spaces at the end
            line = re.sub(r"\x1b\[\??[0-9;]*[hlmAGKHF]| *$", '', line)
            # The spinning wheel at the status lines
            line = re.sub("[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏] *", '> ', line)
            # Apt "Reading database" verboseness
            if r"(Reading database ..." in line:
                line = ""
            return line

        def maybe_filter_and_print(lineraw, verbose, filtered):
            nonlocal last_line, delayed_line
            # TODO: move this out of the function so it does not get compiled every time
            detect_two_lines = re.compile(
                r"> Deploying OpenStack Control Plane to Kubernetes \(this may take a while\)|"
                r"> Resizing OpenStack Control Plane to match appropriate topology|"
                r"> No sunbeam key found in OpenStack\. Creating SSH key at")

            if not filtered:
                if verbose:
                    print(lineraw)
                return lineraw

            # we may have received lots of lines with \r separator in one raw line
            # output may be delayed until a \n comes, but then all lines are shown
            lines_buffer = ""
            for line in lineraw.rstrip().split("\r"):
                line = strip_garbage(line)
                # some lines get empty after removing all garbage
                # this ends up removing originally empty lines too
                if not line:
                    continue
                if delayed_line:
                    line = f"{delayed_line} {line}"
                    delayed_line = None
                elif detect_two_lines.search(line):
                    delayed_line = line
                    continue
                if line != last_line:
                    if verbose:
                        print(line)
                    last_line = line
                lines_buffer += f"{line}\n"
            return lines_buffer

        self.__connect()
        utils.debug(f"SSH-EXECUTE: starting new execute at host {self.host}:")
        if not verbose:
            utils.debug(f"Commands:\n{cmd}")
        # different from sftp, exec needs a new channel every time
        channel = self.transport.open_channel("session")
        if get_pty:
            channel.get_pty(term="xterm-256color")
        channel.set_combine_stderr(combine_stderr)
        channel.exec_command(cmd)

        stdout = channel.makefile("r", 1)
        stdout_buffer = ""
        # hacks to detect websocket error and retry
        websocket_error = False
        websocket_message = "Error: Unable to connect to websocket"
        last_line = None
        delayed_line = None
        while True:
            stdout_read = ""
            if stdout_read := stdout.readline():
                stdout_buffer += maybe_filter_and_print(stdout_read, verbose, filtered)
            else:
                # empty read means stream closed
                break
            # empty stderr buffer but ignore it as an independent stream
            # the only ways to get stderr is to get a pty or combine it
            if channel.recv_stderr_ready():
                bogus = channel.recv_stderr()  # noqa: F841
            if websocket_message in stdout_read:
                websocket_error = True

        rc = channel.recv_exit_status()

        if rc > 0 and websocket_error:
            rc = 1001

        return stdout_buffer, rc


    def file_put(self, localpath, remotepath):
        self.__connect()
        utils.debug(f"SSH-FILE-PUT: uploading local path '{localpath}' "
            "to remote path '{remotepath}'")
        sftp_channel = paramiko.SFTPClient.from_transport(self.transport)
        sftp_channel.put(localpath, remotepath)
        sftp_channel.close()


    def file_get(self, remotepath, localpath):
        """both remote and local paths need to be exact files (no globs,
           not any other epansions)"""
        self.__connect()
        utils.debug("SSH-FILE-GET: downloading remote path "
            f"'{remotepath}' to local path '{localpath}'")
        sftp_channel = paramiko.SFTPClient.from_transport(self.transport)
        sftp_channel.get(remotepath, localpath)
        sftp_channel.close()


    def file_get_glob(self, remotepath, pattern, localpath):
        """remotepath must be dir/, pattern is a glob, destination must be
           dir/ (ending in slash)"""
        self.__connect()
        utils.debug(f"SSH-FILE-GET-GLOB: downloading remote path '{remotepath}' "
            f"glob: '{pattern}', to local dir '{localpath}'")
        sftp_channel = paramiko.SFTPClient.from_transport(self.transport)
        try:
            list_dir = sftp_channel.listdir(remotepath)
        except FileNotFoundError:
            utils.debug("Error, remote dir does not exist")
            return
        for remotefile in list_dir:
            if fnmatch.fnmatch(remotefile, pattern):
                utils.debug("SSH-FILE-GET-GLOB: downloading remote path "
                    f"'{remotepath}' to local path '{localpath}'")
                sftp_channel.get(f"{remotepath}{remotefile}", f"{localpath}{remotefile}")
        sftp_channel.close()


    def file_read(self, remotepath):
        self.__connect()
        utils.debug(f"SSH-FILE-READ: reading remote path '{self.host}:{remotepath}'")
        sftp_channel = paramiko.SFTPClient.from_transport(self.transport)
        fd = sftp_channel.open(remotepath, mode='r')
        data = fd.read()
        sftp_channel.close()
        return data


    def file_write(self, remotepath, contents):
        self.__connect()
        utils.debug(f"SSH-FILE-WRITE: writing remote path '{self.host}:{remotepath}'")
        sftp_channel = paramiko.SFTPClient.from_transport(self.transport)
        fd = sftp_channel.open(remotepath, mode='w')
        fd.write(contents)
        sftp_channel.close()
