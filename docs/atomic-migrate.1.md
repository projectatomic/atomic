% ATOMIC(1) Atomic Man Pages
% Shishir Mahajan
% October 2015
# NAME
atomic-migrate - Migrate docker from one backend storage to another.

# SYNOPSIS
**atomic migrate COMMAND [OPTIONS]**

atomic migrate allows the user to easily migrate images, volumes, and 
containers from one version of Docker to another. With this command, 
users can quickly save all their data from the current docker instance, 
change the docker storage backend, and then import all their old data 
to the new system.

# COMMANDS
**export**

export command will export all the current images, volumes, and containers
to the specified directory, in the /images, /volumes, /containers subdirectories.

**import**

import command will import images, volumes, and containers from the specified 
directory into the new docker instance.

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
/var/lib/docker-migrate would be used as default.

# import OPTIONS
**-h** **--help**
  Print usage statement

**--graph**
Root of the docker runtime. If you are running docker at the default
location (/var/lib/docker), you don't need to pass this flag. However
if you are running docker at a custom location. This flag must be set.

**--dir**
Directory from which to import the files (images, containers and volumes). 
If this flag is not set atomic-migrate will assume the import location to 
be /var/lib/docker-migrate. Whether you set this flag or use the default, 
the directory must be present for the import to happen successfully.

# HISTORY
October 2015, Originally compiled by Shishir Mahajan (shishir dot mahajan at redhat dot com)
