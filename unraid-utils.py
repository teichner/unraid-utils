#!/usr/bin/env python3

from argparse import ArgumentParser
from domain_backup_service import DomainBackupService
from domain import domain_entry
from runner import Runner, DryRunner

domains = [
    domain_entry(id='ubuntu', name='Ubuntu'),
    domain_entry(id='windows', name='Windows 10-2')
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

    args = parser.parse_args()
    runner = DryRunner() if args.dry_run else Runner()
    if args.command == 'backup-vms':
        service = DomainBackupService(runner)
        for domain in domains:
            service.backup_domain(domain)

if __name__ == "__main__":
    main()
