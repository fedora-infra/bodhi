=======================
Developer documentation
=======================

This page contains information for developers who wish to contribute to Bodhi.


Contribution guidelines
=======================

Before you submit a pull request to Bodhi, please ensure that it meets these criteria:

* All tests must pass.
* New code should have 100% test coverage. This one is particularly important, as we don't want to
  deploy any broken code into production.
* New functions, methods, and classes should have docblocks that explain what the code block is, and
  describing any parameters it accepts and what it returns (if anything).
* New code should follow `PEP-8 <https://www.python.org/dev/peps/pep-0008/>`_. You can use the
  ``flake8`` utility to automatically check your code. There is a
  ``bodhi.tests.test_style.TestStyle.test_code_with_flake8`` test, that is slowly being expanded to
  enforce PEP-8 across the codebase.


Create a Bodhi development environment
======================================

There are two ways to bootstrap a Bodhi development environment. You can use Vagrant, or you can use
virtualenv on an existing host.


Vagrant
-------

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
    $ vagrant ssh -c "cd /home/vagrant/bodhi; pserve development.ini --reload"

``Vagrantfile.example`` sets up a port forward from the host machine's port 6543 into the Vagrant
guest's port 6543, so you can now visit http://localhost:6543 with your browser to see your Bodhi
development instance if your browser is on the same host as the Vagrant host. If not, you will need
to connect to port 6543 on your Vagrant host, which is an exercise left for the reader.


Quick tips about the Bodhi Vagrant environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


You can ssh into your running Vagrant box like this::

    # Make sure your bodhi checkout is your shell's cwd
    $ vagrant ssh

Keep in mind that all ``vagrant`` commands should be run with your current working directory set to
your Bodhi checkout. The code from your development host will be mounted in ``/home/vagrant/bodhi``
in the guest. You can edit this code on the host, and the vagrant-sshfs plugin will cause the
changes to automatically be reflected in the guest's ``/home/vagrant/bodhi`` folder.

You can run the unit tests within the guest with nosetests::

    $ cd /home/vagrant/bodhi
    $ python setup.py nosetests

You can run the development server from inside the Vagrant environment::

    $ pserve /home/vagrant/bodhi/development.ini --reload

You can use ``pshell`` and ``tools/shelldb.py`` to get a Python shell quickly set up with a nice
environment for you to hack in::

	[vagrant@localhost bodhi]$ pshell development.ini
	Python 2.7.12 (default, Sep 29 2016, 13:30:34)
	[GCC 6.2.1 20160916 (Red Hat 6.2.1-2)] on linux2
	Type "help" for more information.

	Environment:
	  app          The WSGI application.
	  registry     Active Pyramid registry.
	  request      Active request object.
	  root         Root of the default resource tree.
	  root_factory Default root factory used to create `root`.

	Custom Variables:
	  m            bodhi.server.models
	  t            transaction

	>>> execfile('tools/shelldb.py')

Once you've run that ``execfile('tools/shelldb.py')`` tools command, it's pretty easy to run
database queries::

	>>> db.query(m.Update).filter_by(alias='FEDORA-2016-840ff89708').one().title
	<output trimmed>
	u'gtk3-3.22.1-1.fc25'

It is possible to connect your Vagrant box to the staging Koji instance for testing, which can be
handy at times. You will need to copy your ``.fedora.cert`` and ``.fedora-server-ca.cert`` that you
normally use to connect to Koji into your Vagrant box, storing them in ``/home/vagrant``. Once you
have those in place, you can set ``buildsystem = koji`` in your ``development.ini`` file.

When you are done with your Vagrant guest, you can destroy it permanently by running this command on
the host::

    $ vagrant destroy


Virtualenv
----------

Virtualenv is another option for building a development environment.

Dependencies
^^^^^^^^^^^^
``sudo dnf install libffi-devel postgresql-devel openssl-devel koji pcaro-hermit-fonts freetype-devel libjpeg-turbo-devel python-pillow zeromq-devel liberation-mono-fonts``

Setup virtualenvwrapper
^^^^^^^^^^^^^^^^^^^^^^^
``sudo dnf -y install python-virtualenvwrapper python-createrepo_c``

Add the following to your `~/.bashrc`::

    export WORKON_HOME=$HOME/.virtualenvs
    source /usr/bin/virtualenvwrapper.sh

Set PYTHONPATH
^^^^^^^^^^^^^^

Add the following to your `~/.bashrc`

``export PYTHONPATH=$PYTHONPATH:$HOME/.virtualenv``

Then on the terminal ::

    source ~/.bashrc

Clone the source
^^^^^^^^^^^^^^^^
::

    git clone https://github.com/fedora-infra/bodhi.git
    cd bodhi

Bootstrap the virtualenv
^^^^^^^^^^^^^^^^^^^^^^^^
::

    ./bootstrap.py
    workon bodhi-python2.7

Setting up
^^^^^^^^^^
``python setup.py develop``

``pip install psycopg2``

Create the `development.ini <https://github.com/fedora-infra/bodhi/blob/develop/development.ini.example>`_ file
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Copy ``development.ini.example`` to ``development.ini``:
::

    cp development.ini.example development.ini
    
Run the test suite
^^^^^^^^^^^^^^^^^^
``python setup.py nosetests``

Import the bodhi2 database
^^^^^^^^^^^^^^^^^^^^^^^^^^
::

    curl -O https://infrastructure.fedoraproject.org/infra/db-dumps/bodhi2.dump.xz
    sudo -u postgres createdb bodhi2
    xzcat bodhi2.dump.xz | sudo -u postgres psql bodhi2

.. note:: If you do not have a PostgreSQL server running, please see the
          instructions at the bottom of the file.


Adjust database configuration in `development.ini <https://github.com/fedora-infra/bodhi/blob/develop/development.ini.example>`_ file
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Set the configuration key
`sqlalchemy.url <https://github.com/fedora-infra/bodhi/blob/02d0a883c156d9a27a4dbac994409ecf726d00a9/development.ini#L413>`_
to point to the postgresql database. Something like:
::

    sqlalchemy.url = postgresql://postgres:anypasswordworkslocally@localhost/bodhi2


Upgrade the database
^^^^^^^^^^^^^^^^^^^^
``alembic upgrade head``


Run the web app
^^^^^^^^^^^^^^^
``pserve development.ini --reload``



Setup the postgresql server
^^^^^^^^^^^^^^^^^^^^^^^^^^^

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


Database Schema
---------------

The Bodhi database schema can be seen below.

.. figure:: images/database.png
   :align:  center

   Database schema.


