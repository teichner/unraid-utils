#!/usr/bin/env python3
import os.path
import time
import re
import subprocess
from dataclasses import dataclass

# TODO: Move to config file
main_block_name = "hdc"
snapshot_base = "/mnt/user/domains"
backup_date_format = "%Y-%m-%d_%H:%M:%S"

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

blocklist_pattern = re.compile(r" *(?P<block>[A-Za-z]+) +(?P<path>.+)")

# NOTE: This should be called before a snapshot is created.
def main_block_path(domain_name):
    cmd = ['virsh', 'domblklist', domain_name]
    lines = subprocess \
        .run(cmd, capture_output=True, text=True) \
        .stdout \
        .split('\n')[2:]
    for line in lines:
        m = blocklist_pattern.fullmatch(line)
        if m and m.group('block') == main_block_name:
            return m.group('path')
    raise RuntimeError(f"Could not find the path " + \
            "for block {main_block_name} on domain {domain_name}")

def domain_entry(id, name):
    return Domain(id=id, name=name, path=main_block_path(name))
