% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% January 2015
# NAME
atomic-run - Execute container image run method

# SYNOPSIS
**atomic run**
[**-h**]
[**--name**[=*NAME*]]
[**--spc**]
IMAGE [COMMAND] [ARG...]

# DESCRIPTION
**atomic run** attempts to read the `LABEL RUN` field in the container
IMAGE.


If the container image has a LABEL RUN instruction like the following:

```LABEL RUN /usr/bin/docker run -t -i --rm --cap_add=SYS_ADMIN --net=host -v ${LOGDIR}:/var/log -v ${DATADIR}:/var/lib --name ${NAME} ${IMAGE}```

If this field does not exist, `atomic run` defaults to the following:
```/usr/bin/docker run -t -i --rm -v ${LOGDIR}:/var/log -v ${DATADIR}:/var/lib --name ${NAME} ${IMAGE}```

These defaults are suggested values for your container images.

`atomic run` will set the following environment variables for use in the command:

**NAME**
  The name specified via the command.  NAME will be replaced with IMAGE if it is not specified.

**IMAGE**
  The name and image specified via the command.

**SUDO_UID**
  The `SUDO_UID` environment variable.  This is useful with the docker `-u` option for user space tools.  If the environment variable is not available, the value of `/proc/self/loginuid` is used.

**SUDO_GID**
  The `SUDO_GID` environment variable.  This is useful with the docker `-u` option for user space tools.  If the environment variable is not available, the default GID of the value for `SUDO_UID` is used.  If this value is not available, the value of `/proc/self/loginuid` is used.

# OPTIONS:
**--help**
  Print usage statement

**--name**=""
   Use this name for creating run content for the container.
NAME will default to the IMAGENAME if it is not specified.

**--spc**
  Run container in super privileged container mode

  The image will run with the following command:
  
```/usr/bin/docker run -t -i --rm --privileged -v /:/host -v /run:/run --net=host --ipc=host --pid=host -e HOST=/host -e NAME=${NAME} -e IMAGE=${IMAGE} --name ${NAME} ${IMAGE}```

# HISTORY
January 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
