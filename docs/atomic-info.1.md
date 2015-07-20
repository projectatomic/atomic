% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% January 2015
# NAME
atomic-info - Display LABEL information about an image

# SYNOPSIS
**atomic info**
[**-h**]
[**--remote**]
IMAGE

# DESCRIPTION
**atomic info** displays the LABEL fields within an image. By default, it
will check first for a local image and then all configured registries.

# OPTIONS:
**--help**
  Print usage statement

**--remote**
  Ignore all local images, only search configured registries.

# HISTORY
January 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
