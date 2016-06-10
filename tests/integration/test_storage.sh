#!/bin/bash -x
set -euo pipefail

# Test scripts run with PWD=tests/..

# The test harness exports some variables into the environment during
# testing: PYTHONPATH (python module import path
#          WORK_DIR   (a directory that is safe to modify)
#          DOCKER     (the docker executable location)
#          ATOMIC     (an invocation of 'atomic' which measures code coverage)
#          SECRET     (a generated sha256 hash inserted into test containers)

# In addition, the test harness creates some images for use in testing.
#   See tests/test-images/

# run only when ENABLE_DESTRUCTIVE is set
# :destructive-test

# This can copy non-existing files
#
smarter_copy() {
    if [ -f "$1" ]; then
        cp "$1" "$2"
    else
        rm -f "$2"
    fi
}

setup () {
    # Perform setup routines here.
    smarter_copy /etc/sysconfig/docker-storage-setup /etc/sysconfig/docker-storage-setup.atomic-tests-backup
    dd if=/dev/zero of=${WORK_DIR}/img-1 bs=1M count=10
    TEST_DEV_1=$(losetup --show -f -P ${WORK_DIR}/img-1)
    TEST_DEV_1_pvs=${TEST_DEV_1}p1

    ROOT_DEV=$( awk '$2 ~ /^\/$/ && $1 !~ /rootfs/ { print $1 }' /proc/mounts )
    VGROUP=$(lvs --noheadings -o vg_name ${ROOT_DEV} || true)
}

teardown () {
    # Cleanup your test data.
    set -e
    [ -n "$VGROUP" ] && (vgreduce $VGROUP "$TEST_DEV_1_pvs" || true)
    losetup -d "$TEST_DEV_1"
    smarter_copy /etc/sysconfig/docker-storage-setup.atomic-tests-backup /etc/sysconfig/docker-storage-setup
}

trap teardown EXIT
setup

# Running without /e/s/d-s-s should fail.

set +e
rm -f /etc/sysconfig/docker-storage-setup
OUTPUT=$(${ATOMIC} storage modify --add-device $TEST_DEV_1 2>&1)
if [[ $? -eq 0 ]]; then
    exit 1
fi
set -e
echo $OUTPUT | grep -q "No such file or directory"

if [ -n "$VGROUP" ]; then
    cat >/etc/sysconfig/docker-storage-setup <<EOF
MIN_DATA_SIZE=0G
DEVS=""
EOF

    # Adding a device should put it into the volume group and should add
    # it to /e/s/d-s-s.

    ${ATOMIC} storage modify --add-device $TEST_DEV_1
    [ $(pvs --noheadings -o vg_name $TEST_DEV_1_pvs) == $VGROUP ]
    grep -q "^DEVS=\"$TEST_DEV_1\"$" /etc/sysconfig/docker-storage-setup

    # Removing it should undo all that.

    ${ATOMIC} storage modify --remove-device $TEST_DEV_1
    ! (pvs --noheadings -o pv_name | grep -q $TEST_DEV_1_pvs)
    ! grep -q "^DEVS=\"$TEST_DEV_1\"$" /etc/sysconfig/docker-storage-setup

    # Adding it again straight away should work.

    ${ATOMIC} storage modify --add-device $TEST_DEV_1
    [ $(pvs --noheadings -o vg_name $TEST_DEV_1_pvs) == $VGROUP ]
    grep -q "^DEVS=\"$TEST_DEV_1\"$" /etc/sysconfig/docker-storage-setup

    # Now it should be unused.

    ${ATOMIC} storage modify --remove-unused-devices
    ! (pvs --noheadings -o pv_name | grep -q $TEST_DEV_1_pvs)
    ! grep -q "^DEVS=\"$TEST_DEV_1\"$" /etc/sysconfig/docker-storage-setup

    # Removing a device that is not in the pool should fail

    set +e
    OUTPUT=$(${ATOMIC} storage modify --remove-device $TEST_DEV_1 2>&1)
    if [[ $? -eq 0 ]]; then
        exit 1
    fi
    set -e
    echo $OUTPUT | grep -q "Not part of the storage pool: $TEST_DEV_1"

    # Removing a non-exitsing device should fail

    set +e
    OUTPUT=$(${ATOMIC} storage modify --remove-device /dev/nonexisting 2>&1)
    if [[ $? -eq 0 ]]; then
        exit 1
    fi
    set -e
    echo $OUTPUT | grep -q "Not part of the storage pool: /dev/nonexisting"

fi
