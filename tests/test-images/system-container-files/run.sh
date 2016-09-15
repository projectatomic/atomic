#!/bin/sh

nc --verbose -k -l ${PORT:-8081} --sh-exec /usr/bin/greet.sh &

cleanup ()
{
        kill -9 $!
        exit 0
}

trap cleanup SIGINT SIGTERM

wait $!
