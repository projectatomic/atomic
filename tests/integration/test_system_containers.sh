#!/bin/bash -x
set -euo pipefail
IFS=$'\n\t'

assert_not_reached() {
    echo $@ 1>&2
    exit 1
}

assert_not_matches() {
    if grep -q -e $@; then
	sed -e s',^,| ,' < $2
	assert_not_reached "Matched: " $@
    fi
}

assert_matches() {
    if ! grep -q -e $@; then
	sed -e s',^,| ,' < $2
	assert_not_reached "Failed to match: " $@
    fi
}

# Test scripts run with PWD=tests/..

# The test harness exports some variables into the environment during
# testing: PYTHONPATH (python module import path
#          WORK_DIR   (a directory that is safe to modify)
#          DOCKER     (the docker executable location)
#          ATOMIC     (an invocation of 'atomic' which measures code coverage)
#          SECRET     (a generated sha256 hash inserted into test containers)

# In addition, the test harness creates some images for use in testing.
#   See tests/test-images/

OUTPUT=$(/bin/true)

# Skip the test if OSTree or runc are not installed, or atomic has not --install --system
ostree --version &>/dev/null || exit 77
runc --version &>/dev/null || exit 77

${ATOMIC}  install --help 2>&1 > help.out
grep -q -- --system help.out || exit 77

export ATOMIC_OSTREE_REPO=${WORK_DIR}/repo
export ATOMIC_OSTREE_CHECKOUT_PATH=${WORK_DIR}/checkout

docker save atomic-test-system > ${WORK_DIR}/atomic-test-system.tar

${ATOMIC} pull dockertar:/${WORK_DIR}/atomic-test-system.tar

# Check that the branch is created in the OSTree repository
ostree --repo=${ATOMIC_OSTREE_REPO} refs > refs
assert_matches "ociimage/atomic-test-system-latest" refs

${ATOMIC} images list > ${WORK_DIR}/images
grep -q "atomic-test-system" ${WORK_DIR}/images
${ATOMIC} images list -a > ${WORK_DIR}/images
grep -q "atomic-test-system" ${WORK_DIR}/images
${ATOMIC} images list -f repo=atomic-test-system > ${WORK_DIR}/images
grep -q "atomic-test-system" ${WORK_DIR}/images
${ATOMIC} images list -f repo=non-existing-repo > ${WORK_DIR}/images
assert_not_matches "atomic-test-system" ${WORK_DIR}/images
${ATOMIC} images list -q > ${WORK_DIR}/images
assert_not_matches "atomic-test-system" ${WORK_DIR}/images

export NAME="test-system-container-$$"

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
    systemctl stop $NAME-remote &> /dev/null || true
    systemctl disable $NAME-remote &> /dev/null || true
    rm -rf /etc/systemd/system/${NAME}-remote.service || true
}

trap teardown EXIT

${ATOMIC} install --name=${NAME} --set=RECEIVER=${SECRET} --system oci:atomic-test-system
test -e /etc/tmpfiles.d/${NAME}.conf

test -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.0/${NAME}.service
test -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.0/tmpfiles-${NAME}.conf

systemctl start ${NAME}

${ATOMIC} update --container ${NAME} > update.out
assert_matches "Latest version already installed" update.out

${ATOMIC} containers list --no-trunc > ps.out
assert_matches "test-system" ps.out
${ATOMIC} containers list --json > ps.out
assert_matches "test-system" ps.out
${ATOMIC} containers list --all > ps.out
assert_matches "test-system" ps.out
${ATOMIC} containers list --all --no-trunc > ps.out
assert_matches "test-system" ps.out
${ATOMIC} containers list --no-trunc --filter id=test-system > ps.out
assert_matches "test-system" ps.out
${ATOMIC} containers list --no-trunc > ps.out
assert_matches "test-system" ps.out
${ATOMIC} containers list --no-trunc --quiet > ps.out
assert_matches "test-system" ps.out
${ATOMIC} containers list -aq --no-trunc --filter id=test-system > ps.out
assert_matches "test-system" ps.out
${ATOMIC} containers list -aq --no-trunc --filter id=non-existing-system > ps.out
assert_not_matches "test-system" ps.out

${ATOMIC} containers list --all --no-trunc --filter id=test-system | grep "test-system" > ps.out
# Check the command is included in the output
assert_matches "run.sh" ps.out

systemctl stop ${NAME}

${ATOMIC} containers list --all | grep "test-system" > ps.out
assert_matches "exited" ps.out

${ATOMIC} containers list --quiet > ps.out
assert_not_matches "test-system" ps.out

test -e /etc/systemd/system/${NAME}.service

# The value we set is exported into the config file
assert_matches ${SECRET} ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.0/config.json

# The default value $PORT specified in the manifest.json is exported
assert_matches 8081 ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.0/config.json

${ATOMIC} update --container ${NAME} > update.out
assert_matches "Latest version already installed" update.out

${ATOMIC} update --set=PORT=8082 --container ${NAME}
test -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.1/${NAME}.service
test -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.1/tmpfiles-${NAME}.conf

# Check that the same SECRET value is kept, and that $PORT gets the new value
assert_matches ${SECRET} ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.1/config.json
assert_matches 8082 ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.1/config.json

# Test if a container with a remote rootfs can be installed/updated
${ATOMIC} --debug install --name=${NAME}-remote --rootfs=${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.1 --set=RECEIVER=${SECRET}-remote --system oci:atomic-test-system
systemctl start ${NAME}-remote

${ATOMIC} --debug containers list --no-trunc > ps.out
assert_matches "remote" ps.out
test -e /etc/systemd/system/${NAME}-remote.service

# The rootfs should not exist
test \! -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}-remote.0/rootfs

# Values should still be able to be updated for remote containers
${ATOMIC} update --set=PORT=8083 --container ${NAME}-remote
assert_matches 8083 ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}-remote.1/config.json

mkdir ${WORK_DIR}/mount

# Test that mount and umount work

# Check that --live fails
OUTPUT=$(! ${ATOMIC} mount --live ${NAME} ${WORK_DIR}/mount 2>&1)
grep "do not support --live" <<< $OUTPUT

${ATOMIC} mount --shared ${NAME} ${WORK_DIR}/mount
${ATOMIC} umount ${WORK_DIR}/mount

# mount a container
${ATOMIC} mount ${NAME} ${WORK_DIR}/mount
test -e ${WORK_DIR}/mount/usr/bin/greet.sh
${ATOMIC} umount ${WORK_DIR}/mount

# mount an image
${ATOMIC} mount atomic-test-system ${WORK_DIR}/mount
test -e ${WORK_DIR}/mount/usr/bin/greet.sh
${ATOMIC} umount ${WORK_DIR}/mount

# Check uninstalling a remote container, and whether it affects the original rootfs
${ATOMIC} uninstall ${NAME}-remote
test -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}/rootfs
test \! -e /etc/systemd/system/${NAME}-remote.service
test \! -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}-remote
test \! -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}-remote.0
test \! -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}-remote.1

${ATOMIC} uninstall ${NAME}
test \! -e /etc/systemd/system/${NAME}.service
test \! -e /etc/tmpfiles.d/${NAME}.conf
test \! -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}
test \! -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.0
test \! -e ${ATOMIC_OSTREE_CHECKOUT_PATH}/${NAME}.1


${ATOMIC} pull docker.io/busybox
${ATOMIC} pull docker.io/busybox > second.pull.out
assert_not_matches "Pulling layer" second.pull.out

ostree --repo=${ATOMIC_OSTREE_REPO} refs > refs
assert_matches busybox refs
${ATOMIC} images delete -f busybox
ostree --repo=${ATOMIC_OSTREE_REPO} refs > refs
OUTPUT=$(! grep -c busybox refs)
if test $OUTPUT \!= 0; then
    exit 1
fi
${ATOMIC} pull docker.io/busybox
ostree --repo=${ATOMIC_OSTREE_REPO} refs | grep busybox

${ATOMIC} verify busybox > verify.out
assert_not_matches "contains images or layers that have updates" verify.out

image_digest=$(ostree --repo=${ATOMIC_OSTREE_REPO} show --print-metadata-key=docker.manifest ociimage/busybox-latest | sed -e"s|.*Digest\": \"sha256:\([a-z0-9]\+\).*|\1|" | head -c 12)
${ATOMIC} images list > images.out
grep "busybox.*$image_digest" images.out

${ATOMIC} images list -f type=system > images.out
${ATOMIC} images list -f type=system --all > images.all.out
test $(wc -l < images.out) -lt $(wc -l < images.all.out)
assert_matches '<none>' images.all.out
assert_not_matches '<none>' images.out

${ATOMIC} images delete -f busybox
${ATOMIC} images prune

# Test there are still intermediate layers left after prune
${ATOMIC} images list -f type=system --all > images.all.out
assert_matches "<none>" images.all.out

${ATOMIC} images delete -f atomic-test-system
${ATOMIC} images prune

# Test there are not intermediate layers left layers now
${ATOMIC} images list -f type=system --all > images.all.out
assert_not_matches "<none>" images.all.out

# Verify there are no branches left in the repository as well
ostree --repo=${ATOMIC_OSTREE_REPO} refs > refs
assert_not_matches "<none>" refs
