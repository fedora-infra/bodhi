XMLINFILES=$(wildcard *.xml.in)
XMLFILES = $(patsubst %.xml.in,%.xml,$(XMLINFILES))

all: po $(XMLFILES)

po: $(XMLINFILES)
	make -C po -f Makefile || exit 1

clean:
	@rm -fv *~ *.xml

%.xml: %.xml.in
	@python -c 'import libxml2; libxml2.parseFile("$<")'
	@if test ".$(CLEANUP)" == .yes; then xsltproc --novalid -o $< comps-cleanup.xsl $<; fi
	./update-comps $@
	@if [ "$@" == "$(RAWHIDECOMPS)" ] ; then \
		cat $(RAWHIDECOMPS) | sed 's/redhat-release/rawhide-release/g' > comps-rawhide.xml ; \
	fi

# Add an easy alias to generate a rawhide comps file
comps-rawhide: comps-f10.xml
	@mv comps-f10.xml comps-rawhide.xml
