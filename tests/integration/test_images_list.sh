#!/bin/bash -x
set -euo pipefail
IFS=$'\n\t'

# Test images listing and filtering functionality

IMAGE="atomic-test-1"
IMAGE_SECRET="atomic-test-secret"
TAGGED_IMAGE="local/at1"
RUNNING_CONTAINER="testContainerOut"

assert_not_reached() {
    echo $@ 1>&2
    exit 1

}

assert_matches() {
    if ! grep -q -e $@; then
    sed -e s',^,| ,' < $2
    assert_not_reached "Failed to match: " $@
    fi
}

assert_not_matches() {
    if grep -q -e $@; then
    sed -e s',^,| ,' < $2
    assert_not_reached "Matched: " $@
    fi
}

setup () {
    ${DOCKER} tag ${IMAGE} ${TAGGED_IMAGE}:latest
}

teardown () {
    set +e
    ${DOCKER} rm ${RUNNING_CONTAINER}
    ${DOCKER} rmi ${TAGGED_IMAGE}:latest
    set -e
}

trap teardown exit

setup

${ATOMIC} images list > ${WORK_DIR}/images.out
assert_matches ${IMAGE} ${WORK_DIR}/images.out
assert_matches ${IMAGE_SECRET} ${WORK_DIR}/images.out
assert_matches ${TAGGED_IMAGE} ${WORK_DIR}/images.out

# Testing --all
${ATOMIC} images list --all > ${WORK_DIR}/images.all.out
test $(wc -l < ${WORK_DIR}/images.out) -lt $(wc -l < ${WORK_DIR}/images.all.out)
assert_matches '<none>' ${WORK_DIR}/images.all.out

# Testing filters and used tag >
${ATOMIC} images list -f repo=${IMAGE} > ${WORK_DIR}/images.out
assert_matches ${IMAGE} ${WORK_DIR}/images.out
assert_not_matches ">  "${IMAGE} ${WORK_DIR}/images.out
${DOCKER} run --name=${RUNNING_CONTAINER} ${IMAGE}
${ATOMIC} images list -f repo=${IMAGE} > ${WORK_DIR}/images.out
assert_matches ">  "${IMAGE} ${WORK_DIR}/images.out

${ATOMIC} images list -f type=docker > ${WORK_DIR}/images.out
assert_matches ${IMAGE} ${WORK_DIR}/images.out
${ATOMIC} images list -f repo=non-existing-repo > ${WORK_DIR}/images.out
assert_not_matches ${IMAGE} ${WORK_DIR}/images.out
${ATOMIC} images list -f repo=${IMAGE} -f type=docker > ${WORK_DIR}/images.out
assert_matches ${IMAGE} ${WORK_DIR}/images.out
assert_not_matches ${IMAGE_SECRET} ${WORK_DIR}/images.out

OUTPUT=$(! ${ATOMIC} images list -f not-a-filter=${IMAGE} 2>&1)
grep "not valid" <<< $OUTPUT

# Testing noheading/no-trunc
${ATOMIC} images list --noheading > ${WORK_DIR}/images.out
assert_not_matches 'REPOSITORY' ${WORK_DIR}/images.out

IMAGE_ID=$(${DOCKER} images --no-trunc | grep ${IMAGE} | awk '{print $3}' | cut -d ":" -f 2)
${ATOMIC} images list --no-trunc > ${WORK_DIR}/images.out
assert_matches ${IMAGE_ID} ${WORK_DIR}/images.out

# Testing quiet/json
${ATOMIC} images list -q > ${WORK_DIR}/images.out
assert_not_matches ${IMAGE} ${WORK_DIR}/images.out
assert_matches ${IMAGE_ID:0:12} ${WORK_DIR}/images.out

${ATOMIC} images list --json > ${WORK_DIR}/images.out
assert_matches ${IMAGE_ID} ${WORK_DIR}/images.out
assert_matches ${IMAGE} ${WORK_DIR}/images.out

# Test that filters work together
${ATOMIC} images list -a -q --no-trunc -f repo=${IMAGE} -f type=docker > ${WORK_DIR}/images.out
assert_matches ${IMAGE_ID} ${WORK_DIR}/images.out

# Check that the tagged image is being displayed
${ATOMIC} images list > ${WORK_DIR}/images.out
assert_matches ${TAGGED_IMAGE} ${WORK_DIR}/images.out
${ATOMIC} images list --json > ${WORK_DIR}/images.out
assert_matches ${TAGGED_IMAGE} ${WORK_DIR}/images.out
${ATOMIC} images list -f repo=${TAGGED_IMAGE} > ${WORK_DIR}/images.out
assert_matches ${TAGGED_IMAGE} ${WORK_DIR}/images.out
${ATOMIC} images list -f repo=${TAGGED_IMAGE} -q --no-trunc> ${WORK_DIR}/images.out
assert_matches ${IMAGE_ID} ${WORK_DIR}/images.out
