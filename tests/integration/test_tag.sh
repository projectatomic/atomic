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

teardown () {
	set +e
	${DOCKER} rmi at1:latest  
	${ATOMIC} -y images delete --storage ostree at1:latest
	set -e
}

failed () {
	echo "${1} should have failed and did not"
}

trap teardown EXIT

rc=0
NAME="TEST1"
# Try to tag a non-existant image
${ATOMIC} images tag foobar123:latest f:latest 1>/dev/null || rc=$?
if [[ ${rc} != 1 ]]; then
    # Test failed
    failed "${NAME}"
    exit 1
fi

rc=0
# Try to tag a docker image to ostree should fail
NAME="TEST2"
${ATOMIC} images tag --storage ostree atomic-test-1:latest at1:latest 1>/dev/null || rc=$?
if [[ ${rc} != 1 ]]; then
    # Test failed
    failed "${NAME}"
    exit 1
fi

# Tag a docker image
NAME="TEST3"
${ATOMIC} images tag atomic-test-1:latest at1:latest
${DOCKER} inspect at1:latest 1>/dev/null 

# Tag an ostree image
${ATOMIC} pull --storage ostree docker:atomic-test-1:latest
${ATOMIC} images tag --storage ostree atomic-test-1:latest at1:latest
