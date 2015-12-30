bodhi v2.0
==========

Dependencies
------------
``sudo dnf install libffi-devel openssl-devel koji pcaro-hermit-fonts freetype-devel libjpeg-turbo-devel python-pillow``

Setup virtualenvwrapper
-----------------------
``sudo dnf -y install python-virtualenvwrapper python-createrepo_c``

Add the following to your `~/.bashrc`::

    export WORKON_HOME=$HOME/.virtualenvs
    source /usr/bin/virtualenvwrapper.sh

Then on the terminal ::

    source ~/.bashrc

Clone the source
----------------
::

    git clone https://github.com/fedora-infra/bodhi.git
    cd bodhi

Bootstrap the virtualenv
------------------------
::

    ./bootstrap.py
    workon bodhi-python2.7

Setting up
----------
``python setup.py develop``

``pip install psycopg2``

Run the test suite
------------------
``python setup.py test``

Import the bodhi2 database
--------------------------
::

    curl -O https://infrastructure.fedoraproject.org/infra/db-dumps/bodhi2.dump.xz
    sudo -u postgres createdb bodhi2
    xzcat bodhi2.dump.xz | sudo -u postgres psql bodhi2

.. note:: If you do not have a PostgreSQL server running, please see the
          instructions at the bottom of the file.

Adjust the `development.ini <https://github.com/fedora-infra/bodhi/blob/develop/development.ini>`_ file
-------------------------------

Adjust the configuration key `sqlalchemy.url <https://github.com/fedora-infra/bodhi/blob/02d0a883c156d9a27a4dbac994409ecf726d00a9/development.ini#L413>`_ to point to the postgresql
database. Something like:
::

    sqlalchemy.url = postgresql://postgres:anypasswordworkslocally@localhost/bodhi2

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

  # TYPE  DATABASE        USER            ADDRESS                 METHOD

  # "local" is for Unix domain socket connections only
  local   all             all                                     peer
  # IPv4 local connections are *trusted*, any password will work.
  host    all             all             127.0.0.1/32            trust
  # IPv6 local connections are *trusted*, any password will work.
  host    all             all             ::1/128                 trust

If you need to make other modifications to postgresql please make them now.

4. Start Postgresql
~~~~~~~~~~~~~~~~~~~

As a privileged user on a Fedora system run the following:
::

    sudo systemctl start postgresql.service
