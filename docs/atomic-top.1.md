% ATOMIC(1) Atomic Man Pages
% Brent Baude
% December 2015
# NAME
atomic-top - Run a top-like list of active container processes
# SYNOPSIS
**atomic top**
[**-h**|**--help**]
[**-d**][**-o, --optional=[time, stime, ppid, uid, gid, user, group]**][**-n**]
[Containers to monitor]

# DESCRIPTION

**Atomic top** displays an interactive, top-like view of the processes running in active containers.

While in the interactive view, you can sort the columns of information by pressing a single character
that correlates to the column header.  Any column that you can sort on will have a set of parentheses that surround
a single character. For example, if you want to sort by the '(P)ID' column,
simply press the 'p' key.

Like top, you can exit the interactive view and return to the command line, use the 'q' character key.

# OPTIONS
**-h** **--help**
  Print usage statement

**-d**
  Define the interval in seconds on which you want to refresh the process information.  The interval should be an
  integer greater than 0.  The default interval is set to 1.

**-n**
  The number of iterations.  Must be greater than 0.

**-o** **--optional**
  Add more fields of data to collect for each process.  The fields resemble fields commonly used by
  ps -o.  They currently are: [time, stime, ppid, uid, gid, user, group]
  
  Specify one option per -o flag to include the fields.

# EXAMPLES
Monitor processes with default fields.

    atomic top

Monitor processes with default fields on a 5 second interval for 3 iterations

    atomic top -d 5 -n 3

Monitor processes and add in the data for the parent PIDs and UID.

    atomic top -o ppid -o uid

# HISTORY
December 2015, Originally written by Brent Baude (bbaude at redhat dot com)
