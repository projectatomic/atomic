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
export ATOMIC_LIBEXEC="$(pwd)"

mkdir $WORK_DIR/ostree-repo
ostree --repo=$WORK_DIR/ostree-repo init --mode=bare-user
export ATOMIC_OSTREE_REPO=$WORK_DIR/ostree-repo

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

_checksum () {
    if [[ -d "${1}" ]]; then
        CHK=`find "${1}" -type f -exec sha256sum {} \; | sha256sum`
        echo "${CHK}"
        return 0
    fi
    if [[ -e "${1}" ]]; then
        echo "$(sha256sum ${1})"
    fi
}

# Ensure the test-environment has a standard set of images.
# This function will not rebuild images if the dockerfile
# is the same as its last build.
make_docker_images () {
    echo "${SECRET}" > ${WORK_DIR}/secret
    echo "Pulling standard images from Docker Hub..." | tee -a ${LOG}
    ${DOCKER} pull busybox >> ${LOG}
    ${DOCKER} pull centos >> ${LOG}
    ${DOCKER} pull fedora >> ${LOG}
    echo "Building images from tests/test-images..." | tee -a ${LOG}
    for df in `find ./tests/test-images/ -name Dockerfile.*`; do
        # Don't include directories for dockerfile data
        if [[ -d "${df}" ]]; then
            continue
        fi

        BASE_NAME="$(basename ${df})"

        chksum=$(_checksum ${df})
        IFS=$'.' read -a split <<< "${BASE_NAME}"
        iname="atomic-test-${split[1]}"
        # If there is a matching Dockerfile.X.d, then include its contents
        # in the checksum data.
        chksum="${chksum}$(_checksum ${df}.d)"

        set +e
        i_chksum=`${DOCKER} inspect -f '{{ .Config.Labels.Checksum }}' \
            ${iname} 2> /dev/null`
        if [[ ${i_chksum} = "<no-value>" ]] || \
            [[ "${i_chksum}" = "${chksum}" ]]; then
            printf "\tSkipped : ${iname}\n"
            continue
        fi
        set -e

        # Copy the dockerfile into the build directory, then label the image
        # with the original Dockerfile's checksum. This allows us to prevent
        # rebuilding images
        df_cp=${WORK_DIR}/${BASE_NAME}
        cp ${df} ${df_cp}
        printf "\nLABEL \"Checksum\"=\"${chksum}" >> ${df_cp}

        # Copy help.1 into atomic-test-1
        if [[ ${iname} = "atomic-test-1" ]]; then
            cp ./tests/test-images/help.1 ${WORK_DIR}
        fi

        # Copy help.sh into atomic-test-3
        if [[ ${iname} = "atomic-test-3" ]]; then
            cp ./tests/test-images/help.sh ${WORK_DIR}
        fi

        # Copy install.sh into atomic-test-6
        if [[ ${iname} = "atomic-test-6" ]]; then
            cp ./tests/test-images/install.sh ${WORK_DIR}
            cp ./tests/test-images/show-hostname.sh ${WORK_DIR}
        fi

        # Copy install.sh into atomic-test-system
        if [[ ${iname} = "atomic-test-system" ]]; then
            cp ./tests/test-images/system-container-files/* ${WORK_DIR}
        fi

        # Remove the old image... Though there may not be one.
        set +e
        ${DOCKER} rmi ${iname} &>> ${LOG}
        set -e

        if [[ -d "${df}.d" ]]; then
            cp -r "${df}.d" "${WORK_DIR}/${BASE_NAME}.d"
        fi

        ${DOCKER} build -t ${iname} -f ${df_cp} ${WORK_DIR} >> ${LOG}

        # Clean up build files.
        rm "${df_cp}"
        if [[ -d "${WORK_DIR}/${BASE_NAME}.d" ]]; then
            rm -r "${WORK_DIR}/${BASE_NAME}.d"
        fi
        printf "\tBuilt   : ${iname}\n"
    done
}

make_docker_images

# Python unit tests.
echo "UNIT TESTS:"

COVERAGE_BIN=${COVERAGE_BIN-"/usr/bin/coverage"}

if [[ ! -x "${COVERAGE_BIN}" ]]; then
  # Check to see if it is in local instead.
  COVERAGE_BIN="/usr/local/bin/coverage"
fi

if [[ ! -x "${COVERAGE_BIN}" ]]; then
  # The executable is "coverage2" on systems with default python3 and no
  # python3 install.
  COVERAGE_BIN="/usr/bin/coverage2"
fi

if [[ -x "${COVERAGE_BIN}" ]]; then
    COVERAGE="${COVERAGE_BIN}
run
--source=./Atomic/
--branch"
else
    COVERAGE="${PYTHON:-/usr/bin/python}"
fi

set +e
${COVERAGE} -m unittest discover ./tests/unit/ | tee -a ${LOG}
_UNIT_FAIL="$?"
set -e

# CLI integration tests.
let failures=0 || true
printf "\nINTEGRATION TESTS:\n" | tee -a ${LOG}

export ATOMIC="atomic
--debug"
if [[ -x "${COVERAGE_BIN}" ]]; then
    export ATOMIC="${COVERAGE}
--append
$ATOMIC"
fi

for tf in `find ./tests/integration/ -name test_*.sh`; do

    if [ -n "${TEST_INTEGRATION+ }" ]; then
        tfbn=$(basename "$tf" .sh)
        tfbn="${tfbn#test_}"
        if [[ " $TEST_INTEGRATION " != *" $tfbn "* ]]; then
            continue
        fi
    fi

    # If it is not running with ENABLE_DESTRUCTIVE and the test has
    # not the :test-destructive tag, skip it silently.
    if test -z "${ENABLE_DESTRUCTIVE-}" && grep ":destructive-test" ${tf} &> /dev/null; then
        continue
    fi

    printf "Running %-40.40s" "$(basename ${tf})...."
    printf "\n==== ${tf} ====\n" >> ${LOG}

    if ${tf} &>> ${LOG}; then
        printf "PASS\n";
    else
        if test $? = 77; then
            printf "SKIP\n";
        else
            printf "FAIL\n";
            let "failures += 1"
        fi
    fi
done

if [[ -x "${COVERAGE_BIN}" ]]; then
    echo "Coverage report:" | tee -a ${LOG}
    ${COVERAGE_BIN} report | tee -a ${LOG}
fi

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
