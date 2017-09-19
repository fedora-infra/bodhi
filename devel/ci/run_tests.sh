#!/usr/bin/bash -ex

sed -i '/pyramid_debugtoolbar/d' setup.py
sed -i '/pyramid_debugtoolbar/d' development.ini.example

sudo yum install -y epel-release

# gcc is used to build some dependencies pulled from pypi for coverage.
# git is needed for diff_cover to work.
# python-devel is needed for some of the pypi deps when gcc is run.
# pip is needed to install some things below.
sudo yum install -y gcc git python-devel python2-pip

# We want a newer version of flake8 than EL 7 has, because the EL 7 version fails and we only really
# care about it for devs, who use Fedora.
sudo pip install diff_cover flake8 pytest-cov tox

sudo yum install -y\
    createrepo_c\
    fedmsg\
    koji\
    liberation-mono-fonts\
    packagedb-cli\
    python-alembic\
    python-arrow\
    python-bleach\
    python-bugzilla\
    python-bunch\
    python-click\
    python-colander\
    python-cornice\
    python-createrepo_c\
    python-cryptography\
    python-dogpile-cache\
    python-fedora\
    python-kitchen\
    python-librepo\
    python-markdown\
    python-mock\
    python-openid\
    python-pillow\
    python-progressbar\
    python-pydns\
    python-pylibravatar\
    python-pyramid-fas-openid\
    python-pyramid-mako\
    python-pyramid-tm\
    python-pyramid\
    python-simplemediawiki\
    python-sqlalchemy\
    python-sqlalchemy_schemadisplay\
    python-waitress\
    python-webhelpers\
    python-webob1.4\
    python-webtest\
    python2-fedmsg-atomic-composer\

mv development.ini.example development.ini

sudo /usr/bin/python setup.py develop

/usr/bin/pytest
/usr/bin/tox -e pydocstyle,flake8

diff-cover coverage.xml --compare-branch=origin/develop --fail-under=100
