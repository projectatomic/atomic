% ATOMIC(1) Atomic Man Pages
% Brent Baude
% January 2016
# NAME
atomic-help - Display help associated with a container or image
# SYNOPSIS
**atomic help**
[**-h**|**--help**]
IMAGE|CONTAINER

# DESCRIPTION

**Atomic help** displays a help file associated with a container or image.

If a container or image has a help file (in man format) embedded in itself, atomic help will display
the help file in a pager similar to man.  The default location for a help file is /image_help.1 but
the location of the help can be overridden with the HELP LABEL.  If you choose to override the default
location, ensure the path provided is a fully-qualified path that includes the help file itself.

The help file can be written using the middleman markup and the converted using the go-md2man utility
as follows:
```
go-md2man -in image_help.1.md -out image_help.1
```
You can also use any of the many options to create the help file including using native man tagging.

# OPTIONS
**-h** **--help**
  Print usage statement

# HISTORY
January 2016, Originally written by Brent Baude (bbaude at redhat dot com)
