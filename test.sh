#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

#
# Test harness for the atomic CLI.
#
export PYTHONPATH=${PYTHONPATH:-$(pwd)}
export WORK_DIR=$(mktemp -p $(pwd) -d -t .tmp.XXXXXXXXXX)
export DOCKER=${DOCKER:-"/usr/bin/docker"}
export SECRET=`dd if=/dev/urandom bs=4096 count=1 2> /dev/null | sha256sum`

# This image contains the secret, so it needs to be rebuilt each time.
cat > tests/test-images/Dockerfile.secret <<EOF
FROM scratch
LABEL "Name"="atomic-test-secret"
LABEL "Secret"="${SECRET}"
ADD secret /secret
EOF

LOG=${LOG:-"$(pwd)/tests.log"}

echo -n '' > ${LOG}

cleanup () {
    rm -rf ${WORK_DIR}
}
trap cleanup EXIT

# Ensure the test-environment has a standard set of images.
# This function will not rebuild images if the dockerfile
# is the same as its last build.
make_docker_images () {
    echo "${SECRET}" > ${WORK_DIR}/secret
    echo "Pulling standard images from Docker Hub..." | tee -a ${LOG}
    ${DOCKER} pull busybox >> ${LOG}
    # TODO: Was using RHEL, but suddenly can't pull rhel7:latest
    ${DOCKER} pull centos >> ${LOG}
    echo "Building images from tests/test-images..." | tee -a ${LOG}
    for df in `find ./tests/test-images/ -name Dockerfile.*`; do
        chksum=$(sha256sum ${df})
        IFS=$'.' read -a split <<< "$(basename ${df})"
        iname="atomic-test-${split[1]}"

        set +e
        i_chksum=`${DOCKER} inspect -f '{{ .Config.Labels.Checksum }}' \
            ${iname}`
        if [[ ${i_chksum} = "<no-value>" ]] || \
            [[ "${i_chksum}" = "${chksum}" ]]; then
            printf "\tSkipped : ${iname}\n"
            continue
        fi
        set -e

        df_cp=${WORK_DIR}/$(basename ${df})
        cp ${df} ${df_cp}
        printf "\nLABEL \"Checksum\"=\"${chksum}" >> ${df_cp}
        set +e
        ${DOCKER} rmi ${iname} &>> ${LOG}
        set -e
        ${DOCKER} build -t ${iname} -f ${df_cp} ${WORK_DIR} >> ${LOG}
        printf "\tBuilt   : ${iname}\n"
    done
}

make_docker_images

# Python unit tests.
echo "UNIT TESTS:"

COVERAGE="/usr/bin/coverage"
if [[ ! -x "${COVERAGE}" ]]; then
    # The executable is "coverage2" on systems with default python3 and no
    # python3 install.
    COVERAGE="/usr/bin/coverage2"
fi

set +e

${COVERAGE} run --source=./Atomic/ --branch  -m unittest discover \
	./tests/unit | tee -a ${LOG}
_UNIT_FAIL="$?"
set -e

echo "Coverage report:" | tee -a ${LOG}

${COVERAGE} report | tee -a ${LOG}

# CLI integration tests.
# TODO: I would like to be able to include CLI tests in the coverage report.
let failures=0 || true
printf "\nINTEGRATION TESTS:\n" | tee -a ${LOG}

for tf in `find ./tests/integration/ -name test_*.sh`; do
    printf "Running test $(basename ${tf})...\t\t"
    printf "\n==== ${tf} ====\n" >> ${LOG}
    if ${tf} &>> ${LOG}; then
        printf "PASS\n";
    else
        printf "FAIL\n";
        let "failures += 1"
    fi
done

if [[ "${failures}" -eq "0" ]]; then
    if [[ $_UNIT_FAIL -eq 0 ]]; then
        echo "ALL TESTS PASSED"
        exit 0
    else
        echo "Unit tests failed."
    fi
else
    if [[ $_UNIT_FAIL -ne 0 ]]; then
        echo "Unit tests failed."
    fi
    echo "Integration test failures: ${failures}"
    echo "See ${LOG} for more information."
fi
exit 1
