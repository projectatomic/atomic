#!/bin/bash -x
set -euo pipefail
IFS=$'\n\t'

ATOMIC=${ATOMIC:="/usr/bin/atomic"}
ATOMIC=$(grep -v -- --debug <<< "$ATOMIC")
DOCKER=${DOCKER:="/usr/bin/docker"}

teardown () {
	set +e
	${DOCKER} rm -f RUN_TEST > /dev/null
	set -e
}

fail () {
	echo "Fail: TEST ${1} should have failed and did not"
	exit 1
}

passed () {
	echo "Passed: TEST ${1}"
}


failed () {
	echo "Fail: TEST ${1}"
	exit 1
}


trap teardown EXIT

# Check that atomic run's naming
TEST_NUM=1
${ATOMIC} run -n RUN_TEST atomic-test-1 date
CID=$("$DOCKER" ps -alq)
NAME=$("$DOCKER" inspect --format='{{.Name}}' "$CID")


if [[ "${NAME}" != /RUN_TEST ]]; then
    failed "${TEST_NUM}"
fi
passed "${TEST_NUM}"

TEST_NUM=2
rc=0
${ATOMIC} run -n RUN_TEST atomic-test-1 date 1>/dev/null || rc=$?
if [[ ${rc} != 1 ]]; then
    # Test failed
    fail "${TEST_NUM}"
fi

passed "${TEST_NUM}"


TEST_NUM=3
${ATOMIC} run --replace -n RUN_TEST atomic-test-1 date
NEW_CID=$("$DOCKER" ps -alq)
NAME=$("$DOCKER" inspect --format='{{.Name}}' "$NEW_CID")

if [[ "${NAME}" != /RUN_TEST ]]; then
    failed "${TEST_NUM}"
fi

if [[ "${NEW_CID}" == "${CID}" ]]; then
    failed "${TEST_NUM}"
fi

passed "${TEST_NUM}"
