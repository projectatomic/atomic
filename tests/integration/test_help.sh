#!/bin/bash -x
set -eu
# IFS=$'\n\t'

# ATOMIC="python2 ./atomic --debug"

# Test scripts run with PWD=tests/..

# The test harness exports some variables into the environment during
# testing: PYTHONPATH (python module import path
#          WORK_DIR   (a directory that is safe to modify)
#          DOCKER     (the docker executable location)
#          ATOMIC     (an invocation of 'atomic' which measures code coverage)
#          SECRET     (a generated sha256 hash inserted into test containers)

# In addition, the test harness creates some images for use in testing.
#   See tests/test-images/

OUTPUT=$(/bin/true)

# some other test leaves an image inside ostree backend, so
# let's clean the environment first
ostree --repo=${ATOMIC_OSTREE_REPO} refs --delete ociimage || true

# Test standard help in man format
if [ -x /usr/bin/groff ]; then
    MOUNTS_NUM=$(mount | wc -l)
    mkdir -p /run/atomic
    TEMPFILES_NUM=$(ls -1 /run/atomic | wc -l)
    ${ATOMIC} help atomic-test-1 1>/dev/null
    MOUNTS_NUM_AFTER=$(mount | wc -l)
    TEMPFILES_AFTER_NUM=$(ls -1 /run/atomic | wc -l)
    # Make sure that container mount is unmounted
    if [[ ${MOUNTS_NUM} != ${MOUNTS_NUM_AFTER} ]]; then
        # Test failed
        echo "It looks like that container is not unmounted after showing help file."
        exit 1
    fi
    # Make sure no temp files linger in /tmp
    if [[ ${TEMPFILES_NUM} != ${TEMPFILES_AFTER_NUM} ]]; then
        # Test failed
        echo "Some temporary files from /run/atomic were not cleaned."
        exit 1
    fi
fi

# Test override label - uppercase help
${ATOMIC} help atomic-test-3 | grep "Testing help"

# Test override label - lowercase help
${ATOMIC} help atomic-test-4 | grep "Testing help"

set +e
CENTOS_OUTPUT=$(${ATOMIC} help centos 2>&1)
set -e
grep "There is no help for centos" <<< "${CENTOS_OUTPUT}"

# Ensure atomic returns >0
rc=0
${ATOMIC} help centos >/dev/null || rc=$?
if [[ ${rc} != 1 ]]; then
    # Test failed
    echo "This test should result in a return code of 1"
    exit 1
fi
