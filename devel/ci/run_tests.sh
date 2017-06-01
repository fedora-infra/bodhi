#!/usr/bin/bash

sudo yum install python2-fedmsg-atomic-composer python-flake8 python-nose python-webtest python-mock python-pyramid python-pyramid-mako python-pyramid-tm python-waitress python-colander python-cornice python-openid python-pyramid-fas-openid python-sqlalchemy python-webhelpers python-progressbar python-bunch python-cryptography python-pillow python-kitchen python-pylibravatar python-fedora python-pydns python-dogpile-cache python-arrow python-markdown python-librepo python-createrepo_c createrepo_c python-bugzilla python-simplemediawiki fedmsg python-click python-webob1.4

mv development.ini.example development.ini

PYTHONPATH=. /usr/bin/python setup.py nosetests
