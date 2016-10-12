#!/bin/bash -x
set -euo pipefail
IFS=$'\n\t'

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

# Test standard help in man format
if [ -x /usr/bin/groff ]; then
    ${ATOMIC} help atomic-test-1 1>/dev/null
fi

# Test override label
${ATOMIC} help atomic-test-3 1>/dev/null

rc=0
${ATOMIC} help centos:latest 1>/dev/null || rc=$?
if [[ ${rc} != 1 ]]; then
    # Test failed
    echo "This test should result in a return code of 1"
    exit 1
fi

