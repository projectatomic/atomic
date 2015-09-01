# Installation directories.
PREFIX ?= $(DESTDIR)/usr
SYSCONFDIR ?= $(DESTDIR)/etc/sysconfig
PROFILEDIR ?= $(DESTDIR)/etc/profile.d
PYTHON ?= /usr/bin/python
PYLINT ?= /usr/bin/pylint

all: python-build docs

test:
	sh ./test.sh

python-build: atomic
	$(PYTHON) setup.py build
	$(PYLINT) -E --additional-builtins _ atomic

MANPAGES_MD = $(wildcard docs/*.md)

docs/%.1: docs/%.1.md
	go-md2man -in $< -out $@.tmp && mv $@.tmp $@

docs: $(MANPAGES_MD:%.md=%)

clean:
	$(PYTHON) setup.py clean
	-rm -rf build *~ \#* *pyc .#* docs/*.1

install: all 
	$(PYTHON) setup.py install --install-scripts /usr/share/atomic `test -n "$(DESTDIR)" && echo --root $(DESTDIR)`

	install -d -m 0755 $(DESTDIR)/usr/bin
	ln -fs ../share/atomic/atomic $(DESTDIR)/usr/bin/atomic

	[ -d $(SYSCONFDIR) ] || mkdir -p $(SYSCONFDIR)
	install -m 644 atomic.sysconfig $(SYSCONFDIR)/atomic

	[ -d $(PROFILEDIR) ] || mkdir -p $(PROFILEDIR)
	install -m 644 atomic.sh $(PROFILEDIR)

	install -d $(PREFIX)/share/man/man1
	install -m 644 $(basename $(MANPAGES_MD)) $(PREFIX)/share/man/man1

	echo ".so man1/atomic-push.1" > $(PREFIX)/share/man/man1/atomic-upload.1
