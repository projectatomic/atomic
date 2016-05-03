"""
export docker images, containers and volumes into a filesystem directory.
"""
import os
import sys

from .client import get_docker_client
from . import util

ATOMIC_LIBEXEC = os.environ.get('ATOMIC_LIBEXEC', '/usr/libexec/atomic')

def export_docker(graph, export_location, force):
    """
    This is a wrapper function for exporting docker images, containers
    and volumes.
    """

    if not os.path.isdir(export_location):
        os.makedirs(export_location)

    dangling_images = get_docker_client().images(filters={"dangling":True}, quiet=True)
    if any(dangling_images):
        if not force:
            util.write_out("There are dangling images in your system. Would you like atomic to prune them [y/N]")
            choice = sys.stdin.read(1)
            if choice.lower() == 'n':
                raise ValueError("Please delete dangling images before running atomic storage export")
        util.write_out("Deleting dangling images")
        util.check_call([util.default_docker(), "rmi", "-f"]+dangling_images)

    #Save the docker storage driver
    storage_driver = get_docker_client().info()["Driver"]
    filed = open(export_location+"/info.txt", "w")
    filed.write(storage_driver)
    filed.close()

    #export docker images
    export_images(export_location)
    #export docker containers
    export_containers(graph, export_location)
    #export docker volumes
    export_volumes(graph, export_location)

    util.write_out("atomic export completed successfully")

def export_images(export_location):
    """
    Method for exporting docker images into a filesystem directory.
    """
    if not os.path.isdir(export_location + "/images"):
        os.makedirs(export_location + "/images")

    images = {}
    for image in get_docker_client().images():
        id, tags = image["Id"], image["RepoTags"]

        if '<none>:<none>' in tags:
            continue
        if id not in images:
            images[id] = []
        images[id].extend(tags)

    for id in images:
        tags = " ".join(images[id])
        util.write_out("Exporting image: {0}".format(id[:12]))
        with open(export_location + '/images/' + id, 'w') as f:
            util.check_call([util.default_docker(), "save", tags], stdout=f)

def export_containers(graph, export_location):
    """
    Method for exporting docker containers into a filesystem directory.
    """
    if not os.path.isdir(export_location + "/containers"):
        os.makedirs(export_location + "/containers")

    for container in get_docker_client().containers(all=True):
        id = container["Id"]

        util.write_out("Exporting container: {0}".format(id[:12]))
        util.check_call([ATOMIC_LIBEXEC + '/migrate.sh',
                               'export',
                               '--container-id=' + id[:12],
                               '--graph=' + graph,
                               '--export-location=' + export_location])

def tar_create(srcdir, destfile):
    util.check_call(['/usr/bin/tar', '--create', '--gzip', '--selinux',
                           '--file', destfile, '--directory', srcdir, '.'])


def export_volumes(graph, export_location):
    """
    Method for exporting docker volumes into a filesystem directory.
    """
    if not os.path.isdir(export_location + "/volumes"):
        os.makedirs(export_location + "/volumes")

    util.write_out("Exporting volumes")
    tar_create(srcdir=graph + '/volumes',
               destfile=export_location + '/volumes/volumeData.tar.gz')

    if os.path.isdir(graph + "/vfs"):
        tar_create(srcdir=graph + '/vfs',
                   destfile=export_location + '/volumes/vfsData.tar.gz')
