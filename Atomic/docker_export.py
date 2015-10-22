"""
export docker images, containers and volumes into a filesystem directory.
"""
import sys
import os
import subprocess

def export_docker(graph, export_location):
    """
    This is a wrapper function for exporting docker images, containers
    and volumes.
    """

    if os.geteuid() != 0:
        exit("You need to have root privileges to run atomic export."
             "\nPlease try again, this time using 'sudo'. Exiting.")

    if not os.path.isdir(export_location):
        os.mkdir(export_location)
    try:
	#Save the docker storage driver
	storage_driver = subprocess.check_output("docker info|grep \"Storage Driver\"|cut -d\" \" -f 3", shell=True)
	file = open(export_location+"/dockerInfo.txt", "w")
	file.write(storage_driver)
	file.close()

        #export docker images
        export_images(export_location)
        #export docker containers
        export_containers(graph, export_location)
        #export docker volumes
        export_volumes(graph, export_location)
    except:
        error = sys.exc_info()[0]
        sys.exit(error)

    print("atomic export completed successfully")

def export_images(export_location):
    """
    Method for exporting docker images into a filesystem directory.
    """
    if not os.path.isdir(export_location + "/images"):
        os.mkdir(export_location + "/images")
    images = subprocess.check_output("docker images|awk 'NR!=1{print $1 \":\" $2}'", shell=True)
    ids = subprocess.check_output("docker images|awk 'NR!=1{print $3}'", shell=True)

    split_images = images.split()
    split_ids = ids.split()

    d = {}

    for i in range(0, len(split_ids)):
        if split_images[i] == '<none>:<none>':
           continue
        if split_ids[i] in d:
          d[split_ids[i]]=[d[split_ids[i]],split_images[i]]
        else:
          d[split_ids[i]]=split_images[i]

    for id, images in d.iteritems():
        print("Exporting image with id: {0}".format(id))
        if isinstance(images, list):
           img = ""
           for i, val in enumerate(images):
                img=img+" "+val
           subprocess.check_call(
                "docker save {0} > {1}/images/{2}.tar".format(
                    img.lstrip(), export_location, id), shell=True)
        else:
           subprocess.check_call(
                "docker save {0} > {1}/images/{2}.tar".format(
                    images, export_location, id), shell=True)

def export_containers(graph, export_location):
    """
    Method for exporting docker containers into a filesystem directory.
    """
    if not os.path.isdir(export_location + "/containers"):
        os.mkdir(export_location + "/containers")

    containers = subprocess.check_output("docker ps -aq", shell=True)
    split_containers = containers.split()
    for i in range(0, len(split_containers)):
        print("Exporting container ID:{0}".format(split_containers[i]))
        subprocess.check_call("/usr/libexec/dockermigrate/containers-migrate.sh export --container-id={0}"
                              " --graph={1} --export-location={2}"
                              .format(split_containers[i], graph, export_location),
                              shell=True)

def export_volumes(graph, export_location):
    """
    Method for exporting docker volumes into a filesystem directory.
    """
    if not os.path.isdir(export_location + "/volumes"):
        os.mkdir(export_location + "/volumes")
    print("Exporting Volumes")
    subprocess.check_call("tar --selinux -zcvf {0}/volumes/volumeData.tar.gz"
                          " -C {1}/volumes . > /dev/null"
                          .format(export_location, graph), shell=True)
    if os.path.isdir(graph + "/vfs"):
        subprocess.check_call("tar --selinux -zcvf {0}/volumes/vfsData.tar.gz"
                              " -C {1}/vfs . > /dev/null"
                              .format(export_location, graph), shell=True)


