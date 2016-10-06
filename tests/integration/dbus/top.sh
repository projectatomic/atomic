#!/bin/bash -x
set -euo pipefail
IFS=$'\n\t'
./atomic_client.py Top
docker run -d --name foobar alpine sleep 100
./atomic_client.py Top
./atomic_client.py ContainersDelete foobar False True


