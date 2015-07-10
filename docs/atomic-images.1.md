% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% July 2015
# NAME
atomic-images - list locally installed container images

# SYNOPSIS
**atomic images**
[**-h**]
IMAGE

# DESCRIPTION
**atomic images** by default will list all installed container images on your
system.

Using the ```--prune``` option, will free up disk space deleting unused
`dangling` images.

`Dangling` images are images with no name/tag which are not used by other images.
Since they are not used, they waste system space.  They are usually caused
by doing docker builds to update a container wither newer layered images.

A `*` in the first column indicates a dangling image.

# OPTIONS:
**--help**
  Print usage statement

**--prune**
  Prune dangling images

# HISTORY
July 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
