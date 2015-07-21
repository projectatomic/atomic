#!/bin/bash -x
set -euo pipefail
IFS=$'\n\t'

EXPECTED_T1="Checksum: $(sha256sum ./tests/test-images/Dockerfile.1)"

validTest1 () {
    for e in ${TEST_1}; do
        [[ $e = ${EXPECTED_T1}* ]] && return 0;
    done
    return 1
}

TEST_1=`${ATOMIC} info atomic-test-1`
TEST_RHEL_REMOTE=`${ATOMIC} info --remote rhel7:7.1-9`
TEST_RHEL=`${ATOMIC} info rhel7:7.1-9`

set +e

TEST_DOES_NOT_EXIST=`${ATOMIC} info this-is-not-a-real-image`

set -e

echo $TEST_1

if [[ "${TEST_RHEL_REMOTE}" != "${TEST_RHEL}" ]]; then
    exit 1
fi

if [[ "${TEST_DOES_NOT_EXIST}" != "" ]]; then
    exit 1
fi

validTest1

if [[ $? -ne 0 ]]; then
    exit 1
fi
