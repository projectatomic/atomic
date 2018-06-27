#!/bin/bash
set -xeuo pipefail
NO_TEST=${NO_TEST:-}

if test -z "${INSIDE_CONTAINER:-}"; then

    if [ -f /run/ostree-booted ]; then

        # by default, the root LV on AH is only 3G, but we need a
        # bit more for our tests
        lvresize -r -L +5G atomicos/root || true

        if grep -q ID=fedora /etc/os-release; then
            if [ ! -e /var/tmp/ostree-unlock-ovl.* ]; then
                ostree admin unlock
            fi
        else
            # Until overlayfs and selinux get along, use remount
            # instead of ostree admin unlock
            if [ ! -w /usr ]; then
                mount -o remount,rw /usr
            fi
        fi
    else
        dnf install -y atomic python3-coverage docker
    fi

    # Restarting docker helps with permissions related to above.
    systemctl restart docker

    # somewhat mimic the spec conditional
    source /etc/os-release
    if [ "$ID" == fedora ]; then
      PYTHON=python3
    else
      PYTHON=python
    fi

    docker run --rm \
               --privileged \
               -v $PWD:/code \
               -v /:/host \
               --workdir /code \
               -e INSIDE_CONTAINER=1 \
               -e PYTHON=$PYTHON \
               registry.fedoraproject.org/fedora:28 /code/.papr.sh

    # run the testsuite on the host
    if [ -z ${NO_TEST} ]; then
        PYTHON=$PYTHON ./test.sh
    fi
    exit 0
fi

dnf install -y \
    git \
    make \
    python2-pylint \
    python3-pylint \
    python3-slip-dbus \
    python-gobject-base \
    python-dbus \
    pylint \
    python-slip-dbus \
    python2-docker \
    python2-dateutil \
    PyYAML \
    rpm-python \
    'dnf-command(builddep)' \
&& dnf builddep -y \
       atomic \
&& dnf clean all

# pylint, build, and install in the container
if [ -z ${NO_TEST} ]; then
    make pylint-check
    make test-python3-pylint
fi

rm -rf /host/usr/bin/atomic /host/usr/lib/python*/site-packages/Atomic

make PYTHON=$PYTHON PYLINT=true install DESTDIR=/host
