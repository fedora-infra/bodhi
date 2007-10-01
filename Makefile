# $Id: $
PKGNAME=bodhi
PKGRPMFLAGS=--define "_topdir ${PWD}" --define "_specdir ${PWD}" --define "_sourcedir ${PWD}/dist" --define "_srcrpmdir ${PWD}" --define "_rpmdir ${PWD}" --define "_builddir ${PWD}"

default: all

all:
	@echo "Nothing to do"

docs:
	epydoc -n bodhi -o docs/epydoc -u https://hosted.fedoraproject.org/projects/bodhi \
	`find bodhi -name '*.py'`

test:
	nosetests

todo:
	grep -r --color=auto TODO bodhi/ || :
	grep -r --color=auto FIXME bodhi/ || :

clean:
	find . -name '*.pyc' | xargs rm

dist:
	python setup.py sdist --formats=bztar

build:
	python setup.py build

install:
	python setup.py install -O1 --skip-build --root $(DESTDIR)
	install -D bodhi/tools/bodhi-client.py $(DESTDIR)/usr/bin/bodhi

srpm: dist
	@rpmbuild -bs ${PKGRPMFLAGS} ${PKGNAME}.spec

pyflakes:
	find . -name '*.py' | xargs pyflakes

profile:
	nosetests --with-profile --profile-stats-file=nose.prof
	python -c "import hotshot.stats ; stats = hotshot.stats.load('nose.prof') ; stats.sort_stats('time', 'calls') ; stats.print_stats(20)"

.PHONY: docs test todo clean dist build install srpm pyflakes
