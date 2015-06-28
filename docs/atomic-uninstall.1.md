% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% January 2015
# NAME
atomic-uninstall - Remove/Uninstall container/container image from system

# SYNOPSIS
**atomic uninstall**
[**-f**][**--force**]
[**-h**]
IMAGE [ARG...]

# DESCRIPTION
**atomic uninstall** attempts to read the `LABEL UNINSTALL` field in the
container IMAGE, if this field does not exists **atom uninstall** will just
uninstall the image.

If the container image has a LABEL UNINSTALL instruction like the following:

```LABEL UNINSTALL /usr/bin/docker run -t -i --rm --privileged -v /:/host --net=host --ipc=host --pid=host -e HOST=/host -e NAME=${NAME} -e IMAGE=${IMAGE} -e CONFDIR=${CONFDIR} -e LOGDIR=${LOGDIR} -e DATADIR=${DATADIR} --name ${NAME} ${IMAGE} /bin/uninstall.sh```

`atomic uninstall` will set the following environment variables for use in the command:

**NAME**
  The name specified via the command.  NAME will be replaced with IMAGE if it is not specified.

**IMAGE**
  The name and image specified via the command.

**SUDO_UID**
  The `SUDO_UID` environment variable.  This is useful with the docker `-u` option for user space tools.  If the environment variable is not available, the value of `/proc/self/loginuid` is used.

**SUDO_GID**
  The `SUDO_GID` environment variable.  This is useful with the docker `-u` option for user space tools.  If the environment variable is not available, the default GID of the value for `SUDO_UID` is used.  If this value is not available, the value of `/proc/self/loginuid` is used.

`atomic uninstall` will also pass in the CONFDIR, LOGDIR and DATADIR environment variables to the container. Any additional arguments will be appended to the command.

# OPTIONS:
**-f** **--force**
  Remove all containers based on this image

**--help**
  Print usage statement

**--name**=""
   If name is specified `atomic uninstall` will uninstall the named container from the system, otherwise it will uninstall the container images.

# HISTORY
January 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
