=======================
Developer documentation
=======================

This page contains information for developers who wish to contribute to Bodhi.


Contribution guidelines
=======================

Before you submit a pull request to Bodhi, please ensure that it meets these criteria:

* All tests must pass.
* New code must have 100% test coverage. This one is particularly important, as we don't want to
  deploy any broken code into production. After you've run ``btest``, you can verify your new code's
  test coverage with ``bdiff-cover`` in the Vagrant environment, or
  ``diff-cover coverage.xml --compare-branch=origin/develop --fail-under=100`` if you are not using
  Vagrant.
* New functions, methods, and classes must have docblocks that explain what the code block is, and
  describing any parameters it accepts and what it returns (if anything). You can use the
  ``pydocstyle`` utility to automatically check your code for this. There is a
  ``bodhi.tests.test_style.TestStyle.test_code_with_pydocstyle`` test, that is slowly being expanded
  to enforce PEP-257 across the codebase.
* New code must follow `PEP-8 <https://www.python.org/dev/peps/pep-0008/>`_. You can use the
  ``flake8`` utility to automatically check your code. There is a
  ``bodhi.tests.test_style.TestStyle.test_code_with_flake8`` to enforce this style.
* Add an entry to ``docs/release_notes.rst`` for any changes you make that should be in release
  notes.
* Make sure your commits are atomic. Each commit should focus on one improvement or bug fix. If you
  need to build upon changes that are related but aren't atomic, feel free to send more than one
  commit in the same pull request.
* Your commit messages must include a Signed-off-by tag with your name and e-mail address,
  indicating that you agree to the
  `Developer Certificate of Origin <https://developercertificate.org/>`_. Bodhi uses version 1.1 of
  the certificate, which reads::

   Developer Certificate of Origin
   Version 1.1

    Copyright (C) 2004, 2006 The Linux Foundation and its contributors.
    1 Letterman Drive
    Suite D4700
    San Francisco, CA, 94129

    Everyone is permitted to copy and distribute verbatim copies of this
    license document, but changing it is not allowed.


    Developer's Certificate of Origin 1.1

    By making a contribution to this project, I certify that:

    (a) The contribution was created in whole or in part by me and I
        have the right to submit it under the open source license
        indicated in the file; or

    (b) The contribution is based upon previous work that, to the best
        of my knowledge, is covered under an appropriate open source
        license and I have the right under that license to submit that
        work with modifications, whether created in whole or in part
        by me, under the same open source license (unless I am
        permitted to submit under a different license), as indicated
        in the file; or

    (c) The contribution was provided directly to me by some other
        person who certified (a), (b) or (c) and I have not modified
        it.

    (d) I understand and agree that this project and the contribution
        are public and that a record of the contribution (including all
        personal information I submit with it, including my sign-off) is
        maintained indefinitely and may be redistributed consistent with
        this project or the open source license(s) involved.

  For example, Randy Barlow's commit messages include this line::

   Signed-off-by: Randy Barlow <randy@electronsweatshop.com>
* Code may be submitted by opening a pull request at
  `github.com/fedora-infra/bodhi <https://github.com/fedora-infra/bodhi/>`_, or you may e-mail a
  patch to the
  `mailing list <https://lists.fedoraproject.org/archives/list/bodhi@lists.fedorahosted.org/>`_.


CI Tests
========

All Bodhi pull requests are tested in a `Jenkins instance <https://ci.centos.org/job/bodhi-bodhi/>`_
that is graciously hosted for us by the CentOS Project. Sometimes tests fail, and when they do you
can visit the test job that failed and view its console output. This will display the output from
the ``devel/ci/run_tests.sh`` script. That script runs Bodhi's test suite on a variety of
Fedora versions using containers.

It is possible for you to run these same tests locally. There is a ``devel/run_tests.sh`` script
that is used by ``devel/ci/run_tests.sh`` and does the heavy lifting. This script is intended to be
run as root since it uses ``docker``. It has a handy ``-x`` flag that will cause it to exit
immediately upon failure. You can also set the ``RELEASES`` environment variable to a list of Fedora
releases you wish to test in a given run. Thus, if I want to run the tests on only f26 and f27 and I
want it to exit immediately upon failure, I can execute the script like this::

    # RELEASES="f26 f27" ./devel/run_tests.sh

The CI system does not halt immediately upon failure, so that you can see all the problems at once.
Sometimes this makes it difficult to tell where the failure happened when looking at the console
output on the CI server. Some common failures will print out "JENKIES FAIL" to help with this. If
you browse to the console output on a job with failed tests, you can use your browser's text search
feature to find that string in the output to more quickly identify where the failure occurred.


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

``Vagrantfile.example`` sets up a port forward from the host machine's port 6543 into the Vagrant
guest's port 6543, so you can now visit http://localhost:6543 with your browser to see your Bodhi
development instance if your browser is on the same host as the Vagrant host. If not, you will need
to connect to port 6543 on your Vagrant host, which is an exercise left for the reader.


Quick tips about the Bodhi Vagrant environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


You can ssh into your running Vagrant box like this::

    # Make sure your bodhi checkout is your shell's cwd
    $ vagrant ssh

Once you are inside the development environment, there are a helpful set of commands in your
``.bashrc`` that will be printed to the screen via the ``/etc/motd`` file. Be sure to familiarize
yourself with these.

Keep in mind that all ``vagrant`` commands should be run with your current working directory set to
your Bodhi checkout. The code from your development host will be mounted in ``/home/vagrant/bodhi``
in the guest. You can edit this code on the host, and the vagrant-sshfs plugin will cause the
changes to automatically be reflected in the guest's ``/home/vagrant/bodhi`` folder.

The development server is run inside the Vagrant environment by the ``bodhi.service`` systemd unit.
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
``sudo dnf install libffi-devel postgresql-devel openssl-devel koji pcaro-hermit-fonts freetype-devel libjpeg-turbo-devel python-pillow zeromq-devel liberation-mono-fonts git gcc redhat-rpm-config fedora-cert python2-dnf yum``

Setup virtualenvwrapper
^^^^^^^^^^^^^^^^^^^^^^^
``sudo dnf -y install python-virtualenvwrapper python-createrepo_c createrepo_c``

Add the following to your `~/.bashrc`::

    export WORKON_HOME=$HOME/.virtualenvs
    source /usr/bin/virtualenvwrapper.sh

Set PYTHONPATH
^^^^^^^^^^^^^^

Add the following to your `~/.bashrc`

``export PYTHONPATH=$PYTHONPATH:$HOME/.virtualenvs``

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

``pip install psycopg2 pyramid_debugtoolbar``

Create the `development.ini <https://github.com/fedora-infra/bodhi/blob/develop/devel/development.ini.example>`_ file
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Copy ``devel/development.ini.example`` to ``development.ini``:
::

    cp devel/development.ini.example development.ini
    
Run the test suite
^^^^^^^^^^^^^^^^^^
``py.test``

Import the bodhi2 database
^^^^^^^^^^^^^^^^^^^^^^^^^^
::

    curl -O https://infrastructure.fedoraproject.org/infra/db-dumps/bodhi2.dump.xz
    sudo -u postgres createdb bodhi2
    sudo -u postgres psql -c "create role bodhi2;"
    xzcat bodhi2.dump.xz | sudo -u postgres psql bodhi2

.. note:: If you do not have a PostgreSQL server running, please see the
          instructions at the bottom of the file.


Adjust database configuration in `development.ini <https://github.com/fedora-infra/bodhi/blob/develop/devel/development.ini.example>`_ file
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
===============

The Bodhi database schema can be seen below.

.. figure:: images/database.png
   :align:  center

   Database schema.


