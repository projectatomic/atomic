% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% January 2015
# NAME
atomic-install - Execute Image Install Method

# SYNOPSIS
**atomic install**
[**-h**]
[**--name**[=*NAME*]]
IMAGE [COMMAND] [ARG...]

# DESCRIPTION
**atomic install** attempts to read the `LABEL INSTALL` field in the container
IMAGE, if this field does not exists atom install defaults to the following
command:

```/usr/bin/docker run -t -i --rm --privileged -v /:/host --net=host --ipc=host --pid=host -e HOST=/host -e NAME=NAME -e IMAGE=IMAGE -e CONFDIR=${CONFDIR} -e LOGDIR=${LOGDIR} -e DATADIR=${DATADIR} --name NAME IMAGE /bin/sh```

These defaults are suggested values for your container images.

atomic will replace the NAME and IMAGE fields with the name and image specified via the command,  NAME will be replaced with IMAGE if it is not specified.

# OPTIONS:
**--help**
  Print usage statement

**--name**=""
   Use this name for creating installed content for the container.
NAME will default to the IMAGENAME if it is not specified.

# HISTORY
January 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
