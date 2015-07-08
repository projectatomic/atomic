#!/bin/bash -x
set -euo pipefail
IFS = $'\n\t'

# Test scripts run with PWD=tests/..

# The test harness exports some variables into the environment during
# testing: PYTHONPATH (python module import path
#          WORK_DIR   (a directory that is safe to modify)
#          DOCKER     (the docker executable location)
#          SECRET     (a generated sha256 hash inserted into test
#                      containers)

# In addition, the test harness creates some images for use in testing.
#   See tests/test-images/

setup () {
    # Perform setup routines here.
    true
}

teardown () {
    # Cleanup your test data.
    true
}
# Utilize exit traps for cleanup wherever possible. Additional cleanup
# logic can be added to a "cleanup stack", by cascading function calls
# within traps. See tests/integration/test_mount.sh for an example.
trap teardown EXIT

# To expect a command to fail, observe the following pattern:
set +e # disable fail on error
false
if [[ $? -eq 0 ]]; then
    exit 1
fi
set -e # enable fail on error

# The test is considered to pass if it exits with zero status. Any other
# exit status is considered failure.

OUTPUT=$(/bin/true)

if [[ $? -ne 0 ]]; then
    exit 1
fi
