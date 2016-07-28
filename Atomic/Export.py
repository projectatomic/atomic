"""
export docker images, containers and volumes into a filesystem directory.
"""
import os

from .client import AtomicDocker
from . import util

ATOMIC_LIBEXEC = os.environ.get('ATOMIC_LIBEXEC', '/usr/libexec/atomic')

def export_docker(graph, export_location, force):
    """
    This is a wrapper function for exporting docker images, containers
    and volumes.
    """

    if not os.path.isdir(export_location):
        os.makedirs(export_location)

    with AtomicDocker() as client:
        dangling_images = client.images(filters={"dangling":True}, quiet=True)
        if any(dangling_images):
            if not force:
                choice = util.input("There are dangling images in your system. Would you like atomic to prune them [y/N]")
                choice = choice.strip().lower()
                if not choice in ['y', 'yes']:
                    raise ValueError("Please delete dangling images before running atomic storage export")

            util.write_out("Deleting dangling images")
            util.check_call([util.default_docker(), "rmi", "-f"]+dangling_images)

        #Save the docker storage driver
        storage_driver = client.info()["Driver"]
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
    with AtomicDocker() as client:
        for image in client.images():
            Id, tags = image["Id"], image["RepoTags"]

            if '<none>:<none>' in tags:
                continue
            if Id not in images:
                images[Id] = []
            images[Id].extend(tags)

    for Id in images:
        tags = " ".join(images[Id])
        util.write_out("Exporting image: {0}".format(Id[:12]))
        with open(export_location + '/images/' + Id, 'w') as f:
            util.check_call([util.default_docker(), "save", tags], stdout=f)

def export_containers(graph, export_location):
    """
    Method for exporting docker containers into a filesystem directory.
    """
    if not os.path.isdir(export_location + "/containers"):
        os.makedirs(export_location + "/containers")

    with AtomicDocker() as client:
        for container in client.containers(all=True):
            Id = container["Id"]

            util.write_out("Exporting container: {0}".format(Id[:12]))
            util.check_call([ATOMIC_LIBEXEC + '/migrate.sh',
                             'export',
                             '--container-id=' + Id[:12],
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
