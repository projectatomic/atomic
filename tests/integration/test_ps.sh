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

${ATOMIC} ps --all -q -f type=docker | sort > atomic.ps.out
docker ps --all -q | sort > docker.ps.out
diff docker.ps.out atomic.ps.out

${ATOMIC} ps -q -f type=docker | sort > atomic.ps.out
docker ps -q | sort > docker.ps.out
diff docker.ps.out atomic.ps.out

