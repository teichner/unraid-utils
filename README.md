# Unraid Utilities

This script provides a growing number of utilities for managing my Unraid instance.

## Usage

``` sh
python3 unraid_utils.py [--dry-run] {subcommand}
```

The available subcommands are listed below. The "--dry-run" option will list the steps to be taken instead of performing the command itself.

### backup-vms
Uses virsh to take a snapshot of each virtual machine listed in configuration and copy the snapshot to a backup location. A snapshot may be taken while a VM is running; after the backup, any changes are merged back into the primary image, and the snapshot is removed.

### backup-remote
Uses rsync, or a combination of CIFS (SMB) and rsync, to backup Unraid shares listed in configuration to a remote location. CIFS excels at copying large files (and struggles with smaller files); so it is used to transfer files 1 GB or larger.
