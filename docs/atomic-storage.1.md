% ATOMIC(1) Atomic Man Pages
% Shishir Mahajan
% October 2015
# NAME
atomic-storage - Manage container storage.

# SYNOPSIS
**atomic storage COMMAND [OPTIONS]**

atomic storage allows the user to easily
anage container storage.
You can reset your container enviorment back to its initial state as well
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

**-f** **--force**
Force the removal of dangling images

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

# HISTORY
October 2015, Originally compiled by Shishir Mahajan (shishir dot mahajan at redhat dot com)
