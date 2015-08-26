% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% May 2015
# NAME
atomic-verify - Verify image is fully updated

# SYNOPSIS
**atomic verify**
[**-h**|**--help**]
IMAGE

# DESCRIPTION
**atomic verify** checks whether there is a newer image available and scans
through all layers to see if any of the sublayers have a new version available.
If the tool finds an out of date image it will tell user to update the image.

# OPTIONS:
**-h** **--help**
  Print usage statement

# HISTORY
May 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
