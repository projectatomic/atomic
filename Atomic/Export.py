"""
export docker images, containers and volumes into a filesystem directory.
"""
import os
import sys
import subprocess
try:
    from subprocess import DEVNULL  # pylint: disable=no-name-in-module
except ImportError:
    DEVNULL = open(os.devnull, 'wb')

import docker

from . import util


DOCKER_CLIENT = docker.Client()

def export_docker(graph, export_location):
    """
    This is a wrapper function for exporting docker images, containers
    and volumes.
    """

    if os.geteuid() != 0:
        sys.exit("You need to have root privileges to run atomic export.")

    if not os.path.isdir(export_location):
        os.makedirs(export_location)

    try:
	#Save the docker storage driver
        storage_driver = DOCKER_CLIENT.info()["Driver"]
        filed = open(export_location+"/info.txt", "w")
        filed.write(storage_driver)
        filed.close()

        #export docker images
        export_images(export_location)
        #export docker containers
        export_containers(graph, export_location)
        #export docker volumes
        export_volumes(graph, export_location)
    except:
        error = sys.exc_info()[0]
        sys.exit(error)

    util.writeOut("atomic export completed successfully")

def export_images(export_location):
    """
    Method for exporting docker images into a filesystem directory.
    """
    if not os.path.isdir(export_location + "/images"):
        os.makedirs(export_location + "/images")

    split_images, split_ids = ([] for i in range(2))
    for j in DOCKER_CLIENT.images():
        split_images.append(j["RepoTags"])
    for k in DOCKER_CLIENT.images():
        split_ids.append(k["Id"])

    dic = {}

    for i in range(0, len(split_ids)):
        if split_images[i] == '<none>:<none>':
            continue
        if split_ids[i] in dic:
            dic[split_ids[i]] = [dic[split_ids[i]], split_images[i]]
        else:
            dic[split_ids[i]] = split_images[i]

    for ids, images in dic.iteritems():
        util.writeOut("Exporting image with id: {0}".format(ids[:12]))
        if isinstance(images, list):
            img = ""
            for i, val in enumerate(images):
                img = img+" "+val
            subprocess.check_call(
                "docker save {0} > {1}/images/{2}.tar".format(
                    img.lstrip(), export_location, ids[:12]), shell=True)
        else:
            subprocess.check_call(
                "docker save {0} > {1}/images/{2}.tar".format(
                    images, export_location, ids[:12]), shell=True)

def export_containers(graph, export_location):
    """
    Method for exporting docker containers into a filesystem directory.
    """
    if not os.path.isdir(export_location + "/containers"):
        os.makedirs(export_location + "/containers")

    split_containers = []
    for j in DOCKER_CLIENT.containers(all=True):
        split_containers.append(j["Id"])

    for i in range(0, len(split_containers)):
        util.writeOut("Exporting container ID:{0}".format(split_containers[i][:12]))
        subprocess.check_call("/usr/libexec/atomic/migrate.sh export --container-id={0}"
                              " --graph={1} --export-location={2}"
                              .format(split_containers[i][:12], graph, export_location),
                              shell=True)

def export_volumes(graph, export_location):
    """
    Method for exporting docker volumes into a filesystem directory.
    """
    if not os.path.isdir(export_location + "/volumes"):
        os.makedirs(export_location + "/volumes")
    util.writeOut("Exporting Volumes")
    subprocess.check_call("/usr/bin/tar --selinux -zcvf {0}/volumes/volumeData.tar.gz"
                          " -C {1}/volumes ."
                          .format(export_location, graph), stdout=DEVNULL, shell=True)
    if os.path.isdir(graph + "/vfs"):
        subprocess.check_call("/usr/bin/tar --selinux -zcvf {0}/volumes/vfsData.tar.gz"
                              " -C {1}/vfs ."
                              .format(export_location, graph), stdout=DEVNULL, shell=True)


