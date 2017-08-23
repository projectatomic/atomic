#!/bin/bash -x
set -euo pipefail
IFS=$'\n\t'

DOCKERTAR_SHA256_HELPER=${ATOMIC_LIBEXEC}/dockertar-sha256-helper

T1="${DOCKERTAR_SHA256_HELPER} <(seq 2000)"
EXPECTED_T1="0a611a63a42de01613a6d6eb296e469c1f5c3229b36df014e6434e643e2c827e"

T2="${DOCKERTAR_SHA256_HELPER} <(head -c 4096 /dev/zero)"
EXPECTED_T2="afc5adbe422839336d3a77a5a0267ad740461f4f4db9af9eaa2520107a838f1e"

T3="${DOCKERTAR_SHA256_HELPER} <(head -c 4096 /dev/zero | tr '\0' a)"
EXPECTED_T3="9e4cd3ee84c4916d40f0067b9aa8c70bfce7067510bdd8346c0d62cf30e568e5"

T4="${DOCKERTAR_SHA256_HELPER} <(head -c 500 /dev/zero | tr '\0' a)"
EXPECTED_T4="f5dd206f74a9f913b29d495f7d3c2917d221131a7d261ec4293b48df67cdb6bf"

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
