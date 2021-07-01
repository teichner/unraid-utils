#!/usr/bin/env python3
import sys
import os
import os.path
import shlex
from contextlib import contextmanager
from operator import attrgetter
from domain import main_block_name

class DomainBackupService:
    def __init__(self, runner, base, limit):
        self.runner = runner
        self.base = base
        self.limit = limit

    def backup_records(self, domain):
        for name in os.listdir(self.base):
            try:
                yield domain.parse_backup_name(name)
            except ValueError:
                pass

    def rotate_backups(self, domain):
        records = list(self.backup_records(domain))
        delta = len(records) - self.limit
        if delta > 0:
            records.sort(key=attrgetter('time'))
            for record in records[:delta]:
                path = os.path.join(self.base, record.name)
                self.runner.remove(path)

    def take_snapshot(self, domain):
        sys.stderr.write(f"Taking snapshot of {domain.name}\n")
        snapshot_path = shlex.quote(domain.snapshot_path)
        cmd = [
            'virsh', 'snapshot-create-as',
            '--domain', domain.name,
            domain.snapshot_name,
            '--diskspec', f"{main_block_name},file={snapshot_path}",
            '--disk-only', '--atomic', '--quiesce'
        ]
        self.runner.run(cmd)

    def commit_snapshot(self, domain):
        sys.stderr.write(f"Committing snapshot of {domain.name}\n")
        commit_cmd = [
            'virsh', 'blockcommit',
            domain.name,
            main_block_name,
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
            self.base,
            domain.format_backup_name())
        with self.captured_domain(domain):
            cmd = ['rsync', '-aP', domain.path, backup_path]
            self.runner.run(cmd)
        self.rotate_backups(domain)
