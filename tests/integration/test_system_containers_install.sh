#!/bin/bash -x
set -euo pipefail
IFS=$'\n\t'

. ./tests/integration/setup-scripts/system_containers_setup.sh

# The installation test of system containers, covers:
# 1. installation (install --system)
# 2. setting environment variables (--set)
# 3. setting a remote rootfs (--roofts)
# 4. uninstalling a system container
# 5. expected installation failures
# 6. install from a dockertar
# 7. install from local docker
# 8. install a run-once system container
# 9. install a container with .0 in the name

setup () {
    docker save atomic-test-system > ${WORK_DIR}/atomic-test-system.tar
    ${ATOMIC} pull --storage ostree dockertar:/${WORK_DIR}/atomic-test-system.tar
    ${ATOMIC} pull --storage ostree docker:atomic-test-system-update:latest
}

teardown () {
    set +o pipefail

    # Do not leave the runc container in any case
    runc kill $NAME 9 &> /dev/null || true
    runc delete $NAME &> /dev/null  || true
    runc kill $NAME-remote 9 &> /dev/null || true
    runc delete $NAME-remote &> /dev/null || true

    # Ensure there is no systemd service left running
    systemctl stop $NAME &> /dev/null || true
    systemctl disable $NAME &> /dev/null || true
    rm -rf /etc/systemd/system/${NAME}.service || true
    rm -rf /etc/tmpfiles.d/${NAME}.conf || true
    systemctl stop $NAME-remote &> /dev/null || true
    systemctl disable $NAME-remote &> /dev/null || true
    rm -rf /etc/systemd/system/${NAME}-remote.service || true
    rm -rf /etc/tmpfiles.d/${NAME}-remote.conf || true

    # Delete all images from ostree
    ostree --repo=${ATOMIC_OSTREE_REPO} refs --delete ociimage &> /dev/null || true
}

trap teardown EXIT

OUTPUT=$(/bin/true)

setup

# 1. Install a system container and check for the files
${ATOMIC} install --name=${NAME} --set=RECEIVER=${SECRET} --system oci:atomic-test-system
test -e /etc/tmpfiles.d/${NAME}.conf
test -e /etc/systemd/system/${NAME}.service
test -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.0/${NAME}.service
test -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.0/tmpfiles-${NAME}.conf
test -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.0/config.json
test -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.0/info

if sestatus | grep "SELinux status:.*enabled"; then
    test "$(stat -c%C /)" = "$(stat -c%C ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.0/rootfs)"
fi

# 2. Check the value we set (--set) is exported into the config file
assert_matches ${SECRET} ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.0/config.json

# The default value $PORT specified in the manifest.json is exported
assert_matches 8081 ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.0/config.json


# 3. Test if a container with a remote rootfs is installed correctly
${ATOMIC} install --name=${NAME}-remote --rootfs=${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.0 --set=RECEIVER=${SECRET}-remote --system oci:atomic-test-system
test -d ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}-remote.0
test -e /etc/systemd/system/${NAME}-remote.service

# The rootfs should be a symlink
test -h ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}-remote/rootfs


# 4. Test uninstalling a system container
# Check uninstalling a remote container, and whether it affects the original rootfs
${ATOMIC} uninstall ${NAME}-remote
test -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}/rootfs
test \! -e /etc/systemd/system/${NAME}-remote.service
test \! -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}-remote
test \! -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}-remote.0

${ATOMIC} uninstall ${NAME}
test \! -e /etc/systemd/system/${NAME}.service
test \! -e /etc/tmpfiles.d/${NAME}.conf
test \! -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}
test \! -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.0


# 5. Expected failure tests for system container installs
# Installing a container with the same name fails
${ATOMIC} install --name=${NAME} --system atomic-test-system
${ATOMIC} install --name=${NAME} --system atomic-test-system > ${WORK_DIR}/failure.out
assert_matches "already present" ${WORK_DIR}/failure.out
${ATOMIC} uninstall ${NAME}

# Installing a container with environment variables with no default value fails,
# But succeeds when it is set

OUTPUT=$(! ${ATOMIC} install --name=${NAME} --system atomic-test-system-update 2>&1)
grep "unreplaced value for: ''VAR_WITH_NO_DEFAULT''" <<< $OUTPUT
${ATOMIC} install --name=${NAME} --system --set VAR_WITH_NO_DEFAULT=${SECRET}-new atomic-test-system-update
assert_matches ${SECRET}-new ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.0/config.json

teardown


# 6. installing from a dockertar
export NAME="test-dockertar-system-container-$$"
${ATOMIC} install --name=${NAME} --set=RECEIVER=${SECRET} --system dockertar:/${WORK_DIR}/atomic-test-system.tar
test -e /etc/tmpfiles.d/${NAME}.conf

test -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.0/${NAME}.service
test -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.0/tmpfiles-${NAME}.conf

teardown


# 7. install from local docker
export NAME="test-docker-system-container-$$"
${ATOMIC} install --name=${NAME} --set=RECEIVER=${SECRET} --system docker:atomic-test-system:latest
test -e /etc/tmpfiles.d/${NAME}.conf

test -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.0/${NAME}.service
test -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.0/tmpfiles-${NAME}.conf

teardown


# 8. install a run-once container

export NAME="Saturn"
${ATOMIC} pull --storage ostree docker:atomic-test-runonce:latest
${ATOMIC} install --system --name=${NAME} --set RECEIVER=Pluto atomic-test-runonce:latest > ${WORK_DIR}/ps.out
assert_matches "HI Pluto from Saturn" ${WORK_DIR}/ps.out

${ATOMIC} run --storage ostree --set RECEIVER=Pluto atomic-test-runonce:latest echo Hello World > ${WORK_DIR}/ps.out
assert_matches "Hello World" ${WORK_DIR}/ps.out

test \! -e /etc/systemd/system/${NAME}.service
test \! -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}
test \! -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.0

teardown

# 9. install and uninstall a container with a name ending in .0

export NAME="container.0"
${ATOMIC} pull --storage ostree docker:atomic-test-system:latest
${ATOMIC} install --system --name=${NAME} atomic-test-system:latest
${ATOMIC} uninstall ${NAME}

test \! -e /etc/systemd/system/${NAME}.service
test \! -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}
test \! -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.0
