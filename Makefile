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
	grep -r TODO .
	grep -r FIXME .

.PHONY: clean
clean:
	find . -name '*.pyc' | xargs rm
