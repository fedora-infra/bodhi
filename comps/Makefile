XMLINFILES=$(wildcard *.xml.in)
XMLFILES = $(patsubst %.xml.in,%.xml,$(XMLINFILES))

all: po $(XMLFILES)

po: $(XMLINFILES)
	make -C po -f Makefile || exit 1

clean:
	@rm -fv *~

%.xml: %.xml.in
	./update-comps $@
	@if [ "$@" == "$(RAWHIDECOMPS)" ] ; then \
		cat $(RAWHIDECOMPS) | sed 's/redhat-release/rawhide-release/g' > comps-rawhide.xml ; \
	fi

# Add an easy alias to generate a rawhide comps file
comps-rawhide: comps-f9.xml
	@mv comps-f9.xml comps-rawhide.xml
