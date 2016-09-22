#!/bin/bash -x
set -euo pipefail
IFS=$'\n\t'
./atomic_client.py Diff atomic-test-1 atomic-test-3
./atomic_client.py Diff atomic-test-1 atomic-test-3 True
./atomic_client.py Diff atomic-test-1 atomic-test-3 True True
./atomic_client.py Diff atomic-test-1 atomic-test-3 True True True


