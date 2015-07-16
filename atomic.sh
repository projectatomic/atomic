#
# Licensed under the GNU General Public License Version 2
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

command_not_found_handle () {
	local runcnf=1
	local retval=127

	[ -f /etc/sysconfig/atomic ] && . /etc/sysconfig/atomic

	# only search for the command if we're interactive
	[[ $- =~ i ]] || runcnf=0

	# don't run if not on an atomic host or tools
	([ -n "${TOOLSIMG}" ] &&  [ -f /run/ostree-booted ] && [ -x /usr/bin/atomic ]) ||  runcnf=0

	# run the command, or just print a warning
	if [ $runcnf -eq 1 ]; then
		atomic run ${TOOLSIMG} "$@"
		retval=$?
	else
		echo "bash: $1: command not found"
	fi

	# return success or failure
	return $retval
}

