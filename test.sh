#!/bin/sh -x -e
atomic uninstall busybox
atomic install busybox
atomic uninstall busybox
atomic run --spc busybox /bin/ps
atomic run busybox /bin/ps
atomic run busybox /bin/sh
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
