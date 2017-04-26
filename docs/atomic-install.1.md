% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% January 2015
# NAME
atomic-install - Execute Image Install Method

# SYNOPSIS
**atomic install**
[**-h**|**--help**]
[**--display**]
[**-n**][**--name**[=*NAME*]]
[**--rootfs**=*ROOTFS*]
[**--set**=*NAME*=*VALUE*]
[**--storage**]
[**--system-package=auto|build|yes|no**]
[**--system**]
IMAGE [ARG...]

# DESCRIPTION
**atomic install** attempts to read the `LABEL INSTALL` field in the container
IMAGE, if this field does not exist, `atomic install` will install the IMAGE.

If the container image has a LABEL INSTALL instruction like the following:

`LABEL INSTALL /usr/bin/docker run -t -i --rm \${OPT1} --privileged -v /:/host --net=host --ipc=host --pid=host -e HOST=/host -e NAME=\${NAME} -e IMAGE=\${IMAGE} -e CONFDIR=\/etc/${NAME} -e LOGDIR=/var/log/\${NAME} -e DATADIR=/var/lib/\${NAME} \${IMAGE} \${OPT2} /bin/install.sh \${OPT3}`

`atomic install` will set the following environment variables for use in the command:

**NAME**
The name specified via the command.  NAME will be replaced with IMAGE if it is not specified.

**IMAGE**
The name and image specified via the command.

**OPT1, OPT2, OPT3**
Additional options which can be specified via the command.

**SUDO_UID**
The `SUDO_UID` environment variable.  This is useful with the docker
`-u` option for user space tools.  If the environment variable is
not available, the value of `/proc/self/loginuid` is used.

**SUDO_GID**
The `SUDO_GID` environment variable.  This is useful with the docker
`-u` option for user space tools.  If the environment variable is
not available, the default GID of the value for `SUDO_UID` is used.
If this value is not available, the value of `/proc/self/loginuid`
is used.

Any additional arguments will be appended to the command.

# OPTIONS:
**-h** **--help**
Print usage statement

**--display**
Display the image's install options and environment variables
populated into the install command.
The install command will not execute if --display is specified.
If --display is not specified the install command will execute.

**-n** **--name**=""
 Use this name for creating installed content for the container.
 NAME will default to the IMAGENAME if it is not specified.

**--rootfs=ROOTFS**
Specify a ROOTFS folder, which can be an existing, expanded
container/image, or a location which contains an existing
root filesystem. The existing rootfs will be used as the new
system container's rootfs (read only), and thus the new container
will only contain config and info files.

**--set=NAME=VALUE**
Set a value that is going to be used by a system container for its
configuration and can be specified multiple times.  It is used only
by --system.  OSTree is required for this feature to be available.

**--storage**
Allows you to override the default definition for the storage backend
where your image will reside if pulled.  If the image is already local,
the --storage option will dictate where atomic should look for the image
prior to installing. Valid options are `docker` and `ostree`.

If you are installing a container using `docker` storage, you may define a
label in your image named `atomic.has_install_files`. This label indicates
there are files inside the container image which are meant to be placed on host
system. An rpm is created from these files and installed onto host system.

**--system**
Install a system container.  A system container is a container that
is executed out of an systemd unit file early in boot, using runc.
The specified **IMAGE** must be a system image already fetched.  If it
is not already present, atomic will attempt to fetch it assuming it is
an `oci` image.  For more information on how images are fetched, see
also **atomic-pull(1)**.
Installing a system container consists of checking it the image by
default under /var/lib/containers/atomic/ and generating the
configuration files for runc and systemd.
OSTree and runc are required for this feature to be available.

Note: If the image being pulled contains a label of `system.type=ostree`,
atomic will automatically substitute the storage backend to be ostree. This
can be overridden with the --storage option.

**--system-package=auto|build|no|yes**
Control how the container will be installed to the system.

*auto* generates an rpm and install it to the system when the
image defines a .spec file.  This is the default.

*build* build only the software package, without installing it.

*no* do not generate an rpm package to install the container.

*yes* generate an rpm package and install it to the system.

**--user**
If running as non-root, specify to install the image from the current
OSTree repository and manage it through systemd and bubblewrap.
OSTree and bwrap-oci are required for this feature to be available.

# HISTORY
January 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
July 2015, edited by Sally O'Malley (somalley at redhat dot com)
