% ATOMIC(1) Atomic Man Pages
% Dan Walsh
% May 2015
# NAME
atomic-verify - Verify image is fully updated

# SYNOPSIS
**atomic verify**
[**-h**|**--help**]
[**-v**|**--verbose**]
[**--no-validate**]
IMAGE

# DESCRIPTION
**atomic verify** checks whether there is a newer image available and scans
through all layers to see if any of the layers, which are base images themselves, have a new version available.
If the tool finds an out of date image, it will report as such. If the image is a system image, it will
also look through the layers and validate each layer to determine if it has been tampered with and output
details of these changes (if at all).

If the image or any of its layers are pulled from a repository, it will attempt to check the repository
to see if there is a new image and capture any of its relevant information like version (where applicable).

Any images that do not possess a **Version** LABEL cannot be compared for available updates.  If an image
lacks the version information, it will still be part of the layer descriptions but will be cited as not having
the version information.

# OPTIONS:
**-h** **--help**
  Print usage statement

**--no-validate**
  Skip validation of the files contained inside the image.

**-v** **--verbose**
  Will output the status of each base image that makes up the image being verified.

# EXAMPLES
Verify the Red Hat rsyslog image

    # atomic verify registry.access.redhat.com/rhel7/rsyslog
    #
Verify the Red Hat rsyslog image and show status of each image layer

    # atomic verify -v registry.access.redhat.com/rhel7/rsyslog
    registry.access.redhat.com/rhel7/rsyslog contains the following images:

     rhel7/rsyslog-7.1-29           rhel7/rsyslog-7.1-29
     redhat/rhel7-7.1-24            redhat/rhel7-7.1-24

     * = version difference
Verify a system image

    # sudo atomic verify busybox
    validation output for layer a3ed95caeb02ffe68cdd9fd84406680ae93d633cb16422d00e8a7c22955b46d4:

	(no changes detected)

    validation output for layer 8ddc19f16526912237dd8af81971d5e4dd0587907234be2b83e249518d5b673f:

    "etc/shadow": keyword "size": expected 243; got 268
    "etc/shadow": keyword "sha256digest": expected 22d9cee21ee808c52af44ac...; got 7a07ac69054c2a3533569874c2...


# HISTORY
May 2015, Originally compiled by Daniel Walsh (dwalsh at redhat dot com)

Nov 2015, Updated for remote inspect by Brent Baude (bbaude at redhat dot com)
