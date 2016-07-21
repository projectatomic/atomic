#!/bin/bash
# bash script to migrate containers from one backend storage to another.
set -e

ATOMIC_LIBEXEC="${ATOMIC_LIBEXEC-/usr/libexec/atomic}"
GOTAR="$ATOMIC_LIBEXEC/gotar"

main() {
if [ $(id -u) != 0 ];then
	echo "Run 'migrate' as root user"
	exit 
fi

NUMARGS=$#

if [ $NUMARGS -eq 0 ] || [ "$1" = "--help" ];then 
	echo "Usage: migrate COMMAND [ARGS] [OPTIONS]
       migrate [--help]

A self-sufficient tool for migrating docker containers from one backend storage to another

Commands:
    export  Export a container from an existing storage
    import  Import a container into a new storage"
	exit
fi

if [ "$1" = "export" ];then
   if [ -z "$2" ]; then
	echo "migrate: "export" requires a minimum of 1 argument.
See 'migrate export --help'

Usage: migrate export CONTAINER-ID [OPTIONS]

Export a container from an existing storage"
	exit
   elif [ "$2" = "--help" ];then
	echo "
Usage: migrate export CONTAINER-ID [OPTIONS]

Export a container from an existing storage

--graph   	    Root of the Docker runtime (Default: /var/lib/docker)
--export-location   Path for exporting the container (Default: /var/lib/atomic/migrate/containers)"
	exit
   else
	container_export $2 $3 $4
   fi
fi

if [ "$1" = "import" ];then
   if [ -z "$2" ]; then
        echo "migrate: "import" requires a minimum of 1 argument.
See 'migrate import --help'
        
Usage: migrate import CONTAINER-ID [OPTIONS]

Import a container into a new storage"
        exit
   elif [ "$2" = "--help" ];then
        echo "
Usage: migrate import CONTAINER-ID [OPTIONS]

Import a container into a new storage

--graph             Root of the Docker runtime (Default: /var/lib/docker)
--import-location   Path for importing the container (Default: /var/lib/atomic/migrate/containers)"
        exit
   else
        container_import $2 $3 $4
   fi
fi

}

get_docker_pid() {
	if ! systemctl is-active docker >/dev/null; then
		echo "Docker daemon is not running"
		exit 1
	fi

	pid=$(systemctl show -p MainPID docker.service)
	echo ${pid#*=}
}

container_export(){
	for arg in "$@"
	do 
		flag=$(echo $arg|cut -d'=' -f 1)
		val=$(echo $arg|cut -d'=' -f 2)
		case "$flag" in
			--container-id)
				containerID=$val
			;;
			--graph)
				dockerRootDir=$val
			;;
			--export-location)
				exportPath=$val
			;;
		esac
	done

	if [ -z "$containerID" ]; then
		echo "--container-id cannot be null"
		exit 1
	fi

	if [ -z "$exportPath" ]; then
		exportPath="/var/lib/atomic/migrate"
	fi

        dockerPid=$(get_docker_pid)
        dockerCmdline=$(cat /proc/$dockerPid/cmdline)||exit 1
        if [[ $dockerCmdline =~ "-g=" ]] || [[ $dockerCmdline =~ "-g/" ]] || [[ $dockerCmdline =~ "--graph" ]];then
                if [ -z "$dockerRootDir" ] || [ $dockerRootDir = "/var/lib/docker" ];then
                        echo "Docker is not located at the default (/var/lib/docker) root location."
                        echo "Please provide the new root location of the docker runtime in --graph option."
        		exit 1
                fi
        else
                dockerRootDir="/var/lib/docker"
        fi
        notruncContainerID=$(docker ps -aq --no-trunc|grep $containerID)||exit 1
        tmpDir=$exportPath/containers/migrate-$containerID
        mkdir -p $tmpDir
        cd $tmpDir
	containerBaseImageID=$(docker inspect --format '{{.Image}}' $containerID)||exit 1
	echo $dockerRootDir>containerInfo.txt
	echo $containerBaseImageID>>containerInfo.txt
	echo $notruncContainerID>>containerInfo.txt
        "$GOTAR" -cf container-metadata.tar $dockerRootDir/containers/$notruncContainerID 2> /dev/null
	if [[ ! -z $(docker diff $containerID) ]];then
                imageName=$(echo $RANDOM)
                docker commit $containerID $imageName 1>/dev/null||exit 1
                mkdir -p $tmpDir/temp
                docker save $imageName > $tmpDir/temp/image.tar||exit 1
                $(cd $tmpDir/temp; "$GOTAR" -xf image.tar)
                diffLayerID=$(python -c 'import json; f=open("temp/repositories"); j=json.load(f); print(j[j.keys()[0]]["latest"])')
                cd $tmpDir/temp/$diffLayerID
                cp layer.tar $tmpDir/container-diff.tar
                cd $tmpDir
                /usr/bin/tar --delete -f container-diff.tar run/gotar 2>/dev/null || true
                rm -rf temp
                docker rmi -f $imageName 1>/dev/null||exit 1
	fi
}

container_import(){
	for arg in "$@"
        do
                flag=$(echo $arg|cut -d'=' -f 1)
                val=$(echo $arg|cut -d'=' -f 2)
                case "$flag" in
                        --container-id)
                                containerID=$val
                        ;;
                        --graph)
                                dockerRootDir=$val
                        ;;
                        --import-location)
                                importPath=$val
                        ;;
                esac
        done

        if [ -z "$containerID" ]; then
                echo "--container-id cannot be null"
                exit
        fi

        if [ -z "$importPath" ]; then
                importPath="/var/lib/atomic/migrate"
        fi

        dockerPid=$(get_docker_pid)
        dockerCmdline=$(cat /proc/$dockerPid/cmdline)||exit 1
        if [[ $dockerCmdline =~ "-g=" ]] || [[ $dockerCmdline =~ "-g/" ]] || [[ $dockerCmdline =~ "--graph" ]];then
                if [ -z "$dockerRootDir" ] || [ $dockerRootDir = "/var/lib/docker" ];then
                        echo "Docker is not located at the default (/var/lib/docker) root location."
                        echo "Please provide the new root location of the docker runtime in --graph option."
                        exit 1
                fi
        else
                dockerRootDir="/var/lib/docker"
        fi

	cd $importPath/containers/migrate-$containerID
	dockerBaseImageID=$(sed -n '2p' containerInfo.txt)||exit 1
        if [[ -f container-diff.tar ]];then
                cat container-diff.tar|docker run -i -v "$GOTAR:/run/gotar" $dockerBaseImageID /run/gotar -xf -
	else
		docker run -i $dockerBaseImageID echo "container_import"
	fi
	newContainerID=$(docker ps -lq)||exit 1
	newContainerName=$(docker inspect -f '{{.Name}}' $newContainerID)||exit 1
	newNotruncContainerID=$(docker ps -aq --no-trunc|grep $newContainerID)||exit 1					
	cd $dockerRootDir/containers/$newNotruncContainerID
	rm -rf *
	cp $importPath/containers/migrate-$containerID/container-metadata.tar .
	"$GOTAR" -xf container-metadata.tar	
	rm container-metadata.tar
	oldDockerRootDir=$(sed -n '1p' $importPath/containers/migrate-$containerID/containerInfo.txt)||exit 1
	oldNotruncContainerID=$(sed -n '3p' $importPath/containers/migrate-$containerID/containerInfo.txt)||exit 1
	cp -r ${oldDockerRootDir:1}/containers/$oldNotruncContainerID/* .
	baseDir=$(echo $oldDockerRootDir|cut -d"/" -f 2)
	rm -rf $baseDir

	oldStorageDriver=$(sed -n '1p' $importPath/info.txt)||exit 1
	newStorageDriver=$(docker info|grep "Storage Driver"|cut -d" " -f 3)

	sed -i "s|\"Driver\":\"$oldStorageDriver\"|\"Driver\":\"$newStorageDriver\"|g" config.v2.json	
	sed -i "s|$oldDockerRootDir/containers/$oldNotruncContainerID|$dockerRootDir/containers/$oldNotruncContainerID|g" config.v2.json

	cd $dockerRootDir
	find . -name "*$newNotruncContainerID*" -type d -exec rename $newNotruncContainerID $oldNotruncContainerID {} +
	find . -name "*$newNotruncContainerID*" -type f -exec rename $newNotruncContainerID $oldNotruncContainerID {} +
}

main "$@"
