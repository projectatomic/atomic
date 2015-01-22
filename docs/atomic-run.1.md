% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% January 2015
# NAME
atomic-run - Execute Image Run Method

# SYNOPSIS
**atomic run**
[**-h**]
[**--name**[=*NAME*]]
IMAGE [COMMAND] [ARG...]

# DESCRIPTION
**atomic run** attempts to read the `LABEL RUN` field in the container
IMAGE, if this field does not exists atom run defaults to the following
command:

```/usr/bin/docker run -t -i --rm -e CONFDIR=${CONFDIR} -e LOGDIR=${LOGDIR} -e DATADIR=${DATADIR} --name NAME IMAGE```

These defaults are suggested values for your container images.

atomic will replace the NAME and IMAGE fields with the name and image specified via the command,  NAME will be replaced with IMAGE if it is not specified.

# OPTIONS:
**--help**
  Print usage statement

**--name**=""
   Use this name for creating run content for the container.
NAME will default to the IMAGENAME if it is not specified.

**--spc**
  Run Container in Super Priviliged Container Mode

  The image will run with the following command:
  
```/usr/bin/docker run -t -i --rm --privileged -v /:/host --net=host --ipc=host --pid=host -e HOST=/host -e NAME=NAME -e IMAGE=IMAGE -e CONFDIR=${CONFDIR} -e LOGDIR=${LOGDIR} -e DATADIR=${DATADIR} --name NAME IMAGE COMMAND```

# HISTORY
January 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
