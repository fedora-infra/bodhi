# $Id: $
PKGNAME=bodhi
PKGRPMFLAGS=--define "_topdir ${PWD}" --define "_specdir ${PWD}" --define "_sourcedir ${PWD}/dist" --define "_srcrpmdir ${PWD}" --define "_rpmdir ${PWD}" --define "_builddir ${PWD}"
RPMTOPDIR=$(shell rpm --eval='%{_topdir}')

default: all

all:
	@echo "Nothing to do"

docs:
	epydoc -n bodhi -o docs/epydoc -u https://fedorahosted.org/bodhi \
		`find bodhi -name '*.py'`

test:
	python bodhi_nose.py --processes=10

todo:
	grep -r --color=auto TODO bodhi/ || :
	grep -r --color=auto FIXME bodhi/ || :

clean:
	find . -name '*.pyc' | xargs rm -f
	rm -rf virtenv
	rm bodhi-pickledb.tar.bz2

dist:
	python setup.py sdist --formats=bztar

build:
	python setup.py build

install:
	python setup.py install -O1 --skip-build --root $(DESTDIR)
	install -D bodhi/tools/client.py $(DESTDIR)/usr/bin/bodhi

virt-install:
	virtualenv virtenv
	/bin/sh -c ". virtenv/bin/activate; python setup.py install -O1 --skip-build; install -D bodhi/tools/client.py virtenv/bin/bodhi"

shell:
	tg-admin --config=bodhi.cfg shell

srpm: dist
	@rpmbuild -bs ${PKGRPMFLAGS} ${PKGNAME}.spec

pyflakes:
	find . -name '*.py' | xargs pyflakes

init:
	python setup.py egg_info
	wget -N https://fedorahosted.org/releases/b/o/bodhi/bodhi-pickledb.tar.bz2
	tar -jxvf bodhi-pickledb.tar.bz2
	PYTHONPATH=$(pwd) tg-admin --config=bodhi.cfg sql create && PYTHONPATH=$(pwd) bodhi/tools/init.py && PYTHONPATH=$(pwd) bodhi/tools/dev_init.py && PYTHONPATH=$(pwd) bodhi/tools/pickledb.py load bodhi-pickledb-*
	# remove the untared pickledb
	rm bodhi-pickledb-*

run:
	python start-bodhi

profile:
	nosetests --with-profile --profile-stats-file=nose.prof
	python -c "import hotshot.stats ; stats = hotshot.stats.load('nose.prof') ; stats.sort_stats('time', 'calls') ; stats.print_stats(20)"

install-deps:
	su -c "yum install TurboGears python-TurboMail python-fedora python-sqlalchemy koji mash yum-utils git intltool python-bugzilla python-genshi \
python-crypto python-imaging python-turboflot python-tgcaptcha python-nose.noarch"

rpm: srpm
	@rpm -i bodhi*src.rpm
	@rpmbuild -ba ${RPMTOPDIR}/SPECS/${PKGNAME}.spec

.PHONY: docs test todo clean dist build install virt-install srpm pyflakes profile shell init run install-deps
