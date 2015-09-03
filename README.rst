bodhi v2.0
==========

Setup virtualenvwrapper
-----------------------
``sudo yum -y install python-virtualenvwrapper python-createrepo_c``

Add the following to your `~/.bashrc`::

    export WORKON_HOME=$HOME/.virtualenvs
    source /usr/bin/virtualenvwrapper.sh

Bootstrap the virtualenv
------------------------
::

    ./bootstrap.py
    workon bodhi-python2.7

Run the test suite
------------------
``python setup.py test``

Migrating Bodhi from v1.0 to v2.0
---------------------------------
::

    curl -O https://infrastructure.fedoraproject.org/infra/db-dumps/bodhi2.dump.xz
    xzcat bodhi2.dump.xz | psql -U postgres -W

Adjust the development.ini file
-------------------------------

Adjust the configuration key ``sqlalchemy.url`` to point to the postgresql
database.
Something like:
::

    sqlalchemy.url = postgresql://user:password@localhost/bodhi2

Run the web app
---------------
``pserve development.ini --reload``
