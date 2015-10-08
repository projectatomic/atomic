% ATOMIC(1) Atomic Man Pages
% Brent Baude
% September 2015
# NAME
atomic-scan - Scan for CVEs in a container or image
# SYNOPSIS
**atomic scan**
[**-h**|**--help**]
[**--fetch-cves=True|False**][**--json** | **--detail**] [**--all** | **--images** | **--containers** |
IMAGE or CONTAINER name ...]

# DESCRIPTION
**atomic scan** will scan the a container or image looking for known Common Vulnerabilities and Exposures(CVEs).  By default, atomic scan will summarize the findings by containers or images.

# OPTIONS
**-h** **--help**
  Print usage statement

**--fetch-cves=True|False**
  Override the fetch-cve (fetch the latest CVE input data from Red Hat over the network) setting in /etc/oscapd/config.ini. Values can  be True or False.

**--json**
  Output in the form of JSON.

**--detail**
  Report in greater detail which contains information like the CVE number and name as well as the URL that describes the CVE in greater detail.  Also provided is the RHSA ID and a URL that describes the RHSA in greater detail.

**--all**
  Instead of providing image or container names, scan all images (excluding intermediate image layers) and containers

**--images**
  Scan all images (excluding intermediate layers).   Similar to the results of `docker images`.

**--containers**
  Scan all containers.  Similar to the results of `docker ps -a`

# EXAMPLES
Scan an image named 'foo1'.

    atomic scan foo1

Scan an image named 'foo1' with only the files in the openscap-daemon.

    atomic scan --only-cache foo1

Scan images named 'foo1' and 'foo2' and produce a detailed report.

    atomic scan --detail foo1 foo2

Scan all containers and output the results in JSON format.

    atomic scan --containers --json

Scan all containers and images and create a detailed report.

    atomic scan --all --detail

# HISTORY
Initial revision by Brent Baude (bbaude at redhat dot com) September 2015
