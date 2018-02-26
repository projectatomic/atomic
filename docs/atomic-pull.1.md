% ATOMIC(1) Atomic Man Pages
% Giuseppe Scrivano
% April 2016
# NAME
atomic-pull - fetch an image locally

# SYNOPSIS
**atomic pull**
[**-h|--help**]
[**--storage=[ostree|docker]**]
[**-t**|**--type** atomic]
IMAGE

# DESCRIPTION
**atomic pull**, will fetch a remote image and store it locally.

You can pull an image from a docker registry (like docker.io) to your
local docker daemon with atomic pull.

`atomic pull docker.io/busybox:latest`

Use the `--storage ostree` option to store it into the OSTree repository. You can
define a default storage type in **/etc/atomic.conf** with the key of 
**default_storage**.

IMAGE has the form `SOURCE:IMAGE-NAME`, where `SOURCE` can be one of
'oci', 'docker', 'dockertar', 'ostree', 'http'.  If no `SOURCE` is
specified then 'oci' is assumed.

An 'oci' image is fetched via Skopeo from a Docker registry.  These
two commands are equivalent:

`atomic pull etcd`
`atomic pull oci:etcd`

A 'docker' image is imported from the local Docker engine, thus not
accessing the network.  It is equivalent to saving the image from
docker (`docker save IMAGE`) and importing it into the OSTree
repository:

`atomic pull --storage ostree docker:fedora:latest`

A 'dockertar' image works in a similar way to 'docker' images, except
that the saved tarball is specified:

`atomic pull --storage ostree dockertar:/path/to/the/image.tar`

If the user is not privileged, the image will be stored in the user
specific repository.

If you are pulling from an insecure registry, use the 'http' prefix.
It tells Skopeo to not do TLS verification on the specified registry.

`atomic pull --storage ostree http:REGISTRY/IMAGE:TAG`

Images where the registry is not specified are supported
when pulling to 'ostree'.  However, we recommend that you use a
fully qualified name to refer unambiguously to the image.

If your /etc/containers/policy.json requires signature verification, the 
pulled image is verified prior to being made available to the local docker
daemon. When interacting with a docker registry, Atomic uses the policy 
and YAML configuration files /etc/containers/ to determine:

* if the image should be verified with a signature
* and where to get the signature

If you use the `--type atomic` switch to interact with an atomic registry,
Atomic will still use the policy to determine if verification is needed.  The
signature itself will be obtained from the atomic registry. An example of 
pulling from an atomic registry could be:

`atomic pull --type atomic my-atomic-registry:images/foobar`

# OPTIONS:
**-h** **--help**
Print usage statement

**--src-creds=USERNAME[:PASSWORD]**
Define the credentials to use with the source registry.

**--storage=[ostree|docker]**
Define the destination storage for the pulled image.

**-t** **--type atomic**
Define an alternate registry type.  The only valid option is **atomic** for
when you want to take advantage of advanced atomic registry options.

# HISTORY
April 2016, Originally compiled by Giuseppe Scrivano (gscrivan at
redhat dot com)
