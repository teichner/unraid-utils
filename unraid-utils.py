#!/usr/bin/env python3

from argparse import ArgumentParser
from domain_backup_service import DomainBackupService
from remote_backup_service import RemoteBackupService
from domain import domain_entry
from runner import Runner, DryRunner

#TEST
import subprocess

domains = [
    domain_entry(id='ubuntu', name='Ubuntu'),
    domain_entry(id='windows', name='Windows 10-2')
]

backup_shares = [
    'appdatabackup',
    'isos',
    'libvirtbackup',
    'media',
    'misc',
    'office',
    'syncthing',
    'system',
    'usbbackup'
]

def main():
    parser = ArgumentParser(description='Utilities for managing Unraid')
    subparsers = parser.add_subparsers(title='Commands',
                                       required=True,
                                       dest='command')

    parser.add_argument('--dry-run', action='store_true',
                        help='list the steps to be taken instead of performing them')

    vm_backup_parser = subparsers.add_parser('backup-vms',
                                             help='backup select VMs')

    remote_backup_parser = subparsers.add_parser('backup-remote',
                                                 help='backup files to remote location')

    args = parser.parse_args()
    runner = DryRunner() if args.dry_run else Runner()
    if args.command == 'backup-vms':
        service = DomainBackupService(runner)
        for domain in domains:
            service.backup_domain(domain)
    elif args.command == 'backup-remote':
        service = RemoteBackupService(runner)
        with service.storage() as storage:
            for d in backup_shares:
                storage.backup_path(d)
            #subprocess.run('du -h /mnt/backup/media/movies/', shell=True)
        # # TEST
        # with service.cifs_storage():
        #     service.backup_directory('media')

if __name__ == "__main__":
    main()
