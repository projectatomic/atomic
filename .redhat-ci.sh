#!/bin/bash
set -xeuo pipefail
NO_TEST=${NO_TEST:-}

if [ -f /run/ostree-booted ]; then

    # by default, the root LV on AH is only 3G, but we need a
    # bit more for our tests
    lvresize -r -L +5G atomicos/root

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

DOCKER_RUN="docker run --rm \
              --privileged \
              -v $PWD:/code \
              -v /:/host \
              --workdir /code \
                projectatomic/atomic-tester"

# pylint, build, and install in the container...
if [ -z ${NO_TEST} ]; then
$DOCKER_RUN make pylint-check
$DOCKER_RUN make test-python3-pylint
fi
$DOCKER_RUN make PYTHON=$PYTHON PYLINT=true install DESTDIR=/host

# ... but run the testsuite on the host
if [ -z ${NO_TEST} ]; then
    PYTHON=$PYTHON ./test.sh
fi
