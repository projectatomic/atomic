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
[ image ... ]

# DESCRIPTION
**atomic sign** will create a local signature for one or more local images that have 
been pulled from a registry. Unless overridden, the signature will end up in the 
the default storage location (/var/lib/atomic/containers) for signatures.  A different
default location can be defined in /etc/atomic.conf with the key **default-sigstore-path**.

# OPTIONS
**-h** **--help**
  Print usage statement.

**-d** **--directory**
  Store the signatures in the specified directory.  Default: /var/lib/atomic/signature
 

**--sign-by**
  Override the default identity of the signature. You can define a default in /etc/atomic.conf
  with the key **default_signer**.


# EXAMPLES
Sign the foobar image from privateregistry.example.com

    atomic sign privateregistry.example.com/foobar
    
Sign the foobar image with a specific signature name.

    atomic sign -d /tmp/signatures privateregistry.example.com

Sign the busybox image with the identify of foo@bar.com

    atomic --sign-by foo@bar.com privateregistry.example.com

# HISTORY
Initial revision by Brent Baude (bbaude at redhat dot com) August 2016
