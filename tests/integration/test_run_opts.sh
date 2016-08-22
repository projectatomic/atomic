#!/bin/bash -x
set -euo pipefail
IFS=$'\n\t'

test() {
    expected="$1"
    output=$(${ATOMIC} run atomic-test-6 | grep -v docker)

if [[ "${expected}" != "${output}" ]]; then
    # Test failed
    echo "Test Failed"
    echo ${expected}
    echo "!= "
    echo ${output}
    exit 1
fi
}

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

rc=0
# Test different values
echo --hostname=www.example.test -e VAR1=xyz > docker-run-opts-atomic-test-6
test www.example.test:xyz
echo --hostname=www2.example.test > docker-run-opts-atomic-test-6
test www2.example.test:
rm -f docker-run-opts-atomic-test-6

