# Installation directories.
PREFIX ?= $(DESTDIR)/usr
SYSCONFDIR ?= $(DESTDIR)/etc/sysconfig
PROFILEDIR ?= $(DESTDIR)/etc/profile.d
PYTHON ?= /usr/bin/python

all: python-build

python-build: info.c search.c common.h policy.h policy.c
	$(PYTHON) setup.py build

clean:
	$(PYTHON) setup.py clean
	-rm -rf build *~ \#* *pyc .#*

install:
	$(PYTHON) setup.py install `test -n "$(DESTDIR)" && echo --root $(DESTDIR)`
	[ -d $(SYSCONFDIR) ] || mkdir -p $(SYSCONFDIR)
	install -m 644 atomic.sysconfig $(SYSCONFDIR)/atomic

	[ -d $(PROFILEDIR) ] || mkdir -p $(PROFILEDIR)
	install -m 644 atomic.sh $(PROFILEDIR)
