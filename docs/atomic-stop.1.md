% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% January 2015
# NAME
atomic-stop - Execute container image stop method

# SYNOPSIS
**atomic stop**
[**-h**]
[**--name**[=*NAME*]]
IMAGE

# DESCRIPTION
**atomic stop** attempts to read the `LABEL STOP` field in the container
IMAGE.

If the container image has a `LABEL STOP` instruction like the following:

```CLABEL STOP /usr/bin/docker kill -s HUP --name NAME IMAGE```

atomic would execute this command before stoping the container.

atomic will replace the NAME and IMAGE fields with the name and image specified via the command,  NAME will be replaced with IMAGE if it is not specified.

If this field does not exist, `atomic stop` will just stop the container, if
the container is running.

# OPTIONS:
**--help**
  Print usage statement

**--name**=""
   If name is specified `Catomic stop` will stop the named container from the
   system, otherwise it will stop the container with a name that matches the
   image.

# HISTORY
March 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
