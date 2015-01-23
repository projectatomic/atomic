% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% January 2015
# NAME
atomic \- Atomic Management Tool

# SYNOPSIS
**atomic** [OPTIONS] COMMAND [arg...]
              {upgrade,rollback,status,run,update,remove,install,defaults} ...

# DESCRIPTION
Atomic Management Tool

# OPTIONS
**--help**
  Print usage statement

<<<<<<< .merge_file_KvA3qU
# COMMANDS
**atomic-defaults(1)**
list Default RUN/INSTALL/UNINSTALL Values
**atomic-host(1)**
execute Atomic commands
**atomic-install(1)**
execute image install method
||||||| .merge_file_BJvs6X
=======
# ATOMIC MANAGEMENT COMMANDS
**atomic-upgrade(1)**
Perform Atomic System Upgrade
**atomic-rollback(1)**
Revert Atomic to the previously booted tree
**atomic-status(1)**
Get the version of the booted Atomic system
Atomic Management commands are only available if you are running on an Atomic Host System or rpm-ostree is installed

# ATOMIC CONTAINER COMMANDS
>>>>>>> .merge_file_t2U7WU
**atomic-run(1)**
<<<<<<< .merge_file_KvA3qU
execute image run method (default)
**atomic-uninstall(1)**
uninstall container from system
||||||| .merge_file_BJvs6X
=======
Execute Image Run Method (Default)
>>>>>>> .merge_file_t2U7WU
**atomic-update(1)**
<<<<<<< .merge_file_KvA3qU
pull latest image from repository
||||||| .merge_file_BJvs6X
=======
Pull latest Image from repository
**atomic-remove(1)**
Remove Image from system
**atomic-install(1)**
Execute Image Install Method
**atomic-defaults(1)**
List Default RUN/INSTALL Values
>>>>>>> .merge_file_t2U7WU

# HISTORY
January 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
