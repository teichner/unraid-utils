#!/usr/bin/env python3
import os.path
import subprocess
import shlex
import re
from abc import ABC, abstractmethod
from contextlib import contextmanager
import tempfile

gigabyte = 2 ** 30

server = "10.10.0.252"
remote_base = "/volume1/NetBackup"
remote_volume = "//Synology/NetBackup"
local_base = "/mnt/user"
key_file = "/boot/config/sshroot/Tower-rsync-key"
remote_credentials_file = "/boot/config/custom/synology_credentials"

with open(remote_credentials_file, 'r') as f:
    user, password = f.read().strip().split(':')

rsync_updated_file_pattern = re.compile(r'^<f[^ ]+ +(?P<path>.*)$')

class Storage(ABC):
    @abstractmethod
    def updated_paths(self, directory):
        ...

    @abstractmethod
    def backup_path(self, path):
        ...

    @abstractmethod
    def close(self):
        ...

class RsyncStorage(Storage):
    def __init__(self, runner):
        self.runner = runner

    def rsync_cmd(self, path, options=[]):
        return [
            'rsync',
            *options,
            '-e', f"ssh -i {shlex.quote(key_file)}",
            os.path.join(local_base, path),
            f"{user}@{server}:{remote_base}/"
        ]

    def updated_paths(self, directory):
        cmd = self.rsync_cmd(directory, options=['--dry-run', '-iavu'])
        pipe = subprocess \
            .Popen(cmd, stdout=subprocess.PIPE, text=True) \
            .stdout
        for line in pipe:
            m = rsync_updated_file_pattern.fullmatch(line.strip())
            if m:
                yield m.group('path')

    def backup_path(self, path):
        cmd = self.rsync_cmd(path, options=[
            '-rlptDvu',
            '--numeric-ids',
            '--progress'
        ])
        self.runner.run(cmd)

    def close(self):
        pass

class CIFSOverRsyncStorage(Storage):
    def __init__(self, runner, mount, rsyncStorage):
        self.runner = runner
        self.mount = mount
        self.rsyncStorage = rsyncStorage

    def updated_paths(self, path):
        return self.rsyncStorage.updated_paths(path)

    def backup_path(self, path):
        for updated in self.updated_paths(path):
            local_path = os.path.join(local_base, updated)
            if os.path.getsize(local_path) > gigabyte:
                remote_path = os.path.join(self.mount, updated)
                self.runner.copy(local_path, remote_path)
        self.rsyncStorage.backup_path(path)

    def close(self):
        if os.path.exists(self.mount):
            cmd = ['umount', self.mount]
            subprocess.run(cmd)
            os.rmdir(self.mount)
        self.rsyncStorage.close()

class RemoteBackupService:
    def __init__(self, runner):
        self.runner = runner

    def mount_cifs_storage(self):
        remote_mount = tempfile.mkdtemp(prefix='backup')
        cmd = [
            'mount', '-t', 'cifs',
            '-o', f"username={user},password={password}",
            remote_volume,
            remote_mount
        ]
        subprocess.run(cmd)
        return remote_mount

    @contextmanager
    def cifs_over_rsync_storage(self):
        try:
            remote_mount = self.mount_cifs_storage()
            storage = CIFSOverRsyncStorage(
                runner=self.runner,
                mount=remote_mount,
                rsyncStorage=RsyncStorage(
                    runner=self.runner))
            yield storage
        finally:
            storage.close()
