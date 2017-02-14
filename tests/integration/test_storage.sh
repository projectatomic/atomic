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

copy() {
    if [ -f "$1" ]; then
        cp "$1" "$2"
    fi
}

remove(){
    if [ -f "$1" ]; then
       rm -f "$1"
    fi
}

setup () {
    # Perform setup routines here.
    copy /etc/sysconfig/docker-storage-setup /etc/sysconfig/docker-storage-setup.atomic-tests-backup
    TEST_DEV_1=/dev/vdb
    MNT=$(mount | awk '$1 ~/vdb/' | awk '{print $3}')
    if [ ${MNT} ]; then
	    umount $MNT
    fi
    wipefs -a "$TEST_DEV_1"
    TEST_DEV_1_pvs=${TEST_DEV_1}1

    ROOT_DEV=$( awk '$2 ~ /^\/$/ && $1 !~ /rootfs/ { print $1 }' /proc/mounts )
    VGROUP=$(lvs --noheadings -o vg_name ${ROOT_DEV} || true)
}

teardown () {
    # Cleanup your test data.
    set -e
    wipefs -a "$TEST_DEV_1"
    copy /etc/sysconfig/docker-storage-setup.atomic-tests-backup /etc/sysconfig/docker-storage-setup
    remove /etc/sysconfig/docker-storage-setup.atomic-tests-backup
}

setup
trap teardown EXIT

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
