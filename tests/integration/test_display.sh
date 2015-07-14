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

OUTPUT=`${ATOMIC} run --display -n TEST1 atomic-test-1` 
if [[ ${OUTPUT} != "/usr/bin/docker run -t --user 1000:1000  -v /var/log/TEST1:/var/log -v /var/lib/TEST1:/var/lib  --name TEST1 atomic-test-1  echo I am the run label." ]]; then
    exit 1
fi

OUTPUT=`${ATOMIC} install --display -n TEST2 atomic-test-1` 
if [[ ${OUTPUT} != "docker  run -v /etc/TEST2:/etc/ -v /var/log/TEST2:/var/log/ -v /var/lib/TEST2:/var/lib/  --name TEST2 atomic-test-1  echo I am the install label." ]]; then
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
if [[ ${OUTPUT} != "" ]]; then
    exit 1
fi
