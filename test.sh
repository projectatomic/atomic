#!/bin/bash -xe

atomic uninstall busybox || true
atomic install busybox
atomic uninstall busybox
atomic run --spc busybox /bin/ps
atomic run busybox /bin/ps
atomic run --name=atomic_test busybox sleep 6000
atomic run --name=atomic_test busybox ps 
atomic uninstall --name=atomic_test busybox
cat > Dockerfile <<EOF
FROM busybox
LABEL RUN /usr/bin/docker run -ti --rm IMAGE /bin/echo RUN
LABEL INSTALL /usr/bin/docker run -ti --rm IMAGE /bin/echo INSTALL
LABEL UNINSTALL /usr/bin/docker run -ti --rm IMAGE /bin/echo UNINSTALL
EOF
docker build -t atomic_busybox .
atomic run atomic_busybox
atomic install atomic_busybox
atomic uninstall atomic_busybox
rm -f Dockerfile
atomic uninstall busybox
