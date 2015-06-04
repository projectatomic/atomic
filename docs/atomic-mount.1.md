% ATOMIC(1) Atomic Man Pages
% Will Temple
% June 2015
# NAME
atomic-mount - Mount Images/Containers to Filesystem

# SYNOPSIS
**atomic mount**
[**-o**|**--options** *OPTIONS*]
[REGISTRY/]IMAGE[:TAG]|ID
DIRECTORY

# DESCRIPTION
**atomic mount** attempts to mount the filesystem belonging to a given
container/image ID or IMAGE to the given DIRECTORY. Optionally, provide a
registry and tag to use a specific version of an image.

# OPTIONS
**-o|--options** *OPTIONS*
    Specify options to be passed to *mount*. Any options accepted by mount
are valid. Default settings are: 'ro,nodev,nosuid'. If this flag is specified,
no defaults are assumed. The 'rw' flag is *illegal* and will cause an error.

# HISTORY
June 2015, Originally compiled by William Temple (wtemple at redhat dot com)
