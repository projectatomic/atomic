#!/bin/bash -x
set -euo pipefail
IFS=$'\n\t'

#
# 'atomic run --display' and 'atomic install --display' integration tests
# AUTHOR: Sally O'Malley <somalley at redhat dot com>
#
ATOMIC=${ATOMIC:="/usr/bin/atomic"}
ATOMIC=$(grep -v -- --debug <<< "$ATOMIC")
DOCKER=${DOCKER:="/usr/bin/docker"}
TNAME="test_display"

teardown () {
    ${DOCKER} rm TEST3 TEST4 2> /dev/null
}
trap teardown EXIT

# Remove the --user UID:GID
OUTPUT=`${ATOMIC} run --display -n TEST1 atomic-test-1 | sed 's/ --user [0-9]*:[0-9]* / /' | xargs`
OUTPUT2="/usr/bin/docker run -t -v /var/log/TEST1:/var/log -v /var/lib/TEST1:/var/lib --name TEST1 atomic-test-1 echo I am the run label."
if [[ ${OUTPUT} != ${OUTPUT2} ]]; then
    echo "Failed ${TNAME} 1"
    exit 1
fi

OUTPUT=`${ATOMIC} install --display -n TEST2 atomic-test-1 | xargs`
OUTPUT2="/usr/bin/docker run -v /etc/TEST2:/etc -v /var/log/TEST2:/var/log -v /var/lib/TEST2:/var/lib --name TEST2 atomic-test-1 echo I am the install label."
if [[ ${OUTPUT} != ${OUTPUT2} ]]; then
    echo "Failed ${TNAME} 2"
    exit 1
fi

${ATOMIC} install -n TEST3 atomic-test-1
OUTPUT=`${DOCKER} logs TEST3 | tr -d '\r'`
if [[ ${OUTPUT} != "I am the install label." ]]; then
    echo "Failed ${TNAME} 3"
    exit 1
fi

${ATOMIC} run -n TEST4 atomic-test-1
OUTPUT=`${DOCKER} logs TEST4 | tr -d '\r'`
if [[ ${OUTPUT} != "I am the run label." ]]; then
    echo "Failed ${TNAME} 4"
    exit 1
fi

# The centos image does not have an INSTALL label, so `atomic install` should be
# a noop.
OUTPUT=`${ATOMIC} install --display -n TEST5 centos | xargs`
if [[ -n ${OUTPUT} ]]; then
    echo "Failed ${TNAME} 5"
    exit 1
fi

# The centos image does not have an run label, so output should be $OUTPUT2
OUTPUT=`${ATOMIC} run --display -n TEST6 centos /bin/ls | sed 's/ -t / /g' | xargs`
OUTPUT2="docker run -i --name TEST6 centos /bin/ls"
if [[ ${OUTPUT} != ${OUTPUT2} ]]; then
    echo "Failed ${TNAME} 6"
    exit 1
fi

# The centos image does not have an run label, so output should be $OUTPUT2
OUTPUT=`${ATOMIC} run --display --spc -n TEST7 centos /bin/ls | sed 's/ -t / /g' | xargs`
OUTPUT2="docker run -i --privileged -v /:/host -v /run:/run -v /etc/localtime:/etc/localtime -v /sys/fs/selinux:/sys/fs/selinux:ro --net=host --ipc=host --pid=host -e HOST=/host -e NAME=TEST7 -e IMAGE=centos -e SYSTEMD_IGNORE_CHROOT=1 --name TEST7 centos /bin/ls"

if [[ ${OUTPUT} != ${OUTPUT2} ]]; then
    echo "Failed ${TNAME} 7"
    exit 1
fi

# Test for regression on atomic stop
CID=`docker run -d atomic-test-6 sleep 100`
OUTPUT=`${ATOMIC} stop --display ${CID}`
OUTPUT2="docker stop ${CID}"
docker stop ${CID}

if [[ ${OUTPUT} != ${OUTPUT2} ]]; then
    echo "Failed ${TNAME} 8"
    exit 1
fi

OUTPUT=`${ATOMIC} uninstall --display atomic-test-1`
RESULT='/usr/bin/docker run -v /etc/atomic-test-1:/etc -v /var/log/atomic-test-1:/var/log -v /var/lib/atomic-test-1:/var/lib --name atomic-test-1 atomic-test-1 echo I am the uninstall label.'
if [[ ${OUTPUT} != ${RESULT} ]]; then
    echo "Uninstall display failed for uninstall-1"
    exit 1
fi
