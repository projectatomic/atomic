% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% January 2015
# NAME
atomic-install - Execute Image Install Method

# SYNOPSIS
**atomic install**
[**-h**]
[**--name**[=*NAME*]]
IMAGE [ARG...]

# DESCRIPTION
**atomic install** attempts to read the `LABEL INSTALL` field in the container
IMAGE, if this field does not exist, `atomic install` will install the IMAGE

If the container image has a LABEL INSTALL instruction like the following:

```LABEL INSTALL /usr/bin/docker run -t -i --rm --privileged -v /:/host --net=host --ipc=host --pid=host -e HOST=/host -e NAME=${NAME} -e IMAGE=${IMAGE} -e CONFDIR=${CONFDIR} -e LOGDIR=${LOGDIR} -e DATADIR=${DATADIR} --name ${NAME} ${IMAGE} /bin/install.sh```

`atomic install` will replace the NAME and IMAGE fields with the name and
image specified via the command,  NAME will be replaced with IMAGE if it is
not specified. `atomic install` will pass in the CONFDIR, LOGDIR, DATADIR, NAME, and IMAGE environment variables to the container (the NAME variable will be set to IMAGE if not specified).  Any additional arguments will be
appended to the command.

# OPTIONS:
**--help**
  Print usage statement

**--name**=""
   Use this name for creating installed content for the container.
NAME will default to the IMAGENAME if it is not specified.

# HISTORY
January 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
