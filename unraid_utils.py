#!/usr/bin/env python3

from argparse import ArgumentParser
from domain_backup_service import DomainBackupService
from remote_backup_service import RemoteBackupService
from domain import domain_entry
from runner import Runner, DryRunner
from configparser import ConfigParser

# server = "10.10.0.252"
# remote_base = "/volume1/NetBackup"
# remote_volume = "//Synology/NetBackup"
# local_base = "/mnt/user"
# key_file = "/boot/config/sshroot/Tower-rsync-key"
# remote_credentials_file = "/boot/config/custom/synology_credentials"

# with open(remote_credentials_file, 'r') as f:
#     user, password = f.read().strip().split(':')

def section_subname(expected_type, name):
    section_type, subname = name.split('.')
    if section_type.lower() != expected_type.lower():
        raise ValueError(f"Not a valid {expected_type} section")
    return subname

def parse_file_backup(config, section):
    backup_name = section_subname('FileBackup', section)
    backup_type = config.get(section, 'type')
    options = {
        'type': backup_type,
        'name': backup_name
    }

    #General Options
    options['ip'] = config.get(section, 'IP')
    options['local_base'] = config.get(section, 'LocalBase')
    options['remote_base'] = config.get(section, 'RemoteBase')
    options['remote_user'] = config.get(section, 'RemoteUser')
    options['ssh_key_file'] = config.get(section, 'SSHKeyFile')

    # CIFS Options
    if backup_type == 'CIFSOverRsync':
        options['cifs_volume'] = config.get(section, 'CIFSVolume')
        credentials_file = config.get(section, 'CIFSCredentialsFile')
        with open(credentials_file, 'r') as f:
            user, password = f.read().strip().split(':')
        options['cifs_user'] = user
        options['cifs_password'] = password

    return options

def parse_file_share(config, section):
    share_name = section_subname('FileShare', section)
    options = {
        'name': share_name,
        'share': config.get(section, 'Share'),
        'backups': config.get(section, 'Backup').split(',')
    }
    return options

def parse_vm_domain(config, section):
    domain_name = section_subname('VMDomain', section)
    options = {
        'name': domain_name,
        'id': config.get(section, 'ID'),
        'title': config.get(section, 'Title')
    }
    return options

config_parsers = {
    'file_backups': parse_file_backup,
    'file_shares': parse_file_share,
    'vm_domains': parse_vm_domain
}

def parse_config(config):
    config_values = {
        'file_backups': {},
        'file_shares': {},
        'vm_domains': {}
    }
    for section in config.sections():
        for category, parser in config_parsers:
            try:
                section_values = parser(config, section)
                config_values[category][section_values['name']] = section_values
            except ValueError:
                pass
    return config_values

def main():
    config = ConfigParser()
    config.read('backup.ini')
    config_values = parse_config(config)

    parser = ArgumentParser(
        description='Utilities for managing Unraid')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='list the steps to be taken instead of performing them')

    subparsers = parser.add_subparsers(
        title='Commands',
        required=True,
        dest='command')
    vm_backup_parser = subparsers.add_parser(
        'backup-vms',
        help='backup select VMs')
    remote_backup_parser = subparsers.add_parser(
        'backup-remote',
        help='backup files to remote location')

    args = parser.parse_args()
    runner = DryRunner() if args.dry_run else Runner()
    if args.command == 'backup-vms':
        service = DomainBackupService(runner)
        for domain in config_values['vm_domains']:
            service.backup_domain(domain)
    elif args.command == 'backup-remote':
        service = RemoteBackupService(runner)
        for file_backup in config_values['file_backups']:
            with service.storage(file_backup) as storage:
                for share in config_values['file_shares']:
                    if file_backup['name'] in share['backups']:
                        storage.backup_path(share['share'])

if __name__ == "__main__":
    main()
