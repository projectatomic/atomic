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

lvname="container-root-lv"
rootfs="/var/lib/containers"

setup () {
    # Perform setup routines here.
    copy /etc/sysconfig/docker-storage-setup /etc/sysconfig/docker-storage-setup.atomic-tests-backup
    TEST_DEV_1=/dev/vdb
    if findmnt -o SOURCE | grep "^$TEST_DEV_1"; then
        findmnt -o SOURCE | grep "^$TEST_DEV_1" | uniq | xargs umount
    fi
    wipefs -a "$TEST_DEV_1"
    TEST_DEV_1_pvs=${TEST_DEV_1}1

    ROOT_DEV=$( awk '$2 ~ /^\/$/ && $1 !~ /rootfs/ { print $1 }' /proc/mounts )
    VGROUP=$(lvs --noheadings -o vg_name ${ROOT_DEV} || true)
}

teardown () {
    # Cleanup your test data.
    local mnt
    set -e
    wipefs -a "$TEST_DEV_1"
    copy /etc/sysconfig/docker-storage-setup.atomic-tests-backup /etc/sysconfig/docker-storage-setup
    remove /etc/sysconfig/docker-storage-setup.atomic-tests-backup
    local vgname=$(echo "$VGROUP"|sed 's/ //g')
    set +e
    mnt=$(findmnt -n -o TARGET --first-only --source /dev/${vgname}/${lvname})
    if [ -n "$mnt" ];then
       umount $mnt
    fi
    echo 'y'|lvremove /dev/${vgname}/${lvname}> /dev/null 2>&1
    set -e
}

setup
trap teardown EXIT

# If /etc/sysconfig/docker-storage-setup is missing, atomic should create the file.

# for now, do not remove setup options, as it will cause devicemapper/overlay issues
# rm -f /etc/sysconfig/docker-storage-setup

if [ -n "$VGROUP" ]; then
    cat >>/etc/sysconfig/docker-storage-setup <<EOF
MIN_DATA_SIZE=0G
EOF
    # Add a device to volume group backing root filesystem.

    OUTPUT=$(${ATOMIC} storage modify --add-device $TEST_DEV_1 2>&1)
    grep -q "^DEVS=\"$TEST_DEV_1\"$" /etc/sysconfig/docker-storage-setup
    [ $(pvs --noheadings -o vg_name $TEST_DEV_1_pvs) == $VGROUP ]

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

    # Test atomic storage modify: --lvname, --lvsize and --rootfs options.

    ${ATOMIC} storage modify --lvname "$lvname" --lvsize "20%FREE" --rootfs "$rootfs"
    grep -q "^CONTAINER_ROOT_LV_NAME=\"$lvname\"$" /etc/sysconfig/docker-storage-setup
    grep -q "^CONTAINER_ROOT_LV_MOUNT_PATH=\"$rootfs\"$" /etc/sysconfig/docker-storage-setup
    grep -q "^CONTAINER_ROOT_LV_SIZE=\"20%FREE\"$" /etc/sysconfig/docker-storage-setup

    # atomic storage modify --lvname should throw error if passed without --rootfs.

    set +e
    OUTPUT=$(${ATOMIC} storage modify --lvname "$lvname" 2>&1)
    if [[ $? -eq 0 ]]; then
        exit 1
    fi
    set -e
    echo $OUTPUT | grep -q "You must specify --rootfs when using --lvname"

    # atomic storage modify --rootfs should throw error if passed without --lvname.

    set +e
    OUTPUT=$(${ATOMIC} storage modify --rootfs "$rootfs" 2>&1)
    if [[ $? -eq 0 ]]; then
        exit 1
    fi
    set -e
    echo $OUTPUT | grep -q "You must specify --lvname when using --rootfs"

    # Test atomic storage modify: --lvsize option with invalid value/format.

    set +e
    OUTPUT=$(${ATOMIC} storage modify --lvname "$lvname" --rootfs "$rootfs" --lvsize="free" 2>&1)
    if [[ $? -eq 0 ]]; then
        exit 1
    fi
    set -e
    echo $OUTPUT | grep -q "Invalid format for --lvsize"
fi
