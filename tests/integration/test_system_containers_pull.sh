#!/bin/bash -x
set -euo pipefail
IFS=$'\n\t'

. ./tests/integration/setup-scripts/system_containers_setup.sh

# The pull test of system containers, mainly to
# test out the new usage of skopeo copy, it covers
# 1: pull dockertar with a custom name (dockertar:customimagename)
# 2: pull dockertar with same image name (dockertar:image)
# 3: pull from docker daemon (docker:)

teardown() {
    set +o pipefail

    # For now, we only delete the refs from ostree
    ostree --repo=${ATOMIC_OSTREE_REPO} refs --delete ociimage &> /dev/null || true

    # Remove the generated tar file to avoid affecting other tests
    rm -rf ${WORK_DIR}/atomic-test-random-name || true
    rm -rf ${WORK_DIR}/atomic-test-system || true
}

check_image_existence() {
    image_name=$1; shift
    ref_name=$1; shift

    # Check for image appearance
    ${ATOMIC} images list -f type=ostree > ${WORK_DIR}/images.out
    assert_matches $image_name ${WORK_DIR}/images.out

    # Check for ostree refs
    ostree --repo=${ATOMIC_OSTREE_REPO} refs > ${WORK_DIR}/ostree_refs.out
    assert_matches $ref_name ${WORK_DIR}/ostree_refs.out
}

cleanup_image() {
    image_name=$1
    ${ATOMIC} --assumeyes images delete -f --storage ostree $image_name
    ${ATOMIC} images prune
    ${ATOMIC} images list -f type=ostree > ${WORK_DIR}/images.out
    assert_not_matches $image_name ${WORK_DIR}/images.out
}

trap teardown EXIT

OUTPUT=$(/bin/true)

# 1: Pull docker tar and check from image list
docker save -o ${WORK_DIR}/atomic-test-random-name atomic-test-system
${ATOMIC} pull --storage ostree dockertar:/${WORK_DIR}/atomic-test-random-name
check_image_existence "atomic-test-system" "ociimage/atomic-test-system_3Alatest"
cleanup_image "atomic-test-system"

# 2: Pull docker tar with default name and check image
docker save atomic-test-system > ${WORK_DIR}/atomic-test-system
${ATOMIC} pull --storage ostree dockertar:/${WORK_DIR}/atomic-test-system
check_image_existence "atomic-test-system" "ociimage/atomic-test-system_3Alatest"
cleanup_image "atomic-test-system"

# 3: Pull from local docker and check
${ATOMIC} pull --storage ostree docker:atomic-test-system:latest
check_image_existence "atomic-test-system" "ociimage/atomic-test-system_3Alatest"
cleanup_image "atomic-test-system"

