% ATOMIC(1) Atomic Man Pages
% Matthew Barnes
% May 2016
# NAME
atomic-cluster - Manage cluster hosts

# SYNOPSIS
**atomic cluster [OPTIONS] SUBCOMMAND**

**atomic cluster** will issue commands to a Commissaire server over HTTP.

Commissaire allows administrators of a Kubernetes, Atomic Enterprise or
OpenShift installation to perform administrative tasks without the need
to write custom scripts or manually intervene on systems.

# NOTE
The `cluster` subcommand is only available when `commctl` is installed.

# OPTIONS
**-h** **-help**
  Print usage statement.

# SUBCOMMANDS
**create** CLUSTER_NAME
  Register a new cluster with the specified name.

**delete** CLUSTER_NAME
  Unregister the specified cluster and disassociate all of its hosts.

**get** CLUSTER_NAME
  Report status of the specified cluster.

**list**
  List all available clusters by name.

**deploy start** CLUSTER_NAME VERSION
  Initiate deployment of a tree image with a version tag matching VERSION on all hosts associated with the specified cluster.

**deploy status** CLUSTER_NAME
  Report status of a deployment operation on the specified cluster.

**restart start** CLUSTER_NAME
  Initiate a restart of all hosts associated with the specified cluster.

**restart status** CLUSTER_NAME
  Report status of a restart operation on the specified cluster.

**upgrade start** CLUSTER_NAME
  Initiate an upgrade of all hosts associated with the specified cluster.

**upgrade status** CLUSTER_NAME
  Report status of an upgrade operation on the specified cluster.

# HISTORY
Initial revision by Matthew Barnes (mbarnes at redhat dot com) May 2016
