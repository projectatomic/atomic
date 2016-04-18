% ATOMIC(1) Atomic Man Pages
% Matthew Barnes
% May 2016
# NAME
atomic-rhost - Manage cluster hosts

# SYNOPSIS
**atomic rhost [OPTIONS] SUBCOMMAND**

**atomic rhost** will issue commands to a Commissaire server over HTTP.

Commissaire allows administrators of a Kubernetes, Atomic Enterprise or
OpenShift installation to perform administrative tasks without the need
to write custom scripts or manually intervene on systems.

# NOTE
The `rhost` subcommand is only available when `commctl` is installed.

# OPTIONS
**-h** **-help**
  Print usage statement.

# SUBCOMMANDS
**create** [**-c**/**--cluster** CLUSTER_NAME] IP_ADDRESS SSH_PRIV_KEY
  Register a new host with the specified IP address.  SSH_PRIV_KEY is a file path to the host's private SSH key (e.g. id_rsa), used to drive operations on the host.  Use **--cluster** to add the host to an existing cluster.

**delete** IP_ADDRESS
  Unregister the specified IP address and, if applicable, disassociate it from its cluster.

**get** IP_ADDRESS
  Report status of the host with the specified IP address.

**list**
  List all available hosts by IP address.

# HISTORY
Initial revision by Matthew Barnes (mbarnes at redhat dot com) May 2016
