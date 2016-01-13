"""
export docker images, containers and volumes into a filesystem directory.
"""
import os
import sys
import subprocess

import docker

from . import util
from docker.utils import kwargs_from_env


DOCKER_CLIENT = docker.Client(**kwargs_from_env())

ATOMIC_LIBEXEC = os.environ.get('ATOMIC_LIBEXEC', '/usr/libexec/atomic')

def export_docker(graph, export_location):
    """
    This is a wrapper function for exporting docker images, containers
    and volumes.
    """

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

    images = {}
    for image in DOCKER_CLIENT.images():
        id, tags = image["Id"], image["RepoTags"]

        if '<none>:<none>' in tags:
            continue
        if id not in images:
            images[id] = []
        images[id].extend(tags)

    for id in images:
        tags = " ".join(images[id])
        util.writeOut("Exporting image: {0}".format(id[:12]))
        with open(export_location + '/images/' + id, 'w') as f:
            subprocess.check_call(["docker", "save", tags], stdout=f)

def export_containers(graph, export_location):
    """
    Method for exporting docker containers into a filesystem directory.
    """
    if not os.path.isdir(export_location + "/containers"):
        os.makedirs(export_location + "/containers")

    for container in DOCKER_CLIENT.containers(all=True):
        id = container["Id"]

        util.writeOut("Exporting container: {0}".format(id[:12]))
        subprocess.check_call([ATOMIC_LIBEXEC + '/migrate.sh',
                               'export',
                               '--container-id=' + id,
                               '--graph=' + graph,
                               '--export-location=' + export_location])

def tar_create(srcdir, destfile):
    subprocess.check_call(['/usr/bin/tar', '--create', '--gzip', '--selinux',
                           '--file', destfile, '--directory', srcdir, '.'])


def export_volumes(graph, export_location):
    """
    Method for exporting docker volumes into a filesystem directory.
    """
    if not os.path.isdir(export_location + "/volumes"):
        os.makedirs(export_location + "/volumes")

    util.writeOut("Exporting volumes")
    tar_create(srcdir = graph + '/volumes',
               destfile = export_location + '/volumes/volumeData.tar.gz')

    if os.path.isdir(graph + "/vfs"):
        tar_create(srcdir = graph + '/vfs',
                   destfile = export_location + '/volumes/vfsData.tar.gz')
