FROM centos
RUN yum -y install nmap-ncat && yum clean all

LABEL "Name"="atomic-test-system-hostfs"
LABEL "atomic.has_install_files"="yes"

# Add a file that can be handled by the rpm generator
RUN mkdir -p /exports/hostfs/usr/local/lib /exports/hostfs/usr/local/placeholder-lib
RUN ln -s /does/not/exist /exports/hostfs/broken-symlink
ADD message /exports/hostfs/usr/local/lib/secret-message
ADD message-template /exports/hostfs/usr/local/lib/secret-message-template

# this is going to be renamed
ADD message /exports/hostfs/usr/local/lib/placeholder-file

ADD run.sh greet.sh /usr/bin/

# Export the files used for the system container
ADD tmpfiles.template manifest.json service.template config.json.template /exports/
