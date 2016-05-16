% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% January 2015
# NAME
atomic \- Atomic Management Tool

# SYNOPSIS
**atomic** [OPTIONS] COMMAND [arg...]
  {diff,host,images,info,install,mount,run,scan,stop,storage,uninstall,unmount,update,upload,verify,version}
[**-h**|**-help**]

# DESCRIPTION
Atomic Management Tool

# OPTIONS
**-h** **--help**
  Print usage statement
# ENVIRONMENT VARIABLES

**ATOMIC_CONF** The location of the atomic configuration file (normally /etc/atomic.conf) can be
overridden with the _ATOMIC_CONF_ environment variable

**ATOMIC_CONFD** The location of the atomic configuration directory (normally /etc/atomic.d/) can be
overridden with the _ATOMIC_CONFD_ environment variable.

# COMMANDS
**atomic-diff(1)**
show the differences between two images|containers' RPMs

**atomic-help(1)**
show help associated with a container or image

**atomic-host(1)**
execute Atomic commands

**atomic-images(1)**
list locally installed container images

**atomic-info(1)**
execute Atomic commands

**atomic-install(1)**
execute image install method

**atomic-mount(1)**
mount image or container to filesystem

**atomic-run(1)**
execute image run method (default)

**atomic-scan(1)**
scan an image or container for CVEs

**atomic-storage(1)**
manage the container storage on the system

**atomic-stop(1)**
execute container image stop method

**atomic-top(1)**
display a top-like list of container processes

**atomic-uninstall(1)**
uninstall container from system

**atomic-unmount(1)**
unmount previously mounted image or container

**atomic-update(1)**
pull latest image from repository

**atomic-upload(1)**
upload container image to the repository

**atomic-verify(1)**
verify image is fully updated

**atomic-version(1)**
display image 'Name Version Release' label

# HISTORY
January 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
November, 2015 Addition of scan and diff by Brent Baude (bbaude at dot com)
