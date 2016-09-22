#!/bin/bash -x
set -euo pipefail
IFS=$'\n\t'
./atomic_client.py HostStatus
./atomic_client.py HostUpgrade
./atomic_client.py HostUpgradeDiff
./atomic_client.py HostRollback
./atomic_client.py HostRebase
./atomic_client.py HostDeploy
./atomic_client.py HostDeployPreview
./atomic_client.py HostUnlock
./atomic_client.py HostInstall
./atomic_client.py HostUninstall 

