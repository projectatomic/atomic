% ATOMIC(1) Atomic Man Pages
% Brent Baude
% September 2015
# NAME
atomic-scan - Scan for CVEs in a container or image
# SYNOPSIS
**atomic scan**
[**-h**|**--help**]
[**--list**]
[**--scanner**]
[**--scan_type**]
[**--verbose**]
[**--all** | **--images** | **--containers** | **--rootfs** rootfs path to scan|
IMAGE or CONTAINER names ...]

# DESCRIPTION
**atomic scan** will scan the a container or image looking for known Common Vulnerabilities and Exposures(CVEs) by default.  It can also scan
paths on the host filesystem as well using the _--rootfs_ option.

The architecture for _atomic scan_ is very plug-in friendly.  You can define additional scanners to use via the plug-in interface.  To list the
available scanners setup on your system, you can use _--list_.  To use a different scanner, you simple pass its name with the _--scanner_ switch.
You can also select a different scan type using the _--scan_type_ switch.


# OPTIONS
**-h** **--help**
  Print usage statement

**--verbose**
Show more verbose output.  Specifically the stdout from the image scanner itself.

**--list**
Show all scanners configured for atomic and their scan types.

**--scanner**
Select as scanner other than the default.

**--scan_type**
Select a scan_type other than the default.

**--scanner_args**
  Provide additional arguments for the scanner, for example specify a compliance profile.

**--all**
  Instead of providing image or container names, scan all images (excluding intermediate image layers) and containers

**--images**
  Scan all images (excluding intermediate layers).   Similar to the results of `docker images`.

**--containers**
  Scan all containers.  Similar to the results of `docker ps -a`

**--rootfs**
  Rootfs path to scan.  Can provide _--rootfs_ multiple times.
  Note: SELinux separation will be disabled for --rootfs scans, but all other container
  separation will still be in place.

# EXAMPLES
List all the scanners atomic knows about and display their default scan types.

    atomic scan --list

Scan an image named 'foo1'.

    atomic scan foo1

Scan images named 'foo1' and 'foo2' and produce a detailed report.

    atomic scan foo1 foo2

Scan all containers.

    atomic scan --containers

Scan all containers and images and create a detailed report.

    atomic scan --all

Scan a rootfs mounted at /tmp/chroot

    atomic scan --rootfs /tmp/chroot

Scan an image called 'foo1' with a scanner called 'custom_scanner' and its default scan_type

    atomic scan --scanner custom_scanner foo1

Scan an image called 'foo1' with a scanner called 'custom_scanner' and a scan type of 'list_rpms'

    atomic scan --scanner custom_scanner --scan_type list_rpms foo1

# HISTORY
Initial revision by Brent Baude (bbaude at redhat dot com) September 2015
Updated for new atomic scan architecture by Brent Baude (bbaude at redhat dot com) May 2016
