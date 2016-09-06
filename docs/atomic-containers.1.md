% ATOMIC(1) Atomic Man Pages
% Giuseppe Scrivano
% June 2016
# NAME
atomic-containers - operations on containers

# SYNOPSIS
**atomic containers COMMAND [OPTIONS] [CONTAINERS...]**

atomic containers allows the user to view and operate on containers

# COMMANDS
**list**

list containers on your system.

**trim**

discard unused blocks (fstrim) on running containers.

# DESCRIPTION
**atomic containers list**, by default, will list all running containers on your
system.

Using --all will list all the installed containers.

**atomic containers trim**, Discard unused blocks (fstrim) on rootfs of running containers.

e.g. If you have 2 running containers on your system with container IDs (496b8679b6cf, 9bb990da1203).

>atomic containers trim
Trimming container id 496b8679b6cf
Trimming container id 9bb990da1203

# OPTIONS:
**-h** **--help**
  Print usage statement

# list OPTIONS:
**-a** **--all**
  Print all the installed containers

**-f** **--filter**
  Filter output based on given filters, example usage: `--filter id=foo` will list all containers that has "foo" as part of their ID.

  Filterables: `container (id)`, `image`, `command`, `created`, `status`, `runtime`

**--json**
  Print in a machine parsable format

**-n** **--noheading**
  Do not print heading when listing the containers

**--no-trunc**
  Do not truncate output

**-q** **--quiet**
  Only display container IDs

# HISTORY
June 2016, Originally compiled by Giuseppe Scrivano (gscrivan at redhat dot com)
July 2016, Added sub-commands filter, no-trunc and quiet (jerzhang at redhat dot com)
Sept 2016, Added atomic containers trim subcommand (shishir dot mahajan at redhat dot com)
