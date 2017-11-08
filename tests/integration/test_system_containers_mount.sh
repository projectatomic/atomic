#!/bin/bash -x
set -euo pipefail
IFS=$'\n\t'

. ./tests/integration/setup-scripts/system_containers_setup.sh

# The mount test of system containers, covers:
# 1. mounting an image
# 2. mounting a container
# 3. mount --live
# 4. mount --shared

setup () {
    mkdir ${WORK_DIR}/mount
    ${ATOMIC} pull --storage ostree docker:atomic-test-system:latest
    ${ATOMIC} install --system --name=${NAME} atomic-test-system
}

teardown () {
    set +o pipefail

    # Unmount the mountpoint
    ${ATOMIC} umount ${WORK_DIR}/mount &> /dev/null || true

    # Do not leave the runc container in any case
    runc kill $NAME 9 &> /dev/null || true
    runc delete $NAME &> /dev/null  || true

    # Ensure there is no systemd service left running
    systemctl stop $NAME &> /dev/null || true
    systemctl disable $NAME &> /dev/null || true
    rm -rf /etc/systemd/system/${NAME}.service || true
    rm -rf /etc/tmpfiles.d/${NAME}.conf || true

    # Delete all images from ostree
    ostree --repo=${ATOMIC_OSTREE_REPO} refs --delete ociimage &> /dev/null || true
}

trap teardown EXIT

OUTPUT=$(/bin/true)

setup

# 1. mount an image
# Since we have atomic-test-system in both ostree and docker, test that user must specify
OUTPUT=$(! ${ATOMIC} mount atomic-test-system ${WORK_DIR}/mount 2>&1)
grep "Found more than one Image with name atomic-test-system" <<< $OUTPUT

# Now specify a storage
${ATOMIC} mount atomic-test-system --storage ostree ${WORK_DIR}/mount
test -e ${WORK_DIR}/mount/usr/bin/greet.sh
${ATOMIC} umount ${WORK_DIR}/mount
test \! -e ${WORK_DIR}/mount/usr/bin/greet.sh


# 2. mount a container
${ATOMIC} mount ${NAME} ${WORK_DIR}/mount
test -e ${WORK_DIR}/mount/usr/bin/greet.sh
${ATOMIC} umount ${WORK_DIR}/mount


# 3. Check that --live fails
OUTPUT=$(! ${ATOMIC} mount --live ${NAME} ${WORK_DIR}/mount 2>&1)
grep "do not support --live" <<< $OUTPUT


# 4. Check that --shared works and that 'http:' is dropped
${ATOMIC} mount --shared http:${NAME} ${WORK_DIR}/mount
test -e ${WORK_DIR}/mount/usr/bin/greet.sh
${ATOMIC} umount ${WORK_DIR}/mount
