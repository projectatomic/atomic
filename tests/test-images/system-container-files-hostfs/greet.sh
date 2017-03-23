#/bin/sh

printf "HTTP/1.1 200 OK\r\n"
printf "Connection: Close\r\n"
printf "\r\n"

printf "Hi $RECEIVER from container $NAME with UUID=$UUID\r\n"
