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
echo "testing"
IMAGE="atomic-test-4"
ID=`${DOCKER} inspect ${IMAGE} | grep '"Id"' | cut -f4 --delimiter=\"`
ATOMIC_VAR='/var/lib/containers/atomic'

setup () {
    # Perform setup routines here.
    ${DOCKER} tag ${IMAGE} foobar/${IMAGE}:latest

}

teardown () {
    # Cleanup your test data.
    set +e
    ${DOCKER} rmi foobar/${IMAGE}:latest
    set -e
}

# Utilize exit traps for cleanup wherever possible. Additional cleanup
# logic can be added to a "cleanup stack", by cascading function calls
# within traps. See tests/integration/test_mount.sh for an example.
trap teardown EXIT

setup
rc=0

${ATOMIC} verify ${ID} 1>/dev/null || rc=$?

if [[ ${rc} != 1 ]]; then
    # Test failed
    echo "This test should result in a return code of 1"
    exit 1
fi

${ATOMIC} images generate
if [ ! -d ${ATOMIC_VAR}/gomtree-manifests ]; then
    echo "gomtree manifests not created"
    exit 1
fi
rm -rf ${ATOMIC_VAR}/gomtree-manifests
