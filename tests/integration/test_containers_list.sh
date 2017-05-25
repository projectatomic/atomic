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
ATOMIC=$(grep -v -- --debug <<< "$ATOMIC")

OUTPUT=$(/bin/true)

${ATOMIC} containers list --all -q -f runtime=docker | sort > atomic.ps.out
docker ps --all -q | sort > docker.ps.out
diff docker.ps.out atomic.ps.out

${ATOMIC} containers list -q -f runtime=Docker | sort > atomic.ps.out
docker ps -q | sort > docker.ps.out
diff docker.ps.out atomic.ps.out

# Ensure that when json is requested and no containers are returned we still
# get valid json ([])
${ATOMIC} containers list --json -f container=idonotexist | grep "\[\]"
