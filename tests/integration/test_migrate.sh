#!/bin/bash -x
set -euo pipefail
IFS=$'\n\t'

#With the inclusion of this PR (https://github.com/projectatomic/atomic/pull/294)
#atomic storage export/import will only work with docker 1.10 support.
#Skip this test, until we move to docker 1.10.

echo "WARNING: skipping test_migrate.sh since it is only supported with docker 1.10 onwards."
exit 0

#
# 'atomic storage' integration tests (non-live)
# AUTHOR: Shishir Mahajan <shishir dot mahajan at redhat dot com>
#

if [[ "$(id -u)" -ne "0" ]]; then
    echo "Atomic storage tests require root access. Please try again."
    exit 1
fi

init=$(ps -q 1 -o comm=)
if [ "$init" != "systemd" ];then
    echo "Systemd init system is required to run atomic storage tests. Skipping these tests."
    exit 0
fi

if ! systemctl is-active docker >/dev/null; then
     echo "Docker daemon is not running"
     exit 1
fi
pid=$(systemctl show -p MainPID docker.service)
dockerPid=$(echo ${pid#*=})
dockerCmdline=$(cat /proc/$dockerPid/cmdline)
if [[ $dockerCmdline =~ "-g=" ]] || [[ $dockerCmdline =~ "-g/" ]] || [[ $dockerCmdline =~ "--graph" ]];then
   echo "Docker is not located at the default (/var/lib/docker) root location. Skipping these tests."
   exit 0
fi

if [ ! -f /etc/sysconfig/docker ];then
   echo "Atomic storage tests require /etc/sysconfig/docker to exist. Skipping these tests."
   exit 0
fi

if [ ! -f /etc/sysconfig/docker-storage ];then
   echo "Atomic storage tests require /etc/sysconfig/docker-storage to exist. Skipping these tests."
   exit 0
fi

setup () {
	CNT1=$(${DOCKER} create --name test-migrate-1 -v /tmp fedora /bin/bash)
	CNT2=$(${DOCKER} create --name test-migrate-2 -v /tmp busybox /bin/bash)
}

cleanup () {
	systemctl stop docker

	if findmnt /var/lib/docker >/dev/null; then
		umount /var/lib/docker
	fi

	rm -rf /var/lib/overlayfs

	if [ -f /etc/sysconfig/docker.backup ]; then
		mv /etc/sysconfig/docker{.backup,}
	fi

	if [ -f /etc/sysconfig/docker-storage.backup ]; then
		mv /etc/sysconfig/docker-storage{.backup,}
	fi

	systemctl start docker

	for cnt in test-migrate-1 test-migrate-2; do
		if ${DOCKER} inspect $cnt &>/dev/null; then
			${DOCKER} rm -f -v $cnt
		fi
	done
}

trap cleanup EXIT

# Test for atomic storage export and import using the default graph
# at /var/lib/docker
atomic_storage_migrate () {
	setup
	echo 'y'|${ATOMIC} storage export --dir "$(pwd)/migrate-dir"
	switch_docker_storage
	echo 'y'|${ATOMIC} storage import --dir "$(pwd)/migrate-dir"
	systemctl restart docker

	# check that the containers were actually migrated (this implicitly also
	# checks that at least the fedora and busybox images were also migrated)
	for cnt in $CNT1 $CNT2; do
		${DOCKER} inspect $cnt
	done
}

switch_docker_storage () {
	systemctl stop docker
	mkdir -p /var/lib/overlayfs
	mount -o bind /var/lib/overlayfs /var/lib/docker
	restorecon -R -v /var/lib/docker

	# NB: Let's not actually switch over to overlayfs for now because it can
	# trigger a kernel mm bug from the overlay module's allocations. There is a
	# "fix" (an overlay patch to work around the mm bug) which has made it
	# upstream, but is not yet in the stable kernels. Until then, let's not use
	# overlayfs (see https://github.com/coreos/bugs/issues/489 for more info).

	#cp /etc/sysconfig/docker /etc/sysconfig/docker.backup
	#cp /etc/sysconfig/docker-storage /etc/sysconfig/docker-storage.backup
	#sed -i "/OPTIONS/c OPTIONS=''" /etc/sysconfig/docker
	#sed -i '/DOCKER_STORAGE_OPTIONS/c DOCKER_STORAGE_OPTIONS="-s overlay"' /etc/sysconfig/docker-storage

	systemctl start docker
}

atomic_storage_migrate
