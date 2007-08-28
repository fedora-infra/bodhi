XMLFILES=$(addprefix ../, $(shell cat POTFILES.in))
POFILES=$(wildcard *.po)

# intltool hack
top_srcdir=..

all:

refresh-po: comps.pot $(POFILES)

%.po: comps.pot
	@if msgmerge $@ comps.pot > $@.new ; then \
		echo "msgmerge of $@ succeeded" ; \
		mv $@.new $@ ; \
		msgfmt -o /dev/null --statistics $@ ; \
	else \
		echo "msgmerge of $@ failed" ; \
		rm -f $@.new ; \
	fi

comps.pot: $(XMLFILES)
	intltool-update --pot --gettext-package=comps
	

report:
	for cat in *.po; do \
		echo -n "$$cat: "; \
		msgfmt -v --statistics -o /dev/null $$cat; \
	done
