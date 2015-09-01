% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% September 2015
# NAME
atomic-push - push Image to repository

# SYNOPSIS
**atomic push**
[**-a**][**--activation_key**[=*ACTIVATION_KEY*]]
[**--debug**]
[**-h**|**--help**]
[**--pulp**]
[**-p**][**--password**[=*PASSWORD*]]
[**-r**][**--repository_id**[=*REPOSITORY_ID*]]
[**--satellite**]
[**-u**][**--username**[=*USERNAME*]]
[**-U**][**--url**[=*URL*]]
[**--verify_ssl**[=*VERIFY_SSL*]]

# DESCRIPTION
**atomic push** will push the image to the repository.  Defaults to docker repository; can also upload to satellite or pulp repository.    

# OPTIONS:
**-a ACTIVATION_KEY** **--activation_key ACTIVATION_KEY**
  Activation Key

**--debug**
  Debug mode

**-h** **--help**
  Print usage statement

**-p PASSWORD** **--password PASSWORD**
  Password for remote registry

**--pulp**
  Push using the pulp protocol, defaults to using docker push

**--r REPO_ID** **--repository_id REPO_ID**
  Repository ID

**--satellite**
  Upload using the satellite protocol; defaults to using docker push  

**-u USERNAME** **--username USERNAME**
  Username for remote registry

**-U URL** **--url URL**
  URL for remote registry

**--verify_ssl**
  Flag to verify ssl of registry

# HISTORY
April 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)

July 2015, Edited by Jenny Ramseyer (jramseye at redhat dot com)

September 2015, Edited by Daniel Walsh (dwalsh at redhat dot com)
