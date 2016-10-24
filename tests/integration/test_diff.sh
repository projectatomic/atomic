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
    id1=`${DOCKER} create ${IMAGE} /bin/true`
    id2=`${DOCKER} create ${IMAGE} rpm -e vim-minimal`
    ${DOCKER} start ${id2} 

}

teardown () {
    # Cleanup your test data.
    set +e
    ${DOCKER} rm ${id1}
    ${DOCKER} rm ${id2}
    set -e
}
# Utilize exit traps for cleanup wherever possible. Additional cleanup
# logic can be added to a "cleanup stack", by cascading function calls
# within traps. See tests/integration/test_mount.sh for an example.
trap teardown EXIT

setup

OUTPUT=$(/bin/true)

# Test atomic diff for files and RPMs
${ATOMIC} diff -r -v ${id1} ${id2} 1>/dev/null

# Test atomic diff with RPMs and output to json
${ATOMIC} diff -r --json ${id1} ${id2}  1>/dev/null
