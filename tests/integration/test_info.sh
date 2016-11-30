#!/bin/bash -x
set -euo pipefail
IFS=$'\n\t'

# The debug information will cause test failures because
# the force arg will be different.  This messes up the
# equality testing between a remote and local image.
# Removing the --debug 
ATOMIC=$(grep -v -- --debug <<< "$ATOMIC")

EXPECTED_T1="Checksum: $(sha256sum ./tests/test-images/Dockerfile.1)"

validTest1 () {
    for e in ${TEST_1}; do
        [[ $e = ${EXPECTED_T1}* ]] && return 0;
    done
    return 1
}


TEST_1=`${ATOMIC} info atomic-test-1`
TEST_CENTOS=`${ATOMIC} info centos:latest | sort`

set +e

TEST_CENTOS_REMOTE=`${ATOMIC} info --remote centos:latest | sort`
HAS_REMOTE=$?
TEST_DOES_NOT_EXIST=`${ATOMIC} info this-is-not-a-real-image`

set -e

echo $TEST_1

if [[ "${HAS_REMOTE}" -eq 0 ]]; then
    if [[ ${TEST_CENTOS_REMOTE} != ${TEST_CENTOS} ]]; then
        exit 1
    fi
fi

# Disabled temporarily until skopeo discussion
#if [[ "${TEST_DOES_NOT_EXIST}" != "" ]]; then
#    exit 1
#fi

validTest1

if [[ $? -ne 0 ]]; then
    exit 1
fi
