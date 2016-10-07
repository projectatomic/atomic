#!/bin/bash -x
set -euo pipefail
IFS=$'\n\t'
./atomic_client.py ImagesVersion '[ "atomic-test-1", "atomic-test-2" ]'
./atomic_client.py ImagesVersion '[ "atomic-test-1", "atomic-test-2" ]' True
./atomic_client.py ImagesPrune
./atomic_client.py ImagePull alpine
./atomic_client.py ImagesInfo alpine
./atomic_client.py ImagesDelete alpine True
./atomic_client.py ImagesHelp atomic-test-1
./atomic_client.py ImagesInfo atomic-test-1


