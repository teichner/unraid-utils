import sys
import os
import os.path
import time
import re
import subprocess
import datetime
from operator import attrgetter
from dataclasses import dataclass
from contextlib import contextmanager
from argparse import ArgumentParser

snapshot_base = "/mnt/user/domains"
backup_base = "/mnt/user/backups"
block_name = "hdc"
backup_date_format = "%Y-%m-%d_%H:%M:%S"
backup_limit = 4 # per domain

@dataclass
class BackupRecord:
    domain: object
    name: str
    time: time.struct_time

class Domain:
    def __init__(self, id, name, path):
        self.id = id
        self.name = name
        self.path = path

    @property
    def snapshot_name(self):
        return f"{self.id}-snapshot"

    @property
    def snapshot_path(self):
        return os.path.join(
            snapshot_base,
            f"{self.snapshot_name}.qcow2")

    def parse_backup_name(self, name):
        id, time_text, ext = name.split('.')
        if id != self.id:
            raise ValueError(f"Given domain id {id} does not match {self.id}")
        if ext != 'qcow2':
            raise ValueError(f"Invalid backup file type: {ext}")
        return BackupRecord(
            domain=self,
            name=name,
            time=time.strptime(time_text, backup_date_format))

    def format_backup_name(self):
        return "{id}.{time}.qcow2".format(
                id=self.id,
                time=time.strftime(backup_date_format))

@dataclass
class FakeCompletedProcess:
    args: list
    returncode: int

class DryRunner():
    def remove(self, path):
        print(f"Removing {path}")

    def run(self, cmd):
        print(' '.join(cmd))
        return FakeCompletedProcess(args=cmd, returncode=0)

class Runner():
    def remove(self, path):
        os.remove(path)

    def run(self, cmd):
        return subprocess.run(cmd)

class DomainBackupService:
    def __init__(self, runner):
        self.runner = runner

    def backup_records(self, domain):
        for name in os.listdir(backup_base):
            try:
                yield domain.parse_backup_name(name)
            except ValueError:
                pass

    def rotate_backups(self, domain):
        records = list(self.backup_records(domain))
        delta = len(records) - backup_limit
        if delta > 0:
            records.sort(key=attrgetter('time'))
            for record in records[:delta]:
                path = os.path.join(backup_base, record.name)
                self.runner.remove(path)

    def take_snapshot(self, domain):
        sys.stderr.write(f"Taking snapshot of {domain.name}\n")
        cmd = [
            'virsh', 'snapshot-create-as',
            '--domain', domain.name,
            domain.snapshot_name,
            '--diskspec', f"{block_name},file={domain.snapshot_path}",
            '--disk-only', '--atomic', '--quiesce'
        ]
        self.runner.run(cmd)

    def commit_snapshot(self, domain):
        sys.stderr.write(f"Committing snapshot of {domain.name}\n")
        commit_cmd = [
            'virsh', 'blockcommit',
            domain.name,
            block_name,
            '--verbose', '--pivot'
        ]
        result = self.runner.run(commit_cmd)
        if result.returncode == 0:
            delete_cmd = [
                'virsh', 'snapshot-delete',
                domain.name,
                domain.snapshot_name,
                '--metadata'
            ]
            self.runner.run(delete_cmd)
            self.runner.remove(domain.snapshot_path)

    @contextmanager
    def captured_domain(self, domain):
        try:
            self.take_snapshot(domain)
            yield domain
        finally:
            self.commit_snapshot(domain)

    def backup_domain(self, domain):
        backup_path = os.path.join(
            backup_base, 
            domain.format_backup_name())
        with self.captured_domain(domain):
            cmd = ['rsync', '-aP', domain.path, backup_path]
            self.runner.run(cmd)
        self.rotate_backups(domain)

blocklist_pattern = re.compile(r" *(?P<block>[A-Za-z]+) +(?P<path>.+)")

# NOTE: This should be called before the snapshot is created.
def block_path(domain_name):
    cmd = ['virsh', 'domblklist', domain_name]
    lines = subprocess \
        .run(cmd, capture_output=True, text=True) \
        .stdout \
        .split('\n')[2:]
    for line in lines:
        m = blocklist_pattern.fullmatch(line)
        if m and m.group('block') == block_name:
            return m.group('path')
    raise RuntimeError(f"Could not find the path " + \
            "for block {block_name} on domain {domain_name}")

def domain_entry(id, name):
    return Domain(id=id, name=name, path=block_path(name))

domains = [
    domain_entry(id='ubuntu', name='Ubuntu'),
    domain_entry(id='windows', name='Windows 10-2')
]

def main():
    parser = ArgumentParser(description='Maintain a rolling backup of listed VMs')
    parser.add_argument('--dry-run', action='store_const',
                        const=True, default=False,
                        help='list the steps to be taken instead of performing them')
    args = parser.parse_args()
    runner = DryRunner() if args.dry_run else Runner()
    service = DomainBackupService(runner)
    for domain in domains:
        service.backup_domain(domain)

if __name__ == "__main__":
    main()
