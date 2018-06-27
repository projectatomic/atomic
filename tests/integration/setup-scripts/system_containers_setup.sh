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


# Skip the test if:
# 1. OSTree or runc are not installed
# 2. the version of runc is too low
# 3. atomic has not --install --system
# 4. skopeo copy to ostree fails

ostree --version &>/dev/null || exit 77
runc --version &>/dev/null || exit 77

if runc --version | grep -q "version 0"; then
    exit 77
fi


${ATOMIC}  install --help 2>&1 > help.out
grep -q -- --system help.out || exit 77

export PYTHON=${PYTHON:-/usr/bin/python}
export ATOMIC_OSTREE_REPO=${WORK_DIR}/repo
export ATOMIC_OSTREE_CHECKOUT_PATH=${WORK_DIR}/checkout
export NAME="test-system-container-$$"

ostree --repo=$ATOMIC_OSTREE_REPO init

if test -n "$SKOPEO_NO_OSTREE"; then
    exit 77
fi

# This is to prevent the case where the ostree checkout path
# can be non-existent when no container installation happens prior
mkdir -p $ATOMIC_OSTREE_CHECKOUT_PATH
