# $Id: $
PKGNAME=bodhi
PKGRPMFLAGS=--define "_topdir ${PWD}" --define "_specdir ${PWD}" --define "_sourcedir ${PWD}/dist" --define "_srcrpmdir ${PWD}" --define "_rpmdir ${PWD}" --define "_builddir ${PWD}"

default: all

all:
	@echo "Nothing to do"

.PHONY: docs
docs:
	epydoc -n bodhi -o docs/epydoc -u https://hosted.fedoraproject.org/projects/bodhi \
	`find bodhi -name '*.py'`

.PHONY: test
test:
	nosetests

.PHONY: todo
todo:
	grep -r --color=auto TODO bodhi/ || :
	grep -r --color=auto FIXME bodhi/ || :

.PHONY: clean
clean:
	find . -name '*.pyc' | xargs rm

.PHONY: dist
dist:
	python setup.py sdist --formats=bztar

.PHONY: build
build:
	python setup.py build

.PHONY: install
install:
	python setup.py install -O1 --skip-build --root $(DESTDIR)
	install -D bodhi/tools/bodhi-client.py $(DESTDIR)/usr/bin/bodhi

.PHONY: srpm
srpm: dist
	@rpmbuild -bs ${PKGRPMFLAGS} ${PKGNAME}.spec
