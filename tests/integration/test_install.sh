#!/bin/bash
set -xe

# uncomment to test locally
# WORK_DIR=./test-run/
# mkdir -p $WORK_DIR
# ATOMIC="python2 ./atomic --debug"
# DOCKER="/usr/bin/docker"
export ATOMIC_INSTALL_JSON=${WORK_DIR}/install.json

# we want this image to be present in environment after this integration test is run
PERSISTENT_IMAGE="atomic-test-system-hostfs"
IMAGE="atomic-install-test-image"
CONTAINER_NAME="atomic-test-container"
NON_EXISTENT_IMAGE="non-existent-image"

# get rid of all RPMs lingering from other tests
LINGERING_SYSTEM_RPMS=$(rpm -qa | egrep "^atomic-container" || true)
if [ -n "${LINGERING_SYSTEM_RPMS}" ] ; then dnf remove -y "${LINGERING_SYSTEM_RPMS}"; fi

# test for correct error message if image doesn't exist
${ATOMIC} install --storage=docker ${NON_EXISTENT_IMAGE} 2>&1 | grep "RegistryInspectError: Unable to find ${NON_EXISTENT_IMAGE}"

# ensure ${PERSISTENT_IMAGE} survives `rmi`
${DOCKER} tag ${PERSISTENT_IMAGE} ${IMAGE}

teardown () {
    ${ATOMIC} uninstall --storage=docker --name=${CONTAINER_NAME} ${IMAGE}
    rpm -qa | grep ${CONTAINER_NAME} && { echo "package is installed when it should have been removed"; exit 1; }
    # ensure the $PERSISTENT_IMAGE is present
    ${DOCKER} inspect ${PERSISTENT_IMAGE} >/dev/null
    rm $(dirname $ATOMIC_INSTALL_JSON)/install.json.lock || true
    rm $(dirname $ATOMIC_INSTALL_JSON)/install.json || true
}
trap teardown EXIT

${ATOMIC} install --storage=docker --name=${CONTAINER_NAME} ${IMAGE}

RPM_NAME=$(rpm -qa | egrep "^atomic-container-${CONTAINER_NAME}")

FILE_LIST=$(rpm -ql $RPM_NAME)

egrep "^/usr/local/lib/secret-message$" <<< "${FILE_LIST}"

grep "\$RECEIVER" /usr/local/lib/secret-message

docker inspect --format='{{.Config.Labels}}' ${IMAGE} | grep "atomic.has_install_files"

# ensure that install.json file is valid json
INSTALL_JSON_CONTENT=$(python -m json.tool $ATOMIC_INSTALL_JSON)

grep "\"container_name\": \"${CONTAINER_NAME}\"" <<< "$INSTALL_JSON_CONTENT"
grep "\"system_package_nvra\": \"atomic-container-${CONTAINER_NAME}" <<< "$INSTALL_JSON_CONTENT"
grep '"/usr/local/lib/placeholder-file"' <<< "$INSTALL_JSON_CONTENT"
grep '"/usr/local/lib/secret-message"' <<< "$INSTALL_JSON_CONTENT"
grep '"/usr/local/lib/secret-message-template"' <<< "$INSTALL_JSON_CONTENT"

# test for correct error message when image is already installed
${ATOMIC} install --storage=docker --name=${CONTAINER_NAME} ${IMAGE} 2>&1 | grep "Image ${IMAGE} is already installed."
