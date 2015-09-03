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

Import the bodhi2 database
--------------------------
::

    curl -O https://infrastructure.fedoraproject.org/infra/db-dumps/bodhi2.dump.xz
    xzcat bodhi2.dump.xz | psql -U postgres -W

.. note:: If you do not have a PostgreSQL server running, please see the
          instructions at the bottom of the file.

Adjust the development.ini file
-------------------------------

Adjust the configuration key ``sqlalchemy.url`` to point to the postgresql
database. Something like:
::

    sqlalchemy.url = postgresql://user:password@localhost/bodhi2

Run the web app
---------------
``pserve development.ini --reload``



Setup the postgresql server
---------------------------

1. Install postgresql
~~~~~~~~~~~~~~~~~~~~~
::

    dnf install postgresql-server


2. Setup the Database
~~~~~~~~~~~~~~~~~~~~~

As a privileged user on a Fedora system run the following:
::

    sudo postgresql-setup initdb


3. Adjust Postgresql Connection Settings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

As a privileged user on a Fedora system modify the pg_hba.conf file:
::

    vi /var/lib/pgsql/data/pg_hba.conf

Then adjust the content at the bottom of the file to match the following.

::

  # TYPE  DATABASE    USER        CIDR-ADDRESS          METHOD

  # "local" is for Unix domain socket connections only
  local   all         all                               ident sameuser
  # IPv4 local connections:
  #host    all         all         127.0.0.1/32          ident sameuser
  # IPv6 local connections:
  #host    all         all         ::1/128               ident sameuser

  host all all 0.0.0.0 0.0.0.0 md5
  host all all ::1/128         md5


If you need to make other modifications to postgresql please make them now.

4. Start Postgresql
~~~~~~~~~~~~~~~~~~~

As a privileged user on a Fedora system run the following:
::

    sudo systemctl start postgresql.service
