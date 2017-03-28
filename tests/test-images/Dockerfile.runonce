FROM centos

LABEL "Name"="atomic-test-runonce"\
      "atomic.run"="once"\
      "atomic.type"="system"

ADD hi.sh /usr/bin/run.sh

# Export the files used for the system container
ADD manifest.json config.json.template /exports/
