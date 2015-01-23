% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% January 2015
# NAME
<<<<<<< .merge_file_z4hOFQ
atomic-run - Execute container image run method
||||||| .merge_file_UedLCP
=======
atomic-run - Execute Image Run Method
>>>>>>> .merge_file_E1gobR

# SYNOPSIS
**atomic run**
[**-h**]
[**--name**[=*NAME*]]
IMAGE [COMMAND] [ARG...]

# DESCRIPTION
**atomic run** attempts to read the `LABEL RUN` field in the container
<<<<<<< .merge_file_z4hOFQ
IMAGE.


If the contaimer image has a LABEL RUN instruction like the folling:

```LABEL RUN /usr/bin/docker run -t -i --rm --cap_add=SYS_ADMIN --net=host -v ${LOGDIR}:/var/log -v ${DATADIR}:/var/lib --name NAME IMAGE```

If this field does not exists atom run defaults to the following
||||||| .merge_file_UedLCP
=======
IMAGE, if this field does not exists atom run defaults to the following
>>>>>>> .merge_file_E1gobR
command:

<<<<<<< .merge_file_z4hOFQ
```/usr/bin/docker run -t -i --rm -v ${LOGDIR}:/var/log -v ${DATADIR}:/var/lib --name NAME IMAGE```
||||||| .merge_file_UedLCP
=======
```/usr/bin/docker run -t -i --rm -e CONFDIR=${CONFDIR} -e LOGDIR=${LOGDIR} -e DATADIR=${DATADIR} --name NAME IMAGE```

These defaults are suggested values for your container images.
>>>>>>> .merge_file_E1gobR

atomic will replace the NAME and IMAGE fields with the name and image specified via the command,  NAME will be replaced with IMAGE if it is not specified.

# OPTIONS:
**--help**
  Print usage statement

**--name**=""
   Use this name for creating run content for the container.
NAME will default to the IMAGENAME if it is not specified.

**--spc**
<<<<<<< .merge_file_z4hOFQ
  Run container in super priviliged container mode
||||||| .merge_file_UedLCP
=======
  Run Container in Super Priviliged Container Mode
>>>>>>> .merge_file_E1gobR

  The image will run with the following command:
  
```/usr/bin/docker run -t -i --rm --privileged -v /:/host --net=host --ipc=host --pid=host -e HOST=/host -e NAME=NAME -e IMAGE=IMAGE -e CONFDIR=${CONFDIR} -e LOGDIR=${LOGDIR} -e DATADIR=${DATADIR} --name NAME IMAGE COMMAND```

# HISTORY
January 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
