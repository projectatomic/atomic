% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% January 2015
# NAME
atomic-host - Manage Atomic Host Commands

# SYNOPSIS
**atomic host [OPTIONS] COMMAND**

This command is a high-level wrapper for the underlying `rpm-ostree` tool which
can perform upgrades, rollbacks, and system state inspection.  It is used
for implementations of the Project Atomic Host pattern.

#NOTE
The `host` subcommand is only available when `rpm-ostree` is installed.

# OPTIONS
**-h** **-help**
  Print usage statement

**-r** **--reboot**
Initiate a reboot after rollback is prepared.

# COMMANDS
**status**
Print information about the current deployments.

**rollback**
Set the previously booted tree as the default.

**upgrade**
Perform an Atomic system upgrade.  This process will not modify your
current system.

# SEE ALSO
    man rpm-ostree 

# HISTORY
January 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
