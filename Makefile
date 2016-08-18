# Installation directories.
PREFIX ?= $(DESTDIR)/usr
SYSCONFDIR ?= $(DESTDIR)/etc/sysconfig
PROFILEDIR ?= $(DESTDIR)/etc/profile.d
PYTHON ?= /usr/bin/python
PYTHON3 ?= /usr/bin/python3
PYLINT ?= $(PYTHON) -m pylint
PYTHON3_PYLINT ?= $(PYTHON3) -m pylint
GO_MD2MAN ?= /usr/bin/go-md2man
GO ?= /usr/bin/go
PYTHONSITELIB=$(shell $(PYTHON) -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(0))")
VERSION=$(shell $(PYTHON) setup.py --version)

.PHONY: all
all: python-build docs pylint-check dockertar-sha256-helper gotar

.PHONY: test-python3-pylint
test-python3-pylint:
	$(PYTHON3_PYLINT) --disable=all --enable=E --enable=W --additional-builtins=_ *.py atomic Atomic tests/unit/*.py -d=no-absolute-import,print-statement,no-absolute-import,bad-builtin

.PHONY: test check

check: test

test: all test-python3-pylint
	./test.sh

test-destructive: all
	ENABLE_DESTRUCTIVE=1 ./test.sh

.PHONY: python-build
python-build:
	$(PYTHON) setup.py build

.PHONY: pylint-check
pylint-check:
	$(PYLINT) --disable=all --enable=E --enable=W --additional-builtins=_ *.py atomic Atomic tests/unit/*.py -d=no-absolute-import,print-statement,no-absolute-import,bad-builtin

MANPAGES_MD = $(wildcard docs/*.md)

docs/%.1: docs/%.1.md
	$(GO_MD2MAN) -in $< -out $@.tmp && touch $@.tmp && mv $@.tmp $@

.PHONY: docs
docs: $(MANPAGES_MD:%.md=%)

dockertar-sha256-helper: dockertar-sha256-helper.go
	$(GO) build dockertar-sha256-helper.go

gotar: gotar.go
	$(GO) build -o $@ $<

.PHONY: clean
clean:
	$(PYTHON) setup.py clean
	-rm -rf dist build *~ \#* *pyc .#* docs/*.1

.PHONY: install-only
install-only:
	$(PYTHON) setup.py install --install-scripts /usr/share/atomic `test -n "$(DESTDIR)" && echo --root $(DESTDIR)`

	(cd $(DESTDIR)/$(PYTHONSITELIB) && rm -f atomic-$(VERSION)-*egg-info)

	install -d -m 0755 $(DESTDIR)/usr/bin
	ln -fs ../share/atomic/atomic $(DESTDIR)/usr/bin/atomic

	install -d -m 0755 $(DESTDIR)/usr/libexec/atomic
	install -m 0755 dockertar-sha256-helper migrate.sh gotar gomtree $(DESTDIR)/usr/libexec/atomic

	[ -d $(SYSCONFDIR) ] || mkdir -p $(SYSCONFDIR)
	install -m 644 atomic.sysconfig $(SYSCONFDIR)/atomic

	[ -d $(PROFILEDIR) ] || mkdir -p $(PROFILEDIR)
	install -m 644 atomic.sh $(PROFILEDIR)

	install -d $(PREFIX)/share/man/man1
	install -m 644 $(basename $(MANPAGES_MD)) $(PREFIX)/share/man/man1

	echo ".so man1/atomic-push.1" > $(PREFIX)/share/man/man1/atomic-upload.1

	install -m 644 atomic.conf $(DESTDIR)/etc

	install -d $(DESTDIR)/etc/atomic.d

.PHONY: install
install: all install-only


.PHONY: install-openscap
install-openscap:
	install -m 644 atomic.d/openscap $(DESTDIR)/etc/atomic.d
