% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% January 2015
# NAME
atomic \- Atomic Management Tool

# SYNOPSIS
**atomic** [OPTIONS] COMMAND [arg...]
  {diff,host,images,info,install,mount,run,scan,stop,storage,uninstall,unmount,update,upload,verify,version}
[**-h**|**--help**]

# DESCRIPTION
Atomic Management Tool

# OPTIONS
**-h** **--help**
  Print usage statement

**-v** **--version**
  Show atomic version

**--debug**
  Show debug messages

**-y** **--assumeyes**
  automatically answer yes for all questions

# ENVIRONMENT VARIABLES

**ATOMIC_CONF** The location of the atomic configuration file (normally /etc/atomic.conf) can be
overridden with the _ATOMIC_CONF_ environment variable

**ATOMIC_CONFD** The location of the atomic configuration directory (normally /etc/atomic.d/) can be
overridden with the _ATOMIC_CONFD_ environment variable.

# COMMANDS
**atomic-diff(1)**
show the differences between two images|containers' RPMs

**atomic-help(1)**
show help associated with a container or image

**atomic-host(1)**
execute commands to manage an Atomic host.

Note: only available on atomic host platforms.

**atomic-images(1)**
operations on locally installed container images

**atomic-info(1)**
execute read and display LABEL information about a container image

**atomic-install(1)**
execute commands on installed images

**atomic-mount(1)**
mount image or container to filesystem

**atomic-pull(1)**
pull latest image from repository

**atomic-push(1)**
push container image to a repository

**atomic-run(1)**
execute image run method (default)

**atomic-scan(1)**
scan an image or container for CVEs

**atomic-stop(1)**
execute container image stop method

**atomic-storage(1)**
manage the container storage on the system

**atomic-top(1)**
display a top-like list of container processes

**atomic-uninstall(1)**
uninstall container from system

**atomic-unmount(1)**
unmount previously mounted image or container

**atomic-update(1)**
Downloads the latest container image. 

**atomic-verify(1)**
verify image is fully updated

**atomic-version(1)**
display image 'Name Version Release' label


# CONNECTING TO DOCKER ENGINE

By default, `atomic` command connects to docker engine via UNIX domain socket
located at `/var/run/docker.sock`. You can use different connection method via
setting several environment variables:

**DOCKER_HOST** — this variable specifies connection string. If your engine
listens on UNIX domain socket, you can specify the path via
`http+unix://<path>`, e.g. `http+unix://var/run/docker2.sock`. For TCP the
string has this form: `tcp://<ip>:<port>`, e.g. `tcp://127.0.0.1:2375`

**DOCKER_TLS_VERIFY** — enables TLS verification if it contains any value,
otherwise it disables the verification

**DOCKER_CERT_PATH** — path to directory with TLS certificates, files in the
directory need to have specific names:

**cert.pem** — client certificate

**key.pem** — client key

**ca.pem** — CA certificate

For more info, please visit upstream docs:

**https://docs.docker.com/engine/security/https/**  
**https://docs.docker.com/machine/reference/env/**


# HISTORY
January 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
November, 2015 Addition of scan and diff by Brent Baude (bbaude at dot com)
