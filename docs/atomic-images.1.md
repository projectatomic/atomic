% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% July 2015
# NAME
atomic-images - list locally installed container images

# SYNOPSIS
**atomic images**
[**-h|--help**]
[**--prune**]

# DESCRIPTION
**atomic images**, by default, will list all installed container images on your
system.

Using the ```--prune``` option will free wasted disk space by deleting unused
`dangling` images.

`Dangling` images are those with no name/tag and which are not used by any 
other images. Since they are not used, they waste system space.  Dangling
images are usually caused by using 'docker build' to update an image without
also removing the older version of the image.

A `*` in the first column indicates a dangling image.

# OPTIONS:
**--help**
  Print usage statement

**--prune**
  Prune (remove) all dangling images

# HISTORY
July 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
