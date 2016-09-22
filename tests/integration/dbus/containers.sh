#!/bin/bash -x
set -euo pipefail
IFS=$'\n\t'
./atomic_client.py ContainersList
docker create --name foobar alpine sleep 10
./atomic_client.py ContainersList
./atomic_client.py ContainersDelete foobar
./atomic_client.py ContainersList
./atomic_client.py ContainersTrim
