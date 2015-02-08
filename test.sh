#!/bin/bash -xe
test_image() {
    IMAGE=$1
    ./atomic uninstall ${IMAGE} || true
    ./atomic install ${IMAGE}
    ./atomic uninstall ${IMAGE}
    ./atomic info ${IMAGE}
    ./atomic run --spc ${IMAGE} /bin/ps
    ./atomic run ${IMAGE} /bin/ps
    ./atomic run --name=atomic_test ${IMAGE} sleep 6000 &
    ./atomic run --name=atomic_test ${IMAGE} ps 
    ./atomic uninstall --name=atomic_test ${IMAGE}
}
test_image busybox
test_image fedora

cat > Dockerfile <<EOF
FROM busybox
EOF
docker build -t atomic_busybox .
./atomic info atomic_busybox
cat > Dockerfile <<EOF
FROM busybox
LABEL RUN /usr/bin/docker run -ti --rm IMAGE /bin/echo RUN
LABEL INSTALL /usr/bin/docker run -ti --rm IMAGE /bin/echo INSTALL
LABEL UNINSTALL /usr/bin/docker run -ti --rm IMAGE /bin/echo UNINSTALL
EOF
docker build -t atomic_busybox .
./atomic run atomic_busybox
./atomic install atomic_busybox
./atomic uninstall atomic_busybox
rm -f Dockerfile
./atomic uninstall busybox
