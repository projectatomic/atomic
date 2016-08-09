% ATOMIC(1) Atomic Man Pages
% Giuseppe Scrivano
% April 2016
# NAME
atomic-pull - fetch an image locally

# SYNOPSIS
**atomic pull**
[**-h|--help**]
[**--storage=[ostree]**]
IMAGE

# DESCRIPTION
**atomic pull**, will fetch a remote image and store it locally.

Use the `--ostree` option to store it into the OSTree repository.

IMAGE has the form `SOURCE:IMAGE-NAME`, where `SOURCE` can be one of
'oci', 'docker', 'dockertar', 'ostree'.  If no `SOURCE` is specified
then 'oci' is assumed.

An 'oci' image is fetched via Skopeo from a Docker registry.  These
two commands are equivalent:

`atomic pull etcd`  
`atomic pull oci:etcd`

A 'docker' image is imported from the local Docker engine, thus not
accessing the network.  It is equivalent to saving the image from
docker (`docker save IMAGE`) and importing it into the OSTree
repository:

`atomic pull docker:fedora`

A 'dockertar' image works in a similar way to 'docker' images, except
that the saved tarball is specified:

`atomic pull dockertar:/path/to/the/image.tar`

An 'ostree' image refers to an image which is fetched from a remote
OSTree repository.  The remote has to be already configured in the
local OSTree repository:

`atomic pull ostree:REMOTE/branch`

If the user is not privileged, the image will be stored in the user
specific repository.

# OPTIONS:
**-h** **--help**
Print usage statement

**--storage=[ostree]**
Define the destination storage for the pulled image.

# HISTORY
April 2016, Originally compiled by Giuseppe Scrivano (gscrivan at
redhat dot com)