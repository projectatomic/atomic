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

**--runtime=PATH**
Change the OCI runtime used by the systemd service file for running
system containers and user containers.  If runtime is not defined, the
value **runtime** in the configuration file is used for system
containers.  If there is no runtime defined in the configuration file
as well, then the default **/usr/bin/runc** is used for system containers.
Conversely, for user containers the default value is **/usr/bin/bwrap-oci**.

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

The system container template files support substition of variables.

These files in the image are managed as metadata for system
containers:

**/exports/config.json.template** The OCI configuration for running
the container.  The generated file is ultimately used by the OCI
runtime for setting up the container.

**/exports/manifest.json** Various settings for the container.

**/exports/service.template** Template for the systemd unit file.

**/exports/tmpfiles.template** Template for systemd-tmpfiles, if the
container needs temporary files on the system.

In **/exports/manifest.json** it is possible to setup these settings:

**defaultValues** A dictionary which containers the default values
given to variables used by the template files.  The user can override
these values with **-set=VARIABLE=NEWVALUE**.

**installedFilesTemplate** List of files that must be preprocessed
before being copied to the host.

**noContainerService** Set to True if the container is used only for
copying files to the host but has not a systemd service.

**renameFiles** Define the destination name of the files on the host.
Variable sobstitution is supported so that it is possible to use
variables to compose the final destination path.

Every file under **/exports/hostfs** is copied to the host when the
container is installed, and removed once the container is
uninstalled.
For instance, a file **/exports/hostfs/usr/local/bin/foo** in the
image is copied to the host as **/usr/local/bin/foo**.
The directives **installedFilesTemplate** and **renameFiles** from the
**manifest.json** file can be used to modify the content and the final
destination of the file.

**useLinks** Specify if files copied to the host under */usr* should use
hard links when possible.  By default it is True.

This is the list of the variables that get a value from atomic and
cannot be overriden by the user through **--set**:

**$DESTDIR** Destination on the file system for the checked out
container.

**$EXEC_STARTPRE** Command to use for the systemd directive ExecStartPre=.

**$EXEC_START** Command to use for the systemd directive ExecStart=.

**$EXEC_STOP** Command to use for the systemd directive ExecStop=.

**$EXEC_STOPPOST** Command to use for the systemd directive ExecStopPost=.

**$HOST_UID** UID of the user on the system.

**$HOST_GID** GID of the user on the system.

**$IMAGE_ID** ID of the image being installed.

**$IMAGE_NAME** Name of the image being installed.

**$NAME** Name of the container.

Some other variables get a value but it is possible to override it
through **--set**:

**$ALL_PROCESS_CAPABILITIES** A list of all the kernel process
capabilities available on the system, in the format expected in the
OCI configuration file.
Privileged containers that keep all capabilities should use this
variable instead of hardcoding the list.  This simplifies the
configuration file as well as improve images portability as the same
image can be used on systems with a different set of capabilities.

**$CONFIG_DIRECTORY** Directory where to store configuration files
(/etc on the host, ~/.config/ for user containers).

**$PIDFILE** File where to store the PID of the container main
process.

**$RUN_DIRECTORY** Directory where to store runtime files. (/run on
the host, $XDG_RUNTIME_DIR for user containers).

**$STATE_DIRECTORY** Directory where to store the state of the container.

**$UUID** UUID generated for this container.

**$RUNTIME** The runtime used to execute the containers.

**$ATOMIC** Path to the atomic executable that is installing the container.

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
The same image format as for **--system** is supported.  Please refer
to **--system** for more information.

# HISTORY
January 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
July 2015, edited by Sally O'Malley (somalley at redhat dot com)
October 2017, edited by Giuseppe Scrivano (gscrivan at redhat dot com)
