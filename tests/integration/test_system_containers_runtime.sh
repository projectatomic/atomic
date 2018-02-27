#!/bin/bash -x
set -euo pipefail
IFS=$'\n\t'

. ./tests/integration/setup-scripts/system_containers_setup.sh

# The container runtime test of system containers, covers:
# 1. Starting the container with systemctl
# 2. Stopping the container with systemctl
# 3. Container list functionality
# 4. Container states
# 5. Starting/stopping the container with run/stop
# 6. Updating a container
# 7. Rolling back a container
# 8. Repeated updates/rollbacks
# 9. Update --rebase
# 10. Updating/rolling back a container with a remote rootfs
# 11. Verify --runtime is honored

setup () {
    ${ATOMIC} pull --storage ostree docker:atomic-test-system:latest
    ${ATOMIC} pull --storage ostree docker:atomic-test-system-update:latest
    docker tag atomic-test-system:latest atomic-test-system-new:latest
}

teardown () {
    set +o pipefail

    # Do not leave the runc container in any case
    runc kill ${NAME} 9 &> /dev/null || true
    runc delete ${NAME} &> /dev/null  || true
    runc kill ${NAME}-new 9 &> /dev/null || true
    runc delete ${NAME}-new &> /dev/null  || true

    # Ensure there is no systemd service left running
    systemctl stop ${NAME} &> /dev/null || true
    systemctl disable ${NAME} &> /dev/null || true
    systemctl stop ${NAME}-new &> /dev/null || true
    systemctl disable ${NAME}-new &> /dev/null || true
    rm -rf /etc/systemd/system/${NAME}.service || true
    rm -rf /etc/systemd/system/${NAME}-new.service || true
    rm -rf /etc/tmpfiles.d/${NAME}.conf || true
    rm -rf /etc/tmpfiles.d/${NAME}-new.conf || true

    # Delete all images from ostree
    ostree --repo=${ATOMIC_OSTREE_REPO} refs --delete ociimage &> /dev/null || true
}

trap teardown EXIT

OUTPUT=$(/bin/true)

setup

# 1. Install a system container and start/stop the container with systemctl
${ATOMIC} install --name=${NAME} --set=RECEIVER=${SECRET} --system atomic-test-system
${ATOMIC} run --storage ostree ${NAME} echo hello world < /dev/null > ${WORK_DIR}/status.out
assert_matches "hello world" ${WORK_DIR}/status.out

systemctl start ${NAME}.service

${ATOMIC} run --storage ostree ${NAME} echo hello world again < /dev/null > ${WORK_DIR}/status.out
assert_matches "hello world again" ${WORK_DIR}/status.out

${ATOMIC} run --runtime /usr/bin/runc --storage ostree ${NAME} echo hello world < /dev/null > ${WORK_DIR}/status.out
assert_matches "hello world" ${WORK_DIR}/status.out

# Check the service is running
systemctl status ${NAME}.service > ${WORK_DIR}/status.out
assert_matches "Active: active (running)" ${WORK_DIR}/status.out
sleep 0.5s


# 2. Stop the service and check that it stops successfully
systemctl stop ${NAME}.service
OUTPUT=$(! systemctl status ${NAME}.service 2>&1)
grep "Active: inactive" <<< $OUTPUT
sleep 0.5s


# 3. Test container list functionality
systemctl start ${NAME}.service
${ATOMIC} containers list > ${WORK_DIR}/ps.out
assert_matches "/usr/bin/r" ${WORK_DIR}/ps.out
assert_matches "running" ${WORK_DIR}/ps.out
assert_matches "ostree" ${WORK_DIR}/ps.out
assert_matches "runc" ${WORK_DIR}/ps.out

${ATOMIC} containers list --no-trunc > ${WORK_DIR}/ps.out
assert_matches "test-system" ${WORK_DIR}/ps.out
${ATOMIC} containers list --json > ${WORK_DIR}/ps.out
assert_matches ${NAME} ${WORK_DIR}/ps.out
${ATOMIC} containers list --all > ${WORK_DIR}/ps.out
assert_matches "test-system" ${WORK_DIR}/ps.out
${ATOMIC} containers list --all --no-trunc > ${WORK_DIR}/ps.out
assert_matches ${NAME} ${WORK_DIR}/ps.out
${ATOMIC} containers list --filter image=atomic-test-system > ${WORK_DIR}/ps.out
assert_matches "atomic-test-system" ${WORK_DIR}/ps.out
${ATOMIC} containers list --no-trunc --filter backend=ostree > ${WORK_DIR}/ps.out
assert_matches ${NAME} ${WORK_DIR}/ps.out
${ATOMIC} containers list --quiet > ${WORK_DIR}/ps.out
assert_not_matches "CONTAINER ID" ${WORK_DIR}/ps.out
${ATOMIC} containers list --no-trunc --quiet > ${WORK_DIR}/ps.out
assert_matches ${NAME} ${WORK_DIR}/ps.out

${ATOMIC} containers list -aq --no-trunc --filter container=non-existing-system > ${WORK_DIR}/ps.out
assert_not_matches "test-system" ${WORK_DIR}/ps.out


# 4. Testing for container states
${ATOMIC} containers list --all | grep "test-system" > ${WORK_DIR}/ps.out
assert_matches "running" ${WORK_DIR}/ps.out

# TODO: commented out for sometimes-failing fedora cloud case
# A duplicate will fail due to using the same port
# ${ATOMIC} install --name=${NAME}-new --system atomic-test-system
# systemctl start ${NAME}-new
# ${ATOMIC} containers list --all --no-trunc | grep ${NAME}-new > ${WORK_DIR}/ps.out
# assert_matches "failed" ${WORK_DIR}/ps.out
# ${ATOMIC} uninstall ${NAME}-new

systemctl stop ${NAME}
${ATOMIC} containers list --all --no-trunc | grep ${NAME} > ${WORK_DIR}/ps.out
assert_matches "inactive" ${WORK_DIR}/ps.out


# 5. Start/stop the container with run/stop
${ATOMIC} run ${NAME}
${ATOMIC} containers list --all --no-trunc | grep ${NAME} > ${WORK_DIR}/ps.out
assert_matches "running" ${WORK_DIR}/ps.out
${ATOMIC} stop ${NAME}
${ATOMIC} containers list --all --no-trunc | grep ${NAME} > ${WORK_DIR}/ps.out
assert_matches "inactive" ${WORK_DIR}/ps.out


# 6. Update the container
# Attempting to update without changes will return failure
${ATOMIC} containers update ${NAME} > ${WORK_DIR}/update.out
assert_matches "Latest version already installed" ${WORK_DIR}/update.out

# Updating a container will create a new checkout at ${NAME}.1
${ATOMIC} containers update --set=PORT=8082 ${NAME}
test -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.1/${NAME}.service
test -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.1/tmpfiles-${NAME}.conf
test -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.1/rootfs

# Check that ${NAME} links to the new deployment
readlink ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME} > ${WORK_DIR}/link.out
assert_matches ${NAME}.1 ${WORK_DIR}/link.out

# Variables are updated/preserved correctly
assert_matches ${SECRET} ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.1/config.json
assert_matches 8082 ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.1/config.json
UUID=$(cat ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.0/info | $PYTHON -c 'import json, sys; print(json.loads(sys.stdin.read())["values"]["UUID"])')
echo $UUID | egrep "[[:alnum:]]{8}-[[:alnum:]]{4}-[[:alnum:]]{4}-[[:alnum:]]{4}-[[:alnum:]]{12}"
UUID_AFTER_UPDATE=$(cat ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.1/info | $PYTHON -c 'import json, sys; print(json.loads(sys.stdin.read())["values"]["UUID"])')
echo $UUID_AFTER_UPDATE | egrep "[[:alnum:]]{8}-[[:alnum:]]{4}-[[:alnum:]]{4}-[[:alnum:]]{4}-[[:alnum:]]{12}"
assert_equal $UUID $UUID_AFTER_UPDATE

# The updated container can be started correctly
systemctl start ${NAME}
${ATOMIC} containers list --all --no-trunc | grep ${NAME} > ${WORK_DIR}/ps.out
assert_matches "running" ${WORK_DIR}/ps.out
systemctl stop ${NAME}


# 7. Rollback the container to the previous deployment
${ATOMIC} containers rollback ${NAME}
readlink ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME} > ${WORK_DIR}/link.out
assert_matches ${NAME}.0 ${WORK_DIR}/link.out
systemctl start ${NAME}
${ATOMIC} containers list --all --no-trunc | grep ${NAME} > ${WORK_DIR}/ps.out
assert_matches "running" ${WORK_DIR}/ps.out

# Check that old environment variables are correct
assert_matches 8081 ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}/config.json
assert_matches ${SECRET} ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}/config.json


# 8. Repeated updates/rollbacks
# Rollback to the new deployment again
${ATOMIC} containers rollback ${NAME}
readlink ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME} > ${WORK_DIR}/link.out
assert_matches ${NAME}.1 ${WORK_DIR}/link.out

# Check that the container is still running
${ATOMIC} containers list --all --no-trunc | grep ${NAME} > ${WORK_DIR}/ps.out
assert_matches "running" ${WORK_DIR}/ps.out

# Check that updating again creates a new checkout at ${NAME}.0
${ATOMIC} containers update ${NAME} --set PORT=8083 > ${WORK_DIR}/update.out
readlink ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME} > ${WORK_DIR}/link.out
assert_matches ${NAME}.0 ${WORK_DIR}/link.out

# Updating a running container will keep the container running
${ATOMIC} containers list --all --no-trunc | grep ${NAME} > ${WORK_DIR}/ps.out
assert_matches "running" ${WORK_DIR}/ps.out

${ATOMIC} images update --storage=ostree --all 2> ${WORK_DIR}/update_all_images.out
assert_matches "skipping" ${WORK_DIR}/update_all_images.out
${ATOMIC} containers update --all


# 9. Update --rebase
# rebasing to the same image fails
${ATOMIC} containers update ${NAME} --rebase atomic-test-system > ${WORK_DIR}/update.out
assert_matches "Latest version already installed" ${WORK_DIR}/update.out
readlink ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME} > ${WORK_DIR}/link.out
assert_matches ${NAME}.0 ${WORK_DIR}/link.out

# Updating to a new image fails with missing variables
OUTPUT=$(! ${ATOMIC} containers update ${NAME} --rebase atomic-test-system-update 2>&1)
grep "unreplaced value for: ''VAR_WITH_NO_DEFAULT''" <<< $OUTPUT
readlink ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME} > ${WORK_DIR}/link.out
assert_matches ${NAME}.0 ${WORK_DIR}/link.out

# Update --rebase can update to another image
# Update --rebase works with --set
${ATOMIC} containers update ${NAME} --rebase atomic-test-system-update --set VAR_WITH_NO_DEFAULT=${SECRET}-manual
assert_matches ${SECRET}-manual ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}/config.json
${ATOMIC} containers list --all --no-trunc | grep ${NAME} > ${WORK_DIR}/ps.out
assert_matches "running" ${WORK_DIR}/ps.out

# Rolling back the container preserves old variables and image
${ATOMIC} containers rollback ${NAME}
assert_matches ${SECRET} ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}/config.json
assert_matches 8083 ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}/config.json

# Update can rebase to an image not present in the repository.
${ATOMIC} containers update ${NAME} --rebase docker:atomic-test-system-new:latest > ${WORK_DIR}/update.out


# 10. Updating/rolling back an image with a remote rootfs works
${ATOMIC} install --system --name ${NAME}-new --set RECEIVER=${SECRET} --rootfs ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME} atomic-test-system
systemctl start ${NAME}-new
${ATOMIC} containers list --all --no-trunc | grep ${NAME}-new > ${WORK_DIR}/ps.out
assert_matches "running" ${WORK_DIR}/ps.out

${ATOMIC} containers update --set RECEIVER=new-receiver ${NAME}-new
assert_matches "new-receiver" ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}-new/config.json

${ATOMIC} containers rollback ${NAME}-new
assert_matches ${SECRET} ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}-new/config.json

# 11. Test --runtime
${ATOMIC} uninstall ${NAME}-new
${ATOMIC} install --name=${NAME}-new --runtime=/bin/ls --set=RECEIVER=${SECRET} --system atomic-test-system
assert_matches /bin/ls /etc/systemd/system/${NAME}-new.service

${ATOMIC} uninstall ${NAME}-new
OUTPUT=$(! ${ATOMIC} install --name=${NAME}-new --runtime=/does/not/exist --set=RECEIVER=${SECRET} --system atomic-test-system 2>&1)
grep "is not installed" <<< $OUTPUT
