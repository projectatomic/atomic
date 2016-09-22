#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

for i in $(ls $(dirname $0)/dbus/*.sh); do
    echo $i;
done
