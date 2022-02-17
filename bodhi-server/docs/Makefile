# Makefile for Sphinx documentation
#

# You can set these variables from the command line.
SPHINXOPTS    =
PYTHON = python3
SPHINXBUILD   = $(PYTHON) -m sphinx
PAPER         =
BUILDDIR      = _build

# Internal variables.
# PAPEROPT_a4     = -D latex_paper_size=a4
# PAPEROPT_letter = -D latex_paper_size=letter
ALLSPHINXOPTS   = $(SPHINXOPTS) .
# the i18n builder cannot share the environment and doctrees with the others
# I18NSPHINXOPTS  = $(PAPEROPT_$(PAPER)) $(SPHINXOPTS) .
# BODHI_SERVER_PATH = ../bodhi-server

.PHONY: help man

help:
	@echo "Please use \`make <target>' where <target> is one of"
	@echo "  man        to make manual pages"

man:
	$(SPHINXBUILD) -b man $(ALLSPHINXOPTS) $(BUILDDIR)
	@echo
	@echo "Build finished. The manual pages are in $(BUILDDIR)."
