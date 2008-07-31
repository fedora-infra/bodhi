# $Id: $
PKGNAME=bodhi
PKGRPMFLAGS=--define "_topdir ${PWD}" --define "_specdir ${PWD}" --define "_sourcedir ${PWD}/dist" --define "_srcrpmdir ${PWD}" --define "_rpmdir ${PWD}" --define "_builddir ${PWD}"

default: all

all:
	@echo "Nothing to do"

docs:
	epydoc -n bodhi -o docs/epydoc -u https://fedorahosted.org/bodhi \
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
	install -D bodhi/tools/bodhi_client.py $(DESTDIR)/usr/bin/bodhi

shell:
	tg-admin --config=bodhi.cfg shell

srpm: dist
	@rpmbuild -bs ${PKGRPMFLAGS} ${PKGNAME}.spec

pyflakes:
	find . -name '*.py' | xargs pyflakes

init:
	tg-admin --config=bodhi.cfg sql create && bodhi/tools/init.py && bodhi/tools/dev_init.py && bodhi/tools/pickledb.py load bodhi-pickledb*

run:
	python start-bodhi

profile:
	nosetests --with-profile --profile-stats-file=nose.prof
	python -c "import hotshot.stats ; stats = hotshot.stats.load('nose.prof') ; stats.sort_stats('time', 'calls') ; stats.print_stats(20)"

rpm: srpm
	@rpm -i bodhi*src.rpm
	@rpmbuild -ba ~/rpmbuild/SPECS/bodhi.spec

.PHONY: docs test todo clean dist build install srpm pyflakes profile shell init run
