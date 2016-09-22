#!/bin/bash -x
set -euo pipefail
IFS=$'\n\t'
./atomic_client.py MountImage atomic-test-3 /mnt
./atomic_client.py UnmountImage /mnt

