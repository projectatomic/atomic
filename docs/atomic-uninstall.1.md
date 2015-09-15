% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% January 2015
# NAME
atomic-uninstall - Remove/Uninstall container/container image from system

# SYNOPSIS
**atomic uninstall**
[**-f**][**--force**]
[**-h**|**--help**]
[**-n**][**--name**[=*NAME*]]
[**--opt1**[=*OPT*]]
[**--opt2**[=*OPT*]]
[**--opt3**[=*OPT*]]
IMAGE [ARG...]

# DESCRIPTION
**atomic uninstall** attempts to read the `LABEL UNINSTALL` field in the
container IMAGE, if this field does not exist **atomic uninstall** will just
uninstall the image.

If the container image has a LABEL UNINSTALL instruction like the following:

`LABEL UNINSTALL /usr/bin/docker run -t -i --rm \${OPT1} --privileged -v /:/host --net=host --ipc=host --pid=host -e HOST=/host -e NAME=${NAME} -e IMAGE=${IMAGE} -e CONFDIR=\/etc/${NAME} -e LOGDIR=/var/log/\${NAME} -e DATADIR=/var/lib/\${NAME} ${IMAGE} \${OPT2} /bin/uninstall.sh \${OPT3}`

`atomic uninstall` will set the following environment variables for use in the command:

**NAME**
  The name specified via the command.  NAME will be replaced with IMAGE if it is not specified.

**IMAGE**
  The name and image specified via the command.

**OPT1, OPT2, OPT3**
  Additional options which can be specified via the command.

**SUDO_UID**
  The `SUDO_UID` environment variable.  This is useful with the docker `-u` option for user space tools.  If the environment variable is not available, the value of `/proc/self/loginuid` is used.

**SUDO_GID**
  The `SUDO_GID` environment variable.  This is useful with the docker `-u` option for user space tools.  If the environment variable is not available, the default GID of the value for `SUDO_UID` is used.  If this value is not available, the value of `/proc/self/loginuid` is used.

Any additional arguments will be appended to the command.

# OPTIONS:
**-f** **--force**
  Remove all containers based on this image

**-h** **--help**
  Print usage statement

**-n** **--name**=""
   If name is specified `atomic uninstall` will uninstall the named container from the system, otherwise it will uninstall the container images.

**--opt1**=""
   Substitute options specified as opt1 for all instances of ${OPT1} specified
in the LABEL.

**--opt2**=""
   Substitute options specified as opt2 for all instances of ${OPT2} specified
in the LABEL.

**--opt3**=""
   Substitute options specified as opt3 for all instances of ${OPT3} specified
in the LABEL.

# HISTORY
January 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
