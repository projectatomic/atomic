% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% January 2015
# NAME
atomic-run - Execute container image run method

# SYNOPSIS
**atomic run**
[**-h**|**--help**]
[**--display**]
[**-n**][**--name**[=*NAME*]]
[**--spc**]
[**--quiet**]
IMAGE [COMMAND] [ARG...]

# DESCRIPTION
**atomic run** attempts to start an existing container or run a container
from an image,  first reading the `LABEL RUN` field in the container IMAGE.


If the container image has a LABEL RUN instruction like the following:

`LABEL RUN /usr/bin/docker run -t -i --rm \${OPT1} --cap-add=SYS_ADMIN --net=host -v \${LOGDIR}:/var/log -v \${DATADIR}:/var/lib --name \${NAME} \${IMAGE} \${OPT2} run.sh \${OPT3}`

`atomic run` will run the following:

`/usr/bin/docker run -t -i --rm --cap-add=SYS_ADMIN --net=host -v ${LOGDIR}:/var/log -v ${DATADIR}:/var/lib --name ${NAME} ${IMAGE} run.sh`

If this field does not exist, `atomic run` defaults to the following:

`/usr/bin/docker run -t -i --rm -v ${LOGDIR}:/var/log -v ${DATADIR}:/var/lib --name ${NAME} ${IMAGE}`

These defaults are suggested values for your container images.

`atomic run` will set the following environment variables for use in the command:

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

**RUN_OPTS**
  Content of file specified by `LABEL RUN_OPTS_FILE`.  During `atomic install`, the `install.sh` can populate the file with any additional options that need to be passed to `docker run`, for example `--hostname=www.example.test` or `--net host`. The file name undergoes environment variable expansion, so for example `LABEL RUN_OPTS_FILE '/var/lib/${NAME}/docker-run-opts'` can be used to store per-container configuration.

# OPTIONS:
**-h** **--help**
  Print usage statement

**--display**
  Display the image's run options and environment variables populated into the run command.
The run command will not execute if --display is specified.
If --display is not specified the run command will execute.

**--n** **--name**=""
   Use this name for creating run content for the container.
NAME will default to the IMAGENAME if it is not specified.

**--spc**
  Run container in super privileged container mode.  The image will run with the following command:

`/usr/bin/docker run -t -i --rm --privileged -v /:/host -v /run:/run --net=host --ipc=host --pid=host -e HOST=/host -e NAME=${NAME} -e IMAGE=${IMAGE} --name ${NAME} ${IMAGE}`

**--quiet**
  Run without verbose messaging (i.e. security warnings).

# HISTORY
January 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
July 2015, edited by Sally O'Malley (somalley at redhat dot com)
