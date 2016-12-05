FROM centos
RUN yum -y install nmap-ncat && yum clean all

LABEL "Name"="atomic-test-system"

ADD run.sh greet.sh /usr/bin/

# Export the files used for the system container
ADD tmpfiles.template manifest.json service.template config.json.template /exports/
