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
The `host` subcommand is only available on `Atomic Host Systems`.

# OPTIONS
**-h** **-help**
  Print usage statement

**-r** **--reboot**
Initiate a reboot after rollback is prepared.

# COMMANDS
**status**
List information about all deployments

**rollback**
Switch to alternate installed tree at next boot

**upgrade**
Upgrade to the latest Atomic tree if one is available

**deploy**
Download and deploy a specific Atomic tree

**unlock**
Remove the read-only bind mount on `/usr`
and replace it with a writable overlay filesystem.  This
default invocation of "unlock" is intended for
development/testing purposes.  All changes in the overlay
are lost on reboot (or upgrade).  Pass `--hotfix` to create changes
that persist on reboot (but still not upgrades).


# SEE ALSO
    man rpm-ostree 
    man ostree 

# HISTORY
January 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
