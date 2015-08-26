% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% April 2015
# NAME
atomic-upload - upload Image to repository

# SYNOPSIS
**atomic upload**
[**--pulp**]
[**--satellite**]
[**-h**|**--help**]
IMAGE

# DESCRIPTION
**atomic upload** will upload the image to the repository.  Defaults to docker repository; can also upload to satellite or pulp repository.    

# OPTIONS:
**--pulp**
  Upload using the pulp protocol; defaults to using docker push

**--satellite**
  Upload using the satellite protocol; defaults to using docker push  

**-h** **--help**
  Print usage statement

# HISTORY
April 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)
July 2015, Edited by Jenny Ramseyer (jramseye at redhat dot com)
