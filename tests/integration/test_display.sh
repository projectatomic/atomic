#!/bin/bash -x
set -euo pipefail
IFS=$'\n\t'

#
# 'atomic run --display' and 'atomic install --display' integration tests
# AUTHOR: Sally O'Malley <somalley at redhat dot com>
#

setup () {
    DISP_DIR="${WORK_DIR}/disp_test"
    mkdir -p "${DISP_DIR}"
    
    INAME="atomic-test-1"
}

teardown () {
    rm -rf "${DISP_DIR}"
    ${DOCKER} rm TEST3
    ${DOCKER} rm TEST4
}
trap teardown EXIT

setup

# Remove the --user UID:GID
OUTPUT=`${ATOMIC} run --display -n TEST1 atomic-test-1 | sed 's/ --user [0-9]*:[0-9]* //'`
OUTPUT2="/usr/bin/docker run -t -v /var/log/TEST1:/var/log -v /var/lib/TEST1:/var/lib  --name TEST1 atomic-test-1  echo I am the run label."
if [[ ${OUTPUT} != ${OUTPUT2} ]]; then
    exit 1
fi

OUTPUT=`${ATOMIC} install --display -n TEST2 atomic-test-1`
OUTPUT2="/usr/bin/docker  run -v /etc/TEST2:/etc -v /var/log/TEST2:/var/log -v /var/lib/TEST2:/var/lib  --name TEST2 atomic-test-1  echo I am the install label."
if [[ ${OUTPUT} != ${OUTPUT2} ]]; then
    exit 1
fi

${ATOMIC} install -n TEST3 atomic-test-1
OUTPUT=`${DOCKER} logs TEST3 | tr -d '\r'`
if [[ ${OUTPUT} != "I am the install label." ]]; then
    exit 1
fi

${ATOMIC} run -n TEST4 atomic-test-1
OUTPUT=`${DOCKER} logs TEST4 | tr -d '\r'`
if [[ ${OUTPUT} != "I am the run label." ]]; then
    exit 1
fi

OUTPUT=`${ATOMIC} install --display -n TEST5 centos`
OUTPUT2='/usr/bin/docker run -t -i --rm --privileged -v /:/host --net=host --ipc=host --pid=host -e HOST=/host -e NAME=TEST5 -e IMAGE=centos -e CONFDIR=/host/etc/TEST5 -e LOGDIR=/host/var/log/TEST5 -e DATADIR=/host/var/lib/TEST5 --name TEST5 centos'
if [[ ${OUTPUT} != ${OUTPUT2} ]]; then
    exit 1
fi
