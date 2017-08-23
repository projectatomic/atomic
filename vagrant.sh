#!/bin/bash

set -euo pipefail
_FINISH(){
    RESULT=($?)
    if [ ${RESULT} -eq 0 ]; then
        echo ""
        echo "Tests completed normally..."
	vagrant destroy ${BOX}
        echo ""
    else
        echo ""
        echo "** Test failed.  Leaving '${BOX}' running for debug." 2>&1 | tee -a ${tee_file}
        echo "** Be sure to halt or destroy prior to re-running the check" 2>&1 | tee -a ${tee_file}
        echo "** Logs are stored at ${tee_file}"
        echo ""
        exit 1
    fi
}

# When make calls bash, the real signals are not surfaced
# correctly to trap.  So we trap on EXIT and then sort it
# out in _FINISH
trap _FINISH EXIT

BOXES="fedora_atomic centos_atomic fedora_cloud"

is_running() {
    status=$(vagrant status | grep ${BOX} | awk '{print $2}')
    if [ ${status} == "running" ]; then
        RUNNING=true
    else
        RUNNING=false
        
    fi
}


if [[ ! $BOXES =~ $BOX ]]; then
    echo ""
    echo "Invalid BOX name: $BOX.  Valid choices are $BOXES"
    echo ""
    exit 1
fi

echo "Testing on ${BOX}"
timestamp=$(date +%Y_%m_%d_%H_%M)
tee_file="${BOX}_${timestamp}.log"
is_running

if ${RUNNING}; then
        echo ""
        echo "*** '${BOX}' is already running.  Re-syncing and rerunning test ..."
        echo ""
        vagrant rsync ${BOX}
else
    vagrant up ${BOX} 2>&1 | tee ${tee_file}
fi

vagrant ssh ${BOX} -c "cd /home/vagrant/atomic && sudo sh ./.papr.sh" 2>&1 | tee -a ${tee_file}
