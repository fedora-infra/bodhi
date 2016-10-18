=============================
bodhi development environment
=============================

There are two ways to bootstrap a Bodhi development environment. You can use Vagrant, or you can use
virtualenv on an existing host.


Vagrant
=======

`Vagrant <https://www.vagrantup.com/>`_ allows contributors to get quickly up and running with a
Bodhi development environment by automatically configuring a virtual machine. Before you get
started, ensure that your host machine has virtualization extensions enabled in its BIOS so the
guest doesn't go slower than molasses. To get started, simply
use these commands::

    $ sudo dnf install ansible libvirt vagrant-libvirt vagrant-sshfs
    $ sudo systemctl enable libvirtd
    $ sudo systemctl start libvirtd
    $ cp Vagrantfile.example Vagrantfile
    # Make sure your bodhi checkout is your shell's cwd
    $ vagrant up
    $ vagrant ssh -c "cd /vagrant/; pserve development.ini --reload"

``Vagrantfile.example`` sets up a port forward from the host machine's port 6543 into the Vagrant
guest's port 6543, so you can now visit http://localhost:6543 with your browser to see your Bodhi
development instance if your browser is on the same host as the Vagrant host. If not, you will need
to connect to port 6543 on your Vagrant host, which is an exercise left for the reader.


Quick tips about the Bodhi Vagrant environment
----------------------------------------------


You can ssh into your running Vagrant box like this::

    # Make sure your bodhi checkout is your shell's cwd
    $ vagrant ssh

Keep in mind that all ``vagrant`` commands should be run with your current working directory set to
your Bodhi checkout. The code from your development host will be mounted in ``/vagrant`` in the
guest. You can edit this code on the host, and the vagrant-sshfs plugin will cause the changes to
automatically be reflected in the guest's ``/vagrant`` folder.

You can run the unit tests within the guest with nosetests::

    $ cd /vagrant
    $ nosetests -v

You can run the development server from inside the Vagrant environment::

    $ pserve /vagrant/development.ini --reload

It is possible to connect your Vagrant box to the staging Koji instance for testing, which can be
handy at times. You will need to copy your ``.fedora.cert`` and ``.fedora-server-ca.cert`` that you
normally use to connect to Koji into your Vagrant box, storing them in ``/home/vagrant``. Once you
have those in place, you can set ``buildsystem = koji`` in your ``development.ini`` file.

When you are done with your Vagrant guest, you can destroy it permanently by running this command on
the host::

    $ vagrant destroy


Virtualenv
==========

Virtualenv is another option for building a development environment.

Dependencies
------------
``sudo dnf install libffi-devel postgresql-devel openssl-devel koji pcaro-hermit-fonts freetype-devel libjpeg-turbo-devel python-pillow zeromq-devel``

Setup virtualenvwrapper
-----------------------
``sudo dnf -y install python-virtualenvwrapper python-createrepo_c``

Add the following to your `~/.bashrc`::

    export WORKON_HOME=$HOME/.virtualenvs
    source /usr/bin/virtualenvwrapper.sh

Set PYTHONPATH
--------------

Add the following to your `~/.bashrc`

``export PYTHONPATH=$PYTHONPATH:$HOME/.virtualenv``

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

Create the `development.ini <https://github.com/fedora-infra/bodhi/blob/develop/development.ini.example>`_ file
---------------------------------------------------------------------------------------------------------------

Copy ``development.ini.example`` to ``development.ini``:
::

    cp development.ini.example development.ini
    
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


Adjust database configuration in `development.ini <https://github.com/fedora-infra/bodhi/blob/develop/development.ini.example>`_ file
-------------------------------------------------------------------------------------------------------------------------------------

Set the configuration key
`sqlalchemy.url <https://github.com/fedora-infra/bodhi/blob/02d0a883c156d9a27a4dbac994409ecf726d00a9/development.ini#L413>`_
to point to the postgresql database. Something like:
::

    sqlalchemy.url = postgresql://postgres:anypasswordworkslocally@localhost/bodhi2


Upgrade the database
--------------------
``alembic upgrade head``


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


Meetings
========

There is a meeting every four weeks between Bodhi developers and stakeholder,
held on IRC. If you would like to attend, you can see details here:

https://apps.fedoraproject.org/calendar/meeting/4667/


IRC
===

Come join us on `Freenode <https://freenode.net/>`_! We've got two channels:

* #bodhi - We use this channel to discuss upstream bodhi development
* #fedora-apps - We use this channel to discuss Fedora's Bodhi deployment (it is more generally
  about all of Fedora's infrastructure applications.)
