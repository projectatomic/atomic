#!/bin/bash -x
set -euo pipefail
IFS=$'\n\t'
./atomic_client.py TrustShow
./atomic_client.py TrustDefaultPolicy reject
./atomic_client.py TrustDefaultPolicy accept
./atomic_client.py TrustDefaultPolicy foobar && echo "Should have failed"
./atomic_client.py TrustAdd registry.access.redhat.com reject
./atomic_client.py TrustShow | tail -1 | json_pp
./atomic_client.py TrustDelete registry.access.redhat.com web
./atomic_client.py TrustShow | tail -1 | json_pp

