FROM fedora:24
MAINTAINER Jonathan Lebon <jlebon@redhat.com>

# NB: we also install python2 reqs here (which the builddep
# does not catch since on F24 we build for py3) so that we
# can do pylint for both py2 and py3 as well as reuse the
# same image for RHEL & CentOS tests rather than maintaining
# two separate images.

RUN dnf install -y \
        make \
        python3-pylint \
        python3-slip-dbus \
        python-gobject-base \
        python-dbus \
        pylint \
        python-slip-dbus \
        python-docker-py \
        python2-dateutil \
        PyYAML \
        rpm-python \
        'dnf-command(builddep)' \
 && dnf builddep -y \
        atomic \
 && dnf clean all
