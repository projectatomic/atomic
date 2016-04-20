% ATOMIC(1) Atomic Man Pages
% Giuseppe Scrivano
% April 2016
# NAME
atomic-pull - fetch an image locally

# SYNOPSIS
**atomic pull**
[**-h|--help**]
[**--storage=[ostree]**]
IMAGE

# DESCRIPTION
**atomic pull**, will fetch a remote image and store it locally.

Use the `--ostree` option to store it into the OSTree repository.

# OPTIONS:
**-h** **--help**
  Print usage statement

**--storage=[ostree]**
  Define the destination storage for the pulled image.

# HISTORY
April 2016, Originally compiled by Giuseppe Scrivano (gscrivan at redhat dot com)
