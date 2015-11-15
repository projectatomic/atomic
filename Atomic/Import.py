"""
import docker images, containers and volumes from a filesystem directory.
"""
import os
import sys
import subprocess
try:
    from subprocess import DEVNULL  # pylint: disable=no-name-in-module
except ImportError:
    DEVNULL = open(os.devnull, 'wb')

from . import util


def import_docker(graph, import_location):
    """
    This is a wrapper function for importing docker images, containers
    and volumes.
    """

    if os.geteuid() != 0:
        sys.exit("You need to have root privileges to run atomic import.")

    if not os.path.isdir(import_location):
        sys.exit("{0} does not exist".format(import_location))
    try:
        #import docker images
        import_images(import_location)
        #import docker containers
        import_containers(graph, import_location)
        #import docker volumes
        import_volumes(graph, import_location)
    except:
        error = sys.exc_info()[0]
        sys.exit(error)

    util.writeOut("atomic import completed successfully")
    util.writeOut("Would you like to cleanup (rm -rf {0}) the temporary directory [y/N]"
          .format(import_location))
    choice = sys.stdin.read(1)
    if (choice == 'y') or (choice == 'Y'):
        util.writeOut("Deleting {0}".format(import_location))
        subprocess.check_call("rm -rf {0}".format(import_location), shell=True)
    else:
        util.writeOut("Cleanup operation aborted")
    util.writeOut("Please restart docker daemon for the changes to take effect")


def import_images(import_location):
    """
    Method for importing docker images from a filesystem directory.
    """
    tarballs = subprocess.check_output("ls {0}/images".format(import_location), shell=True)
    split_tarballs = tarballs.split()
    for i in split_tarballs:
        util.writeOut("Importing image with id: {0}".format(i[:-4]))
        subprocess.check_call("docker load < {0}/images/{1}".format(import_location, i), shell=True)

def import_containers(graph, import_location):
    """
    Method for importing docker containers from a filesystem directory.
    """
    if not os.path.isdir(import_location + "/containers"):
        sys.exit("{0} does not exist. No containers to import."
                 .format(import_location+"/containers"))

    containers = subprocess.check_output("ls {0}/containers".format(import_location), shell=True)
    split_containers = containers.split()
    for i in split_containers:
        util.writeOut("Importing container ID:{0}".format(i[8:]))
        subprocess.check_call("/usr/libexec/atomic/migrate.sh import --container-id={0}"
                              " --graph={1} --import-location={2}"
                              .format(i[8:], graph, import_location), shell=True)

def import_volumes(graph, import_location):
    """
    Method for importing docker volumes from a filesystem directory.
    """
    util.writeOut("Importing Volumes")
    subprocess.check_call("/usr/bin/tar --selinux -xzvf {0}/volumes/volumeData.tar.gz"
                          " -C {1}/volumes"
                          .format(import_location, graph), stdout=DEVNULL, shell=True)
    if os.path.isdir(graph + "/vfs"):
        subprocess.check_call("/usr/bin/tar --selinux -xzvf {0}/volumes/vfsData.tar.gz"
                              " -C {1}/vfs"
                              .format(import_location, graph), stdout=DEVNULL,  shell=True)
