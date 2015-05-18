# Installation directories.
PREFIX ?= $(DESTDIR)/usr
SYSCONFDIR ?= $(DESTDIR)/etc/sysconfig
PROFILEDIR ?= $(DESTDIR)/etc/profile.d
PYTHON ?= /usr/bin/python
BASHCOMPLETIONDIR ?= $(PREFIX)/share/bash-completion/completions/

all: python-build docs

test:
	sh ./test.sh

python-build: atomic
	$(PYTHON) setup.py build
	pylint -E --additional-builtins _ atomic

MANPAGES_MD = $(wildcard docs/*.md)

docs/%.1: docs/%.1.md
	go-md2man -in $< -out $@.tmp && mv $@.tmp $@

docs: $(MANPAGES_MD:%.md=%)

clean:
	$(PYTHON) setup.py clean
	-rm -rf build *~ \#* *pyc .#*

install: all 
	$(PYTHON) setup.py install `test -n "$(DESTDIR)" && echo --root $(DESTDIR)`
	[ -d $(SYSCONFDIR) ] || mkdir -p $(SYSCONFDIR)
	install -m 644 atomic.sysconfig $(SYSCONFDIR)/atomic

	[ -d $(PROFILEDIR) ] || mkdir -p $(PROFILEDIR)
	install -m 644 atomic.sh $(PROFILEDIR)

	install -d $(PREFIX)/share/man/man1
	install -m 644 $(basename $(MANPAGES_MD)) $(PREFIX)/share/man/man1
	-mkdir -p $(BASHCOMPLETIONDIR)
	install -m 644 bash/atomic $(BASHCOMPLETIONDIR)

	-mkdir -p $(DESTDIR)/etc/dbus-1/system.d/
	install -m 644 org.atomic.conf $(DESTDIR)/etc/dbus-1/system.d/
	-mkdir -p $(DESTDIR)/usr/share/dbus-1/system-services
	install -m 644 org.atomic.service $(DESTDIR)/usr/share/dbus-1/system-services
	-mkdir -p $(DESTDIR)/usr/share/polkit-1/actions/
	install -m 644 org.atomic.policy $(DESTDIR)/usr/share/polkit-1/actions/

	-mkdir -p $(DESTDIR)/usr/share/atomic
	install -m 755 atomic_server.py $(DESTDIR)/usr/share/atomic
