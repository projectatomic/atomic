#!/bin/bash -x
set -euo pipefail
IFS=$'\n\t'

DOCKERTAR_SHA256_HELPER=${ATOMIC_LIBEXEC}/dockertar-sha256-helper

T1="${DOCKERTAR_SHA256_HELPER} <(seq 2000)"
EXPECTED_T1="cc27c088933fbaf64a2374cd1ff39f38df03badac18861f2c3f16e3d78be8f93"

T2="${DOCKERTAR_SHA256_HELPER} <(head -c 4096 /dev/zero)"
EXPECTED_T2="d84f7b85b256694bcb87b6c01777871a2e928fee54b4013e87d04ec4ff844053"

T3="${DOCKERTAR_SHA256_HELPER} <(head -c 4096 /dev/zero | tr '\0' a)"
EXPECTED_T3="9d974f75dec805bd50bcf0abb82c7e785c3822a3620987b42253ffe78e703639"

T4="${DOCKERTAR_SHA256_HELPER} <(head -c 500 /dev/zero | tr '\0' a)"
EXPECTED_T4="1d83d97035d26a51b6d85ad57d2894afdd74121752b296be874512fd9d85a370"

validTest() {
    test $(eval $(eval echo \$${1})) = $(eval echo '$EXPECTED_'$1) || return 1
    return 0
}

for CURRENT_TEST in T1 T2 T3 T4; do
    validTest $CURRENT_TEST
    if [[ $? -ne 0 ]]; then
        exit 1
    fi
done
