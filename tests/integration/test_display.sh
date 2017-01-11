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
