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

setup () {
    # Perform setup routines here.
    IMAGE="atomic-test-1"
    id1=`${DOCKER} run -d ${IMAGE} /usr/bin/vi`
    id2=`${DOCKER} run -d ${IMAGE} /usr/bin/top`

}

teardown () {
    # Cleanup your test data.
    set +e
    ${DOCKER} stop ${id1}
    ${DOCKER} rm ${id1}
    ${DOCKER} stop ${id2}
    ${DOCKER} rm ${id2}
    set -e
}
# Utilize exit traps for cleanup wherever possible. Additional cleanup
# logic can be added to a "cleanup stack", by cascading function calls
# within traps. See tests/integration/test_mount.sh for an example.
trap teardown EXIT

setup

OUTPUT=$(/bin/true)

${ATOMIC} top -n 1



