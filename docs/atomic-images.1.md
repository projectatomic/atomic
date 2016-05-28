% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% July 2015
# NAME
atomic-images - list locally installed container images

# SYNOPSIS
**atomic images**
[**-h|--help**]
[**-n|--noheading**]
[**--prune**]

# DESCRIPTION
**atomic images**, by default, will list all installed container images on your
system.

A `>` preceeding the image name indicates that the image is used by a container.

Using the `--prune` option will free wasted disk space by deleting unused
`dangling` images.

`Dangling` images are those with no name/tag and which are not used by any 
other images. Since they are not used, they waste system space.  Dangling
images are usually caused by using 'docker build' to update an image without
also removing the older version of the image.

A `*` in the first column indicates a dangling image.

# OPTIONS:
**-h** **--help**
  Print usage statement

**-n** **--noheading**
  Do not print heading when listing the images

**--prune**
  Prune (remove) all dangling images

# HISTORY
July 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
