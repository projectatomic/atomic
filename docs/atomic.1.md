% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% January 2015
# NAME
atomic \- Atomic Management Tool

# SYNOPSIS
**atomic** [OPTIONS] COMMAND [arg...]
              {upgrade,rollback,status,run,install,update,uninstall,defaults} ...

# DESCRIPTION
Atomic Management Tool

# OPTIONS
**--help**
  Print usage statement

# ATOMIC MANAGEMENT COMMANDS
**atomic-upgrade(1)**
Perform Atomic System Upgrade
**atomic-rollback(1)**
Revert Atomic to the previously booted tree
**atomic-status(1)**
Get the version of the booted Atomic system
Atomic Management commands are only available if you are running on an Atomic Host System or rpm-ostree is installed

# ATOMIC CONTAINER COMMANDS
**atomic-run(1)**
Execute Image Run Method (Default)
**atomic-update(1)**
Pull latest Image from repository
**atomic-uninstall(1)**
Uninstall Container from system
**atomic-install(1)**
Execute Image Install Method
**atomic-defaults(1)**
List Default RUN/INSTALL Values

# HISTORY
January 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
