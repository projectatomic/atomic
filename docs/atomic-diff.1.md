% ATOMIC(1) Atomic Man Pages
% Brent Baude
% November 2015
# NAME
atomic-diff - show the differences between two images|containers RPMs
# SYNOPSIS
**atomic diff**
[**-h**|**--help**]
[**--json**]
[**--names-only**]
[**-n**][**--no-files**]
[**-r**][**--rpms**]
[**-v**][**--verbose**]
image|container image|container ...]

# DESCRIPTION
**atomic diff** will compare the RPMs found in two different images or containers and output to stdout or as JSON.
By default, the comparison is done by name and version of the RPMs.

# OPTIONS
**-h** **--help**
  Print usage statement.

**--json**
  Output in the form of JSON.

**-n** **--no-files**
  Instead of comparing the differences in name and version, it will only compare the difference in name.
  This will also change the output to only output the names.

**--names-only**
  Only show the RPM names and not versions.

**-r** **--rpms**
  Show the where the two docker objects have different RPMs.

**-v** **--verbose**
  Be verbose in showing the differences in RPMs.  The default will only show the differences in RPMs, whereas
  with **verbose** it will show all the RPMS in each object.


# EXAMPLES
Compare images the files in 'foo1' and 'foo2'.

    atomic diff foo1 foo2

Compare the files in images 'foo1' and 'foo2' and output in JSON.

    atomic diff --json foo1 foo2

Compare only the RPMs in images 'foo1' and 'foo2'

    atomic diff -r -n foo1 foo2

Compare the files and RPMs (without versions) in images 'foo1' and 'foo2' and output as json

    atomic diff -r --json foo1 foo2

# HISTORY
Initial revision by Brent Baude (bbaude at redhat dot com) November 2015
