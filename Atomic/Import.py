"""
import docker images, containers and volumes from a filesystem directory.
"""
import os
import sys

from . import util


ATOMIC_LIBEXEC = os.environ.get('ATOMIC_LIBEXEC', '/usr/libexec/atomic')

def import_docker(graph, import_location, assumeyes):
    """
    This is a wrapper function for importing docker images, containers
    and volumes.
    """

    if not os.path.isdir(import_location):
        sys.exit("{0} does not exist".format(import_location))
    #import docker images
    import_images(import_location)
    #import docker containers
    import_containers(graph, import_location)
    #import docker volumes
    import_volumes(graph, import_location)

    util.write_out("atomic import completed successfully")
    confirm = ""
    if assumeyes:
        confirm = "yes"
    else:
        confirm = util.input("Would you like to cleanup (rm -rf {0}) the temporary directory [y/N]"
                      .format(import_location))
    confirm = confirm.strip().lower()
    if confirm in ['y', 'yes']:
        util.write_out("Deleting {0}".format(import_location))
        util.check_call(['/usr/bin/rm', '-rf', import_location])
    util.write_out("Please restart docker daemon for the changes to take effect")

def import_images(import_location):
    """
    Method for importing docker images from a filesystem directory.
    """
    subdir = import_location + '/images'
    images = os.listdir(subdir)
    for image in images:
        util.write_out("Importing image: {0}".format(image[:12]))
        with open(subdir + '/' + image) as f:
            util.check_call([util.default_docker(), "load"], stdin=f)

def import_containers(graph, import_location):
    """
    Method for importing docker containers from a filesystem directory.
    """
    subdir = import_location + '/containers'
    containers = os.listdir(subdir)
    for cnt in containers:
        cnt = cnt[8:] # strip off the "migrate-" prefix
        util.write_out("Importing container: {0}".format(cnt[:12]))
        util.check_call([ATOMIC_LIBEXEC + '/migrate.sh',
                               'import',
                               '--container-id=' + cnt,
                               '--graph=' + graph,
                               '--import-location=' + import_location])

def tar_extract(srcfile, destdir):
    util.check_call(['/usr/bin/tar', '--extract', '--gzip', '--selinux',
                           '--file', srcfile, '--directory', destdir])

def import_volumes(graph, import_location):
    """
    Method for importing docker volumes from a filesystem directory.
    """

    volfile = import_location + '/volumes/volumeData.tar.gz'
    if os.path.isfile(volfile):
        util.write_out("Importing volumes")
        tar_extract(srcfile=volfile,
                    destdir=graph + '/volumes')

    vfsfile = import_location + '/volumes/vfsData.tar.gz'
    if os.path.isfile(vfsfile) and os.path.isdir(graph + "/vfs"):
        tar_extract(srcfile=vfsfile,
                    destdir=graph + '/vfs')
