% ATOMIC(1) Atomic Man Pages
% Giuseppe Scrivano
% June 2016
# NAME
atomic-ps - list locally installed containers

# SYNOPSIS
**atomic ps**
[**-h|--help**]
[**-a|--all**]
[**-f|--filter**]
[**--json**]
[**-n|--noheading**]
[**--no-trunc**]
[**-q|--quiet**]

# DESCRIPTION
**atomic ps**, by default, will list all running containers on your
system.

Using --all will list all the installed containers.

# OPTIONS:
**-h** **--help**
  Print usage statement

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
