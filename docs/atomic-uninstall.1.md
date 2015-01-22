% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% January 2015
# NAME
atomic-uninstall - Remove/Uninstall Image from system

# SYNOPSIS
**atomic uninstall**
[**-h**]
IMAGE

# DESCRIPTION
**atomic uninstall** attempts to read the `LABEL REMOVE` field in the
container IMAGE, if this field does not exists **atom uninstall** will just
uninstall the image.

# OPTIONS:
**--help**
  Print usage statement

# HISTORY
January 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
