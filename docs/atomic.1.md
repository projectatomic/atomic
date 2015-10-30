% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% January 2015
# NAME
atomic \- Atomic Management Tool

# SYNOPSIS
**atomic** [OPTIONS] COMMAND [arg...]
  {diff,host,images,info,install,mount,run,scan,stop,uninstall,unmount,update,upload,verify,version}
[**-h**|**-help**]

# DESCRIPTION
Atomic Management Tool

# OPTIONS
**-h** **--help**
  Print usage statement

# COMMANDS
**atomic-diff(1)**
show the differences between two images|containers' RPMs

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

**atomic-stop(1)**
execute container image stop method

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
