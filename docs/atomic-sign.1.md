% ATOMIC(1) Atomic Man Pages
% Brent Baude
% August 2016
# NAME
atomic-sign- Create a signature for an image

**WARNING**

Only use **atomic sign** if you trust the remote registry which contains the image
(preferably by being the only administrator of it).


# SYNOPSIS
**atomic sign**
[**-h**|**--help**]

[**-d**, **--directory**]
[**--sign-by**]
[**-g**, **--gnupghome**]
[ image ... ]

# DESCRIPTION
**atomic sign** will create a local signature for one or more local images that have 
been pulled from a registry. By default, the signature will be written into a directory
derived from the registry configuration files as configured by **registry_confdir**
in /etc/atomic.conf.  

# OPTIONS
**-h** **--help**
  Print usage statement.

**-d** **--directory**
  Store the signatures in the specified directory.  Default: /var/lib/atomic/signature

**--sign-by**
  Override the default identity of the signature. You can define a default in /etc/atomic.conf
  with the key **default_signer**.

**-g** **--gnupghome**
  Specify the GNUPGHOME directory to use for signing, e.g. &#126;/.gnupg. This
  argument will override the value of **gnupg_homedir** in /etc/atomic.conf.

# EXAMPLES
Sign the foobar image from privateregistry.example.com

    atomic sign privateregistry.example.com/foobar
    
Sign the foobar image and save the signature in /tmp/signatures/.

    atomic sign -d /tmp/signatures privateregistry.example.com

Sign the busybox image with the identify of foo@bar.com with a user's keyring

   sudo atomic sign --sign-by foo@bar.com --gnupghome=&#126;/.gnupg privateregistry.example.com

# RELATED CONFIGURATION

The write (and read) location for signatures is defined in YAML-based
configuration files in /etc/containers/registries.d/.  When you sign
an image, atomic will use those configuration files to determine
where to write the signature based on the the name of the originating
registry or a default storage value unless overriden with the -d 
option. For example, consider the following configuration file.

docker:
  privateregistry.example.com:
    sigstore: file:///var/lib/atomic/signature

When signing an image preceeded with the registry name 'privateregistry.example.com',
the signature will be written into subdirectories of 
/var/lib/atomic/signature/privateregistry.example.com. The use of 'sigstore' also means
the signature will be 'read' from that same location on a pull-related function.

You can also scope the registry definitions by repository and even name.  Consider the
following addition to the configuration above.

  privateregistry.exaple.com/john:
    sigstore-staging: file:///mnt/export/signatures
    sigstore: https://www.example.com/signatures/

Now any image from the john repository will use the sigstore-staging location of
'/mnt/export/signatures'.  Also note the use of sigstore-staging versus sigstore. This
means that signatures should be written to that location but read should occur from
the http URL provided.

The user's keyring will be used during signing. When running as root user this may
not be desired. Another keyring may be specified using environment variable GNUPGHOME,
passed in via argument --gnupghome or set in configuration file atomic.conf. For example:

gnupg_homedir: /home/USER/.gnupg

# HISTORY
Initial revision by Brent Baude (bbaude at redhat dot com) August 2016
Updated by Brent Baude (bbaude at redhat dot com) September 2016
Updated by Aaron Weitekamp (aweiteka at redhat dot com) September 2016
