% ATOMIC(1) Atomic Man Pages
% Tomas Tomecek
% May 2017
# NAME
atomic-help - Get help for container images

# SYNOPSIS
**atomic help**
[**-h**|**--help**]
IMAGE

**atomic help** provides documentation for the specified container IMAGE.

The documentation is extracted from the container image. **atomic** searches
for the documentation in following locations:

1. File placed inside root of the container named either **help.1** or
**README.md**.
2. Label named **help** which should contain executable command
to display the documentation.

# OPTIONS
**-h** **-help**
  Print usage statement.

# HISTORY
May 2017, Originally compiled by Tomas Tomecek (ttomecek at redhat dot com)
