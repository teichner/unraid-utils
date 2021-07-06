#!/usr/bin/env python3

from argparse import ArgumentParser
from domain_backup_service import DomainBackupService
from remote_backup_service import RemoteBackupService, CIFSOverRsyncStorage, RsyncStorage
from domain import domain_entry
from runner import Runner, DryRunner
from configparser import ConfigParser

def section_subname(expected_type, name):
    section_type, subname = name.split('.')
    if section_type.lower() != expected_type.lower():
        raise ValueError(f"Not a valid {expected_type} section")
    return subname

def parse_file_backup(config, section):
    backup_name = section_subname('FileBackup', section)
    backup_type = config.get(section, 'type')
    values = {
        'type': backup_type
    }

    #General Values
    values['ip'] = config.get(section, 'IP')
    values['local_base'] = config.get(section, 'LocalBase')
    values['remote_base'] = config.get(section, 'RemoteBase')
    values['remote_user'] = config.get(section, 'RemoteUser')
    values['ssh_key_file'] = config.get(section, 'SSHKeyFile')

    # CIFS Values
    if backup_type == 'CIFSOverRsync':
        values['cifs_volume'] = config.get(section, 'CIFSVolume')
        credentials_file = config.get(section, 'CIFSCredentialsFile')
        with open(credentials_file, 'r') as f:
            user, password = f.read().strip().split(':')
        values['cifs_user'] = user
        values['cifs_password'] = password

    return backup_name, values

def parse_file_share(config, section):
    share_name = section_subname('FileShare', section)
    values = {
        'directory': config.get(section, 'Directory'),
        'backups': config.get(section, 'Backup').split(',')
    }
    return share_name, values

def parse_vm_domain(config, section):
    domain_name = section_subname('VMDomain', section)
    values = {
        'id': config.get(section, 'ID'),
        'name': config.get(section, 'Name')
    }
    return domain_name, values

config_parsers = {
    'file_backups': parse_file_backup,
    'file_shares': parse_file_share,
    'vm_domains': parse_vm_domain
}

def parse_config(config):
    config_values = {
        'file_backups': {},
        'file_shares': {},
        'vm_domains': {},
        'vm_backup_settings': {
            'base': config.get('VMBackup', 'Base'),
            'limit': config.getint('VMBackup', 'Limit')
        }
    }

    for section in config.sections():
        for category, parser in config_parsers.items():
            try:
                name, section_values = parser(config, section)
                config_values[category][name] = section_values
            except ValueError:
                pass

    return config_values

def backup_vms(runner, config_values):
    service = DomainBackupService(runner, **config_values['vm_backup_settings'])
    for domain_values in config_values['vm_domains'].values():
        domain = domain_entry(**domain_values)
        service.backup_domain(domain)

storage_types = {
    'Rsync': RsyncStorage,
    'CIFSOverRsync': CIFSOverRsyncStorage
}

def backup_remote(runner, config_values):
    service = RemoteBackupService(runner)
    for backup_name, file_backup in config_values['file_backups'].items():
        storage_type = storage_types[file_backup['type']]
        storage_options = {k: v for k, v in file_backup.items() if k != 'type'}
        with service.storage(storage_type, **storage_options) as storage:
            for share_values in config_values['file_shares'].values():
                if backup_name in share_values['backups']:
                    storage.backup_path(share_values['directory'])

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
        backup_vms(runner, config_values)
    elif args.command == 'backup-remote':
        backup_remote(runner, config_values)

if __name__ == "__main__":
    main()
