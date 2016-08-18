# Atomic: /usr/bin/atomic

This project defines the entrypoint for Project Atomic hosts.  On an
Atomic Host, there are at least two distinct software
delivery vehicles; Docker (often used in combination with the
traditional RPM/yum/dnf), and rpm-ostree to provide atomic upgrades of the
host system.

The goal of Atomic is to provide a high level, coherent entrypoint to
the system, and fill in gaps in Linux container implementations.

For Docker, `atomic` can make it easier to interact with special kinds
of containers, such as super-privileged debugging tools and the like.

The `atomic host` subcommand wraps `rpm-ostree`, currently just
providing a friendlier name, but in the future Atomic may provide more
unified management.

## atomic run

Atomic allows an image provider to specify how a container image expects to be
run.

Specifically this includes the privilege level required.

For example if you built an 'ntpd' container application, that required the
SYS_TIME capability, you could add meta data to your container image using the
command:

`LABEL RUN /usr/bin/docker run -d --cap-add=SYS_TIME ntpd`

Now if you executed `atomic run ntpd`, it would read the `LABEL RUN` json
metadata from the container image and execute this command.

## atomic install

Most of the time when you ship an application, you need to run an install
script.  This script would configure the system to run the application, for
example it might configure a systemd unit file or configure kubernetes to
run the application.  This tool will allow application developers to embed the
install and uninstall scripts within the application.  The application
developers can then define the LABEL INSTALL and LABEL UNINSTALL methods, in
the image meta data.  Here is a simple httpd installation description.

cat Dockerfile
```
# Example Dockerfile for httpd application
#
FROM		fedora
MAINTAINER	Dan Walsh
ENV container docker
RUN yum -y update; yum -y install httpd; yum clean all

LABEL Vendor="Red Hat" License=GPLv2
LABEL Version=1.0
LABEL INSTALL="docker run --rm --privileged -v /:/host -e HOST=/host -e LOGDIR=/var/log/\${NAME} -e CONFDIR=/etc/\${NAME} -e DATADIR=/var/lib/\${NAME} -e IMAGE=\${IMAGE} -e NAME=\${NAME} \${IMAGE} /bin/install.sh"
LABEL UNINSTALL="docker run --rm --privileged -v /:/host -e HOST=/host -e IMAGE=${IMAGE} -e NAME=${NAME} ${IMAGE} /bin/uninstall.sh"
ADD root /

EXPOSE 80

CMD [ "/usr/sbin/httpd", "-D", "FOREGROUND" ]
```

`atomic install` will read the LABEL INSTALL line and substitute `${NAME}` with
the name specified with the name option, or use the image name, it will also
replace`${IMAGE}` with the image name.

To be used by the application.  The install script could populate these
directories if necessary.

In my example the INSTALL method will execute the install.sh which we add to
the image.  The root sub directory contains the following scripts:

The `atomic install` will set the following environment variables for use in the command:

**SUDO_UID**
  The `SUDO_UID` environment variable.  This is useful with the docker `-u` option for user space tools.  If the environment variable is not available, the value of `/proc/self/loginuid` is used.

**SUDO_GID**
  The `SUDO_GID` environment variable.  This is useful with the docker `-u` option for user space tools.  If the environment variable is not available, the default GID of the value for `SUDO_UID` is used.  If this value is not available, the value of `/proc/self/loginuid` is used.

cat root/usr/bin/install.sh
```
#!/bin/sh
# Make Data Dirs
mkdir -p ${HOST}/${CONFDIR} ${HOST}/${LOGDIR}/httpd ${HOST}/${DATADIR}

# Copy Config
cp -pR /etc/httpd ${HOST}/${CONFDIR}

# Create Container
chroot ${HOST} /usr/bin/docker create -v /var/log/${NAME}/httpd:/var/log/httpd:Z -v /var/lib/${NAME}:/var/lib/httpd:Z --name ${NAME} ${IMAGE}

# Install systemd unit file for running container
sed -e "s/TEMPLATE/${NAME}/g" etc/systemd/system/httpd_template.service > ${HOST}/etc/systemd/system/httpd_${NAME}.service

# Enabled systemd unit file
chroot ${HOST} /usr/bin/systemctl enable /etc/systemd/system/httpd_${NAME}.service
```

## atomic uninstall

The `atomic unistall` does the same variable substitution as described for
install, and can be used to remove any host system configuration.

Here is the example script we used.

cat root/usr/bin/uninstall.sh
```
#!/bin/sh
chroot ${HOST} /usr/bin/systemctl disable /etc/systemd/system/httpd_${NAME}.service
rm -f ${HOST}/etc/systemd/system/httpd_${NAME}.service
```

Finally here is the systemd unit file template I used:

cat root/etc/systemd/system/httpd_template.service
```
# cat ./root/etc/systemd/system/httpd_template.service
[Unit]
Description=The Apache HTTP Server for TEMPLATE
After=docker.service
BindTo=docker.service

[Service]
ExecStart=/usr/bin/docker start TEMPLATE
ExecStop=/usr/bin/docker stop TEMPLATE
ExecReload=/usr/bin/docker exec -t TEMPLATE /usr/sbin/httpd $OPTIONS -k graceful

[Install]
WantedBy=multi-user.target
```

For an explaination of the Atomic scan JSON output, see the JSON [specification document](README-atomic-scan.md).
