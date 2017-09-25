#!/bin/bash -x
set -euo pipefail
IFS=$'\n\t'

if test -e /run/ostree-booted; then
    exit 77
fi

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

# Skip the test if OSTree, runc are not installed, or atomic has not --install --system
ostree --version &>/dev/null || exit 77
runc --version &>/dev/null || exit 77

if runc --version | grep -q "version 0"; then
    exit 77
fi

touch /usr/lib/.writeable || exit 77
rm /usr/lib/.writeable

${ATOMIC}  install --help 2>&1 > help.out
grep -q -- --system help.out || exit 77

export ATOMIC_OSTREE_REPO=${WORK_DIR}/repo
export ATOMIC_OSTREE_CHECKOUT_PATH=${WORK_DIR}/checkout

${ATOMIC} pull --storage ostree docker:atomic-test-system-hostfs:latest

${ATOMIC} install --system --system-package=build --set RECEIVER=Venus atomic-test-system-hostfs

rpm -qip *-hostfs.rpm > rpm_info

assert_matches "atomic-container-atomic-test-system" rpm_info
assert_matches "^Version.*:.*1" rpm_info

rpm -qlp *-hostfs.rpm > rpm_file_list

assert_matches "/usr/local/lib/secret-message" rpm_file_list

rpm2cpio *-hostfs.rpm | cpio -iv --to-stdout usr/local/lib/secret-message-template > secret-message-template
assert_matches "Venus" secret-message-template

# A --system-package=build includes also the files for running
# the container itself, let's check it...
assert_matches "/usr/lib/containers/atomic/atomic-test-system" rpm_file_list

# now install the package to the system
ATOMIC_OSTREE_TEST_FORCE_IMAGE_ID=563246d74eda8a9337a5ad1f019d1c7aaa221c5288f16b975d230644017953b1 ${ATOMIC} install --system --system-package=yes atomic-test-system-hostfs

test -e /usr/local/placeholder-lib

teardown () {
    set +o pipefail
    ${ATOMIC} uninstall --storage ostree atomic-test-system-hostfs || true
    rm -rf /etc/systemd/system/atomic-test-system-*.service /etc/tmpfiles.d/atomic-test-system-*.conf
    ostree --repo=${ATOMIC_OSTREE_REPO} refs --delete ociimage &> /dev/null || true
}
trap teardown EXIT

RPM_NAME=$(rpm -qa | grep ^atomic-container-atomic-test-system)

rpm -ql $RPM_NAME > rpm_file_list

# --system-package=yes doesn't include the files of the container rootfs
assert_not_matches "/usr/lib/containers/atomic/atomic-test-system" rpm_file_list

for i in /usr/local/lib/renamed-atomic-test-system-hostfs /usr/local/lib/secret-message /usr/local/lib/secret-message-template;
do
    assert_matches $i rpm_file_list
    test -e $i
done

# This is not a template file, the $RECEIVER is not replaced
assert_matches "\$RECEIVER" /usr/local/lib/secret-message

# Instead this is a template file, the $RECEIVER must be replaced
assert_not_matches "\$RECEIVER" /usr/local/lib/secret-message-template
ATOMIC_OSTREE_TEST_FORCE_IMAGE_ID=a948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a448 ${ATOMIC} containers update atomic-test-system-hostfs

rpm -qa | grep ^atomic-container-atomic-test-system > rpm_name_upgrade
assert_matches "a948904f2" rpm_name_upgrade

${ATOMIC} containers rollback atomic-test-system-hostfs

rpm -qa | grep ^atomic-container-atomic-test-system > rpm_name_rollback
assert_matches "563246d7" rpm_name_rollback

# We try another container that install the same files to the host, this must fail, and check that
# there are no files left on the host as well.
if ${ATOMIC} install --system --system-package=yes --set RECEIVER=Mars --name atomic-test-system-broken atomic-test-system-hostfs; then
	assert_not_reached "Conflicting container installation succedeed"
fi

test -e /usr/local/placeholder-lib

test \! -e /etc/systemd/system/atomic-test-system-broken.service
test \! -e /etc/tmpfiles.d/atomic-test-system-broken.conf

${ATOMIC} uninstall --storage ostree atomic-test-system-hostfs

test \! -e /usr/local/placeholder-lib

# check that auto behaves in the same way as yes with this container.
${ATOMIC} install --system --system-package=auto --set RECEIVER=Jupiter atomic-test-system-hostfs
RPM_NAME=$(rpm -qa | grep ^atomic-container-atomic-test-system)

assert_matches "Jupiter" /usr/local/lib/secret-message-template

rpm -ql $RPM_NAME > rpm_file_list_2
cmp rpm_file_list rpm_file_list_2
${ATOMIC} uninstall --storage ostree atomic-test-system-hostfs

test \! -e /usr/local/placeholder-lib

for i in /usr/local/lib/renamed-atomic-test-system-hostfs /usr/local/lib/secret-message /usr/local/lib/secret-message-template;
do
    test \! -e $i
done

${ATOMIC} install --system --system-package=no atomic-test-system-hostfs
for i in /usr/local/lib/renamed-atomic-test-system-hostfs /usr/local/lib/secret-message /usr/local/lib/secret-message-template;
do
    test -e $i
done
