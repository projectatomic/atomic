% ATOMIC(1)
% Will Temple
% June 2015
# NAME
atomic-unmount - Unmount Images/Containers

# SYNOPSIS
**atomic unmount**
[**-h**|**--help**]
DIRECTORY

# DESCRIPTION
**atomic unmount** will unmount a container/image previously mounted with
**atomic mount**. If the UID of the user is not zero, i.e. if the user
is not root, it will expect the image being deleted was mounted by
non-root user and will delete the files rather than use the unmount
system call. 

# OPTIONS:
**-h** **--help**
  Print usage statement

# HISTORY
June 2015, Originally compiled by William Temple (wtemple at redhat dot com)
