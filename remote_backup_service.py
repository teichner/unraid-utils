#!/usr/bin/env python3
import os.path
import subprocess
import shlex
import re
from abc import ABC, abstractmethod
from contextlib import contextmanager
import tempfile

gigabyte = 2 ** 30
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
    def __init__(self, runner, ip, remote_base, local_base, ssh_key_file, remote_user):
        self.runner = runner
        self.ip = ip
        self.remote_base = remote_base
        self.local_base = local_base
        self.ssh_key_file = ssh_key_file
        self.remote_user = remote_user

    def rsync_cmd(self, path, options=[]):
        return [
            'rsync',
            *options,
            '-e', f"ssh -i {shlex.quote(self.ssh_key_file)}",
            os.path.join(self.local_base, path),
            f"{self.remote_user}@{self.ip}:{self.remote_base}/"
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
    def __init__(self, runner, cifs_user, cifs_password, cifs_volume, local_base, **rsync_options):
        self.runner = runner
        self.rsync_storage = RsyncStorage(runner, local_base=local_base, **rsync_options)
        self.local_base = local_base
        self.cifs_user = cifs_user
        self.cifs_password = cifs_password
        self.cifs_volume = cifs_volume

        self.mount = self.mount_cifs_storage()

    def mount_cifs_storage(self):
        remote_mount = tempfile.mkdtemp(prefix='cifs-backup')
        cmd = [
            'mount',
            '-t', 'cifs',
            '-o', f"username={self.cifs_user},password={self.cifs_password}",
            self.cifs_volume,
            remote_mount
        ]
        subprocess.run(cmd)
        return remote_mount

    def updated_paths(self, path):
        return self.rsync_storage.updated_paths(path)

    def backup_path(self, path):
        for updated in self.updated_paths(path):
            local_path = os.path.join(self.local_base, updated)
            if os.path.getsize(local_path) > gigabyte:
                remote_path = os.path.join(self.mount, updated)
                self.runner.copy(local_path, remote_path)
        self.rsync_storage.backup_path(path)

    def close(self):
        if os.path.exists(self.mount):
            cmd = ['umount', self.mount]
            subprocess.run(cmd)
            os.rmdir(self.mount)
        self.rsync_storage.close()

class RemoteBackupService:
    def __init__(self, runner):
        self.runner = runner

    @contextmanager
    def storage(self, storageType, **options):
        try:
            storage = storageType(self.runner, **options)
            yield storage
        finally:
            storage.close()
