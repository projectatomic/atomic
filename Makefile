# Installation directories.
PREFIX ?= $(DESTDIR)/usr
SYSCONFDIR ?= $(DESTDIR)/etc/sysconfig
PROFILEDIR ?= $(DESTDIR)/etc/profile.d
PYTHON ?= /usr/bin/python

test:
	sh ./test.sh

all: python-build

python-build: atomic
	$(PYTHON) setup.py build
	pylint -E --additional-builtins _ atomic

clean:
	$(PYTHON) setup.py clean
	-rm -rf build *~ \#* *pyc .#*

install: test all 
	$(PYTHON) setup.py install `test -n "$(DESTDIR)" && echo --root $(DESTDIR)`
	[ -d $(SYSCONFDIR) ] || mkdir -p $(SYSCONFDIR)
	install -m 644 atomic.sysconfig $(SYSCONFDIR)/atomic

	[ -d $(PROFILEDIR) ] || mkdir -p $(PROFILEDIR)
	install -m 644 atomic.sh $(PROFILEDIR)
