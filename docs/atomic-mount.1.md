% ATOMIC(1) Atomic Man Pages
% Will Temple
% June 2015
# NAME
atomic-mount - Mount Images/Containers to Filesystem

# SYNOPSIS
**atomic mount**
[**--live** | [**-o**|**--options** *OPTIONS*]]
[REGISTRY/]REPO[:TAG]|UUID|NAME
DIRECTORY

# DESCRIPTION
**atomic mount** attempts to mount the underlying filesystem of a container or
image into the host filesystem. Accepts one of image UUID, container UUID,
container NAME, or image REPO (optionally with registry and tag information).
If the given UUID or NAME is a container, and **--live** is not set, then
*atomic mount* will create a snapshot of the container by commiting it to a
temporary image and spawning a temporary container from that image. If UUID or
REPO refers to an image, then *atomic mount* will simply create a temporary
container from the given image. All temporary artifacts are cleaned upon
*atomic unmount*.

# OPTIONS
**-o|--options** *OPTIONS*
Specify options to be passed to *mount*. All options accepted by the 'mount'
command are valid. The default mount options (if the **--live** flag is unset)
are: 'ro,nodev,nosuid'. If the **-o** flag is specified, then no default
options are assumed. Use of the 'rw' flag is discouraged, as writes into the
atomic temporary containers are never preserved. Use of this option conflicts
with **--live**, as live containers have predetermined, immutable mount
options.

**--live**
Mount a container live, writable, and synchronized. This option allows the user
to modify the container's contents as it runs or update the container's
software without rebuilding the container. If live mode is used, no mount
options may be provided.

# HISTORY
June 2015, Originally compiled by William Temple (wtemple at redhat dot com)
