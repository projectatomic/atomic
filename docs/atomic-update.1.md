% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% January 2015
# NAME
atomic-update - Pull latest Image from repository

# SYNOPSIS
**atomic update**
[**-f**|**--force**]
[**-h**|**-h**]
IMAGE

# DESCRIPTION
**atomic update** will pull the latest update of the image from the repository.
If a container based on this image exists, the container will
continue to use the old image. Use --force to remove the container.

# OPTIONS:
**-f** **--force**
  Remove all containers based on this image

**-h** **--help**
  Print usage statement

# HISTORY
January 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
