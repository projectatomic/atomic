% ATOMIC(1) Atomic Man Pages
% Shishir Mahajan
% October 2015
# NAME
atomic-storage - Manage container storage.

# SYNOPSIS
**atomic storage COMMAND [OPTIONS]**

atomic storage allows the user to easily manage container storage.
You can reset your container environment back to its initial state as well
as migrate all images, volumes, and containers from one version of atomic
to another. With this command, users can quickly save all their data from
the current atomic instance, change the container's content storage backend,
and then import all their old data to the new system.

# COMMANDS
**export**

export command will export all the current images, volumes, and containers
to the specified directory (/var/lib/atomic/migrate by default), in the /images,
/volumes, /containers subdirectories.

**import**

import command will import images, volumes, and containers from the specified
directory (/var/lib/atomic/migrate by default) into the new atomic instance.

**reset**
	Remove all containers/images from your system

**modify**
	Modify the default storage setup

# export OPTIONS
**-h** **--help**
  Print usage statement

**--graph**
Root of the docker runtime. If you are running docker at the default
location (/var/lib/docker), you don't need to pass this flag. However
if you are running docker at a custom location. This flag must be set.

**--dir**
Directory in which to temporarily store the files (can be an existing
directory, or the command will create one). If no directory is specified,
/var/lib/atomic/migrate would be used as default.

# Note:
Atomic --assumeyes option can be used

[**-y|--assumeyes**]
  Delete image(s) without conformation from the user

# import OPTIONS
**-h** **--help**
  Print usage statement

**--graph**
Root of the docker runtime. If you are running docker at the default
location (/var/lib/docker), you don't need to pass this flag. However
if you are running docker at a custom location. This flag must be set.

**--dir**
Directory from which to import the files (images, containers and volumes).
If this flag is not set atomic storage will assume the import location to
be /var/lib/atomic/migrate. Whether you set this flag or use the default,
the directory must be present for the import to happen successfully.

# modify OPTIONS
**-h** **--help**
  Print usage statement

**--add-device**
Add the block devices names to /etc/sysconfig/docker-storage-setup.
You must run docker-storage-setup to add the block devices
to storage pool. docker-storage-setup will expand your devicemapper
storage pool by adding the block device. Only works with devicemapper driver.

E.g atomic storage modify --add-device /dev/vdb will add `DEVS="/dev/vdb"`
to /etc/sysconfig/docker-storage-setup.

**--remove-device**
Remove block devices from the storage pool.  If a device is not empty, this
command will try to first move its data to some other device in the pool.

**--remove-unused-devices**
Remove all block devices from the storage pool that are currently unused.

**--driver**
Add the backend storage driver name to /etc/sysconfig/docker-storage-setup.
Drivers supported: devicemapper, overlay, overlay2.
E.g atomic storage modify --driver=overlay2 will add `STORAGE_DRIVER=overlay2`
to /etc/sysconfig/docker-storage-setup.

**--lvname**
Add the logical volume name for container storage to
/etc/sysconfig/docker-storage-setup.
E.g atomic storage modify --lvname="container-root-lv"
--rootfs="/var/lib/containers" will add
`CONTAINER_ROOT_LV_NAME="container-root-lv"` and
`CONTAINER_ROOT_LV_MOUNT_PATH="/var/lib/containers"`
to /etc/sysconfig/docker-storage-setup.
Note: You must set --rootfs when setting --lvname.

**--rootfs**
Add the mountpath where logical volume for container storage
would be mounted to /etc/sysconfig/docker-storage-setup.
E.g. atomic storage modify --rootfs="/var/lib/containers"
--lvname="container-root-lv" will add
`CONTAINER_ROOT_LV_MOUNT_PATH="/var/lib/containers"` and
`CONTAINER_ROOT_LV_NAME="container-root-lv"` to
/etc/sysconfig/docker-storage-setup.
Note: You must set --lvname when setting --rootfs.

**--lvsize**
Add logical volume size for container storage to
/etc/sysconfig/docker-storage-setup. It defaults to 40% of all free space.
--lvsize can take values acceptable to "lvcreate -L" as well as some values
acceptable to "lvcreate -l". If user intends to pass values acceptable to
"lvcreate -l", then only those values which contains "%" in syntax are acceptable.
If value does not contain "%" it is assumed value is suitable for "lvcreate -L".
E.g. atomic storage modify --rootfs="/var/lib/containers" --lvname="container-root-lv"
--lvsize=20%FREE will add `CONTAINER_ROOT_LV_MOUNT_PATH="/var/lib/containers"`,
`CONTAINER_ROOT_LV_NAME="container-root-lv"` and `CONTAINER_ROOT_LV_SIZE=20%FREE` to
/etc/sysconfig/docker-storage-setup.
Note: You must set --lvname and --rootfs when setting --lvsize.

**--vgroup**
Add the name of the volume group for the storage pool to
/etc/sysconfig/docker-storage-setup.
E.g atomic storage modify --vgroup=atomicos would add
`VG=atomicos` to /etc/sysconfig/docker-storage-setup.

# reset OPTIONS
**-h** **--help**
  Print usage statement

**--graph**
Root of the container runtime. atomic will search for either /var/lib/docker or
/var/lib/docker-latest, if only one exists, atomic will select it as the default.
If both exists or you are running docker with a graph storage at a non default
location, you need to pass this flag.

# HISTORY
October 2015, Originally compiled by Shishir Mahajan (shishir dot mahajan at redhat dot com)
