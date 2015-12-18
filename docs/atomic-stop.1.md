% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% January 2015
# NAME
atomic-stop - Execute container image stop method

# SYNOPSIS
**atomic stop**
[**-h**|**--help**]
[**-n**][**--name**[=*NAME*]]
IMAGE [ARG...]

# DESCRIPTION
**atomic stop** attempts to read the `LABEL STOP` field in the container
IMAGE.

If the container image has a `LABEL STOP` instruction like the following:

`LABEL STOP /usr/bin/docker kill -s HUP ${NAME}

atomic would execute this command before stopping the container.

`atomic stop` will set the following environment variables for use in the command:

**NAME**
  The name specified via the command. NAME will be replaced with IMAGE if it is not specified.

If this field does not exist, `atomic stop` will just stop the container, if
the container is running.

Any additional arguments will be appended to the command.

# OPTIONS:
**-h** **--help**
  Print usage statement

**-n** **--name**=""
   If name is specified `atomic stop` will stop the named container from the
   system, otherwise it will stop the container with a name that matches the
   image.

# HISTORY
March 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
