#!/bin/bash -x
set -euo pipefail
IFS=$'\n\t'

#
# 'atomic migrate' integration tests (non-live)
# AUTHOR: Shishir Mahajan <shishir dot mahajan at redhat dot com>
#

if [[ "$(id -u)" -ne "0" ]]; then
    echo "Atomic migrate tests require root access. Please try again."
    exit 1
fi

init=$(ps -q 1 -o comm=)
if [ "$init" != "systemd" ];then
    echo "Systemd init system is required to run atomic migrate tests. Skipping these tests."
    exit 0
fi

dockerPid=$(ps -C docker -o pid=|xargs)
dockerCmdline=$(cat /proc/$dockerPid/cmdline)
if [[ $dockerCmdline =~ "-g=" ]] || [[ $dockerCmdline =~ "-g/" ]] || [[ $dockerCmdline =~ "--graph" ]];then
   echo "Docker is not located at the default (/var/lib/docker) root location. Skipping these tests."
   exit 0
fi

if [ ! -f /etc/sysconfig/docker ];then
   echo "Atomic migrate tests require /etc/sysconfig/docker to exist. Skipping these tests."
   exit 0
fi

if [ ! -f /etc/sysconfig/docker-storage ];then
   echo "Atomic migrate tests require /etc/sysconfig/docker-storage to exist. Skipping these tests."
   exit 0
fi

setup () {
	${DOCKER} create --name test-migrate-1 -v /tmp fedora /bin/bash
	${DOCKER} create --name test-migrate-2 -v /tmp busybox /bin/bash
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

# Test for atomic migrate export and import using the default graph
# at /var/lib/docker
atomic_migrate () {
	setup
	${ATOMIC} migrate export --dir "$(pwd)/migrate-dir"
	switch_docker_storage
	echo 'y'|${ATOMIC} migrate import --dir "$(pwd)/migrate-dir"
	systemctl restart docker
}

switch_docker_storage () {
	systemctl stop docker
	mkdir -p /var/lib/overlayfs
	mount -o bind /var/lib/overlayfs /var/lib/docker
	restorecon -R -v /var/lib/docker
	cp /etc/sysconfig/docker /etc/sysconfig/docker.backup
	cp /etc/sysconfig/docker-storage /etc/sysconfig/docker-storage.backup
	sed -i "/OPTIONS/c OPTIONS=''" /etc/sysconfig/docker
	sed -i '/DOCKER_STORAGE_OPTIONS/c DOCKER_STORAGE_OPTIONS="-s overlay"' /etc/sysconfig/docker-storage
	systemctl start docker
}

atomic_migrate
