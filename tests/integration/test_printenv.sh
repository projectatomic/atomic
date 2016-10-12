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

TESTDIR=/run/atomic/test

mkdir -p ${TESTDIR}

# In addition, the test harness creates some images for use in testing.
#   See tests/test-images/

teardown () {
    # Cleanup your test data.
    set +e
    rm -rf ${TESTDIR}
    set -e
}

# Utilize exit traps for cleanup wherever possible. Additional cleanup
# logic can be added to a "cleanup stack", by cascading function calls
# within traps. See tests/integration/test_mount.sh for an example.
trap teardown EXIT

OUTPUT=$(/bin/true)

cd $(realpath $PWD)

${ATOMIC} run atomic-test-5 | grep -v ^NAME= | grep -v ^IMAGE= | grep -v ^SUDO | grep -v printenv | grep -v atomic | grep -v coverage | sort > ${TESTDIR}/atomic-test-5.1

printenv | grep -v printenv | grep -v ^SUDO | grep -v atomic | grep -v coverage | sort > ${TESTDIR}/atomic-test-5.2
diff ${TESTDIR}/atomic-test-5.1 ${TESTDIR}/atomic-test-5.2
exit $?

