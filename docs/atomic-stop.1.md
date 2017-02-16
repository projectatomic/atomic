% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% January 2015
# NAME
atomic-stop - Execute container image stop method

# SYNOPSIS
**atomic stop**
[**--display**]
[**-h**|**--help**]
container [ARG...]

# DESCRIPTION
**atomic stop** attempts to stop a running container, first reading the
`LABEL STOP` field in the container IMAGE.

If the container image has a `LABEL STOP` instruction like the following:

`LABEL STOP /usr/bin/docker kill -s HUP \${NAME}`

atomic would execute this command before stopping the container.

`atomic stop` will set the following environment variables for use in the command:

If this field does not exist, `atomic stop` will just stop the container, if
the container is running.

Any additional arguments will be appended to the command.

# OPTIONS:
**--display**
  Display the container's stop options and environment variables populated into the stop command.
The stop command will not execute if --display is specified.
If --display is not specified the stop command will execute.
**-h** **--help**
  Print usage statement

# HISTORY
March 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
