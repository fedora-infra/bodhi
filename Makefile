# $Id: $

.PHONY: docs
docs:
	epydoc -n bodhi -o docs/epydoc -u https://hosted.fedoraproject.org/projects/bodhi \
	`find bodhi -name '*.py'`

.PHONY: test
test:
	nosetests

.PHONY: todo
todo:
	grep -r TODO bodhi/ || :
	grep -r FIXME bodhi/ || :

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
	install -D tools/bodhi-client.py $(DESTDIR)/usr/bin/bodhi
