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

assert_equal() {
    if ! test $1 = $2; then
	assert_not_reached "Failed: not equal " $1 $2
    fi
}

OUTPUT=$(/bin/true)
PYTHON=${PYTHON:-/usr/bin/python}

# Skip the test if OSTree, runc, rpmbuild are not installed, or atomic has not --install --system
ostree --version &>/dev/null || exit 77
runc --version &>/dev/null || exit 77
rpmbuild --version &>/dev/null || exit 77

${ATOMIC}  install --help 2>&1 > help.out
grep -q -- --system help.out || exit 77

export ATOMIC_OSTREE_REPO=${WORK_DIR}/repo
export ATOMIC_OSTREE_CHECKOUT_PATH=${WORK_DIR}/checkout

${ATOMIC} pull --storage ostree docker:atomic-test-system-hostfs:latest

${ATOMIC} install --system --system-package=build atomic-test-system-hostfs

rpm -qip atomic-container-atomic-test-system-*.x86_64.rpm > rpm_info

assert_matches "atomic-container-atomic-test-system" rpm_info
assert_matches "^Release.*:.*1" rpm_info

rpm -qlp atomic-container-atomic-test-system-*.x86_64.rpm > rpm_file_list

assert_matches "/usr/local/lib/secret-message" rpm_file_list

# A --system-package=build includes also the files for running
# the container itself, let's check it...
assert_matches "/usr/lib/containers/atomic/atomic-test-system" rpm_file_list

# now install the package to the system
${ATOMIC} install --system --system-package=yes atomic-test-system-hostfs

teardown () {
    set +o pipefail
    ${ATOMIC} uninstall --storage ostree atomic-test-system-hostfs
    exit 0
}
trap teardown EXIT

RPM_NAME=$(rpm -qa | grep ^atomic-container-atomic-test-system)

rpm -ql $RPM_NAME > rpm_file_list

# --system-package=yes doesn't include the files of the container rootfs
assert_not_matches "/usr/lib/containers/atomic/atomic-test-system" rpm_file_list

for i in /usr/lib/systemd/system/atomic-test-system.service \
         /usr/lib/tmpfiles.d/atomic-test-system.conf \
         /usr/local/lib/renamed-atomic-test-system \
         /usr/local/lib/secret-message \
         /usr/local/lib/secret-message-template;
do
    assert_matches $i rpm_file_list
done

# This is not a template file, the $RECEIVER is not replaced
assert_matches "\$RECEIVER" /usr/local/lib/secret-message

# Instead this is a template file, the $RECEIVER must be replaced
assert_not_matches "\$RECEIVER" /usr/local/lib/secret-message-template
assert_matches "Hello World" /usr/local/lib/secret-message
