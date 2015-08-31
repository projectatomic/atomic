% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% January 2015
# NAME
atomic-stop - Execute container image stop method

# SYNOPSIS
**atomic stop**
[**-h**|**--help**]
[**-n**][**--name**[=*NAME*]]
IMAGE

# DESCRIPTION
**atomic stop** attempts to read the `LABEL STOP` field in the container
IMAGE.

If the container image has a `LABEL STOP` instruction like the following:

`LABEL STOP /usr/bin/docker kill -s HUP --name ${NAME} ${IMAGE}`

atomic would execute this command before stopping the container.

`atomic stop` will set the following environment variables for use in the command:

**NAME**
  The name specified via the command.  NAME will be replaced with IMAGE if it is not specified.

**IMAGE**
  The name and image specified via the command.

**SUDO_UID**
  The `SUDO_UID` environment variable.  This is useful with the docker `-u` option for user space tools.  If the environment variable is not available, the value of `/proc/self/loginuid` is used.

**SUDO_GID**
  The `SUDO_GID` environment variable.  This is useful with the docker `-u` option for user space tools.  If the environment variable is not available, the default GID of the value for `SUDO_UID` is used.  If this value is not available, the value of `/proc/self/loginuid` is used.

If this field does not exist, `atomic stop` will just stop the container, if
the container is running.

# OPTIONS:
**-h** **--help**
  Print usage statement

**-n** **--name**=""
   If name is specified `atomic stop` will stop the named container from the
   system, otherwise it will stop the container with a name that matches the
   image.

# HISTORY
March 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
