% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% July 2015
# NAME
atomic-images - operations on container images

# SYNOPSIS
**atomic images COMMAND [OPTIONS] [IMAGES...]**

atomic images allows the user to view and operate on container images in a docker registry.

# COMMANDS
**list**

list all installed container images on your system.

A `>` preceding the image name indicates that the image is used by a container.

A `*` in the first column indicates a dangling image.


`Dangling` images are those with no name/tag and which are not used by any
other images. Since they are not used, they waste system space.  Dangling
images are usually caused by using 'docker build' to update an image without
also removing the older version of the image.

# list OPTIONS
[**-h|--help**]
  Print usage statement

[**-n|--noheading**]
  Do not print heading when listing the images

[**--no-trunc**]
  Do not truncate output

[**--prune**]
  Prune (remove) all dangling images

Using the `--prune` option will free wasted disk space by deleting unused `dangling` images.


**delete IMAGES...**

Mark given container image(s) for deletion. Remote disk space will not be freed until the
```registry garabage-collection``` command is invoked for the remote registry.

# delete OPTIONS
[**-f|--force**]
  Delete image(s) without conformation from the user

[**--remote**]
  Delete images in remote registry

# HISTORY
July 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)


June 2016, Updated to reflect images sub-command changes (jhonce at redhat dot com)
