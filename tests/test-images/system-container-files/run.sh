#!/bin/sh

nc -k -l ${PORT:-8081} --sh-exec /usr/bin/greet.sh
