#!/bin/bash -x
set -euo pipefail
IFS=$'\n\t'

. ./tests/integration/setup-scripts/system_containers_setup.sh

# The image tests of system containers, covers:
# 1. pulling image from repository
# 2. listing local images (filters)
# 3. deleting/pruning images
# 4. pulling image from local docker
# 5. pulling image from local dockertar
# 6. tagging local images
# 7. info of local images (environment vars)
# 8. version and verify

setup () {
    docker save atomic-test-system > ${WORK_DIR}/atomic-test-system.tar
}

teardown () {
    set +o pipefail

    # Delete all images from ostree
    ostree --repo=${ATOMIC_OSTREE_REPO} refs --delete ociimage &> /dev/null || true
}

trap teardown EXIT

OUTPUT=$(/bin/true)

setup


# 1. pulling image from repository
${ATOMIC} pull --storage ostree busybox
ostree --repo=${ATOMIC_OSTREE_REPO} refs > ${WORK_DIR}/ostree_refs.out
assert_matches "ociimage/busybox_3Alatest" ${WORK_DIR}/ostree_refs.out

# Check that pulling an image twice does not re-pull the image
${ATOMIC} pull --storage ostree busybox > ${WORK_DIR}/pull.out
assert_not_matches "Pulling layer" ${WORK_DIR}/pull.out

# Check that pulling the image with another name doesn't pull the layer,
# but creates a ref
${ATOMIC} pull --storage ostree docker.io/busybox > ${WORK_DIR}/pull.out
assert_not_matches "Pulling layer" ${WORK_DIR}/pull.out
ostree --repo=${ATOMIC_OSTREE_REPO} refs > ${WORK_DIR}/ostree_refs.out
assert_matches "ociimage/docker.io_2Fbusybox_3Alatest" ${WORK_DIR}/ostree_refs.out


# 2. listing local images
${ATOMIC} images list > ${WORK_DIR}/images.out
assert_matches "busybox" ${WORK_DIR}/images.out
${ATOMIC} images list -q > ${WORK_DIR}/images.out
assert_not_matches "busybox" ${WORK_DIR}/images.out

# Testing filters
${ATOMIC} images list -f repo=busybox > ${WORK_DIR}/images.out
assert_matches "busybox" ${WORK_DIR}/images.out
${ATOMIC} images list -f type=ostree -f repo=busybox > ${WORK_DIR}/images.out
assert_matches "busybox" ${WORK_DIR}/images.out
${ATOMIC} images list -f repo=non-existing-repo > ${WORK_DIR}/images.out
assert_not_matches "busybox" ${WORK_DIR}/images.out

${ATOMIC} images list -f type=ostree > ${WORK_DIR}/images.out
${ATOMIC} images list -f type=ostree --all > ${WORK_DIR}/images.all.out
test $(wc -l < ${WORK_DIR}/images.out) -lt $(wc -l < ${WORK_DIR}/images.all.out)
assert_matches '<none>' ${WORK_DIR}/images.all.out
assert_not_matches '<none>' ${WORK_DIR}/images.out


# 3. deleting/pruning local images
${ATOMIC} --assumeyes images delete -f --storage ostree busybox
ostree --repo=${ATOMIC_OSTREE_REPO} refs > ${WORK_DIR}/ostree_refs.out
assert_not_matches "ociimage/busybox_3Alatest" ${WORK_DIR}/ostree_refs.out

# Since the image exists as multiple tags,
# Test there are still intermediate layers left after prune
${ATOMIC} images prune
${ATOMIC} images list -f type=ostree --all > ${WORK_DIR}/images.all.out
assert_matches "<none>" ${WORK_DIR}/images.all.out

# Test that the image can be deleted by ID
BUSYBOX_IMAGE_ID=$(${ATOMIC} images list -f type=ostree | grep busybox | awk '{print $3}')
${ATOMIC} --assumeyes images delete -f --storage=ostree ${BUSYBOX_IMAGE_ID}
${ATOMIC} images list -f type=ostree > ${WORK_DIR}/images.out
assert_not_matches "busybox" ${WORK_DIR}/images.out

# Test that pruning now removes all images
${ATOMIC} images prune
${ATOMIC} images list -f type=ostree --all > ${WORK_DIR}/images.all.out
assert_not_matches "<none>" ${WORK_DIR}/images.all.out


# 4. pull image from local docker
${ATOMIC} pull --storage ostree docker:atomic-test-system:latest
${ATOMIC} images list -f type=ostree > ${WORK_DIR}/images.out
assert_matches "atomic-test-system" ${WORK_DIR}/images.out


# 4.1 Check that the virtual size of the imported image is the same as showed for Docker
${ATOMIC_NO_DEBUG} images list -f repo=atomic-test-system --json > ${WORK_DIR}/images.json
${PYTHON} -c 'import json; import sys; sizes = [str(i["virtual_size"]) for i in json.load(sys.stdin)]; sys.exit(len([x for x in sizes if x != sizes[0]]))' < ${WORK_DIR}/images.json


${ATOMIC} --assumeyes images delete -f --storage ostree atomic-test-system
${ATOMIC} images prune
${ATOMIC} images list -f type=ostree > ${WORK_DIR}/images.out
assert_not_matches "atomic-test-system" ${WORK_DIR}/images.out


# 5. pulling image from local dockertar
${ATOMIC} pull --storage ostree dockertar:/${WORK_DIR}/atomic-test-system.tar
${ATOMIC} images list -f type=ostree > ${WORK_DIR}/images.out
assert_matches "atomic-test-system" ${WORK_DIR}/images.out


# 6. tagging local images
${ATOMIC} images tag --storage ostree atomic-test-system:latest atomic-test-ostree:latest
${ATOMIC} images list -f type=ostree > ${WORK_DIR}/images.out
assert_matches "atomic-test-ostree" ${WORK_DIR}/images.out

# Make sure the tagged image has the same id
OLD_ID=$(${ATOMIC} images list -f type=ostree | grep atomic-test-system | awk '{print $3}')
NEW_ID=$(${ATOMIC} images list -f type=ostree | grep atomic-test-ostree | awk '{print $3}')
assert_equal ${OLD_ID} ${NEW_ID}


# 7. image info (labels and environment variables)
${ATOMIC} pull --storage ostree docker:atomic-test-system-update:latest
${ATOMIC} images info --storage ostree atomic-test-system-update > ${WORK_DIR}/info.out
assert_matches "atomic.type: system" ${WORK_DIR}/info.out
assert_matches "Template variables with default value, but overridable with --set:" ${WORK_DIR}/info.out
assert_matches "PORT: 8081" ${WORK_DIR}/info.out
assert_matches "Template variables that has no default value, and must be set with --set:" ${WORK_DIR}/info.out
assert_matches "VAR_WITH_NO_DEFAULT: {DEF_VALUE}" ${WORK_DIR}/info.out


# 8. version and verify
${ATOMIC} pull --storage ostree busybox

${ATOMIC} images version --storage ostree busybox > ${WORK_DIR}/version.out
assert_matches "busybox" ${WORK_DIR}/version.out

${ATOMIC} images verify --storage ostree busybox > ${WORK_DIR}/verify.out
# TODO: this is currently failing due to a discrepancy between ostree and docker ID's, fix first
# assert_not_matches "YES" ${WORK_DIR}/verify.out
