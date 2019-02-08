=======
Vagrant
=======

`Vagrant`_ allows contributors to get quickly up and running with a Bodhi development environment by
automatically configuring a virtual machine. Before you get started, ensure that your host machine
has virtualization extensions enabled in its BIOS so the guest doesn't go slower than molasses. To
get started, simply use these commands::

    $ sudo dnf install ansible libvirt vagrant-libvirt vagrant-sshfs
    $ sudo systemctl enable libvirtd
    $ sudo systemctl start libvirtd

Check out the code and run ``vagrant up``::

    $ git clone https://github.com/fedora-infra/bodhi
    $ cd bodhi
    $ vagrant up

The ``Vagrantfile`` sets up a port forward from the host machine's port 6543 into the Vagrant
guest's port 6543, so you can now visit http://localhost:6543 with your browser to see your Bodhi
development instance if your browser is on the same host as the Vagrant host. If not, you will need
to connect to port 6543 on your Vagrant host, which is an exercise left for the reader.

The ``Vagrantfile`` also sets up a port forward from the host machine's port
15672 to the Vagrant guest's port 15672. The Vagrant guest runs an AMQP message
broker (RabbitMQ) which has a web interface for monitoring and administration
at http://localhost:15672. The default username is "guest" and the password is
"guest".


.. _Vagrant: https://www.vagrantup.com


Quick tips about the Bodhi Vagrant environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


You can ssh into your running Vagrant box like this::

    # Make sure your bodhi checkout is your shell's cwd
    $ vagrant ssh

Once you are inside the development environment, there are a helpful set of commands in your
``.bashrc`` that will be printed to the screen via the ``/etc/motd`` file. Be sure to familiarize
yourself with these:

.. include:: ../../devel/ansible/roles/bodhi/files/motd
   :literal:

Keep in mind that all ``vagrant`` commands should be run with your current working directory set to
your Bodhi checkout. The code from your development host will be mounted in ``/home/vagrant/bodhi``
in the guest. You can edit this code on the host, and the vagrant-sshfs plugin will cause the
changes to automatically be reflected in the guest's ``/home/vagrant/bodhi`` folder.

The development server is run inside the Vagrant environment by the ``bodhi.service`` systemd unit.
You can use ``bodhi-shell`` to get a Python shell quickly set up with a nice environment for you to hack
in. Here's an example where we use ``bodhi-shell`` to set an update's request to stable::

	[vagrant@bodhi-dev bodhi]$ bodhi-shell
	2017-11-02 21:08:56,359 INFO  [bodhi][MainThread] Using the FakeBugTracker
	2017-11-02 21:08:56,359 DEBUG [bodhi][MainThread] Using DevBuildsys
	Python 2.7.13 (default, May 10 2017, 20:04:28) 
	Type "copyright", "credits" or "license" for more information.

	IPython 3.2.1 -- An enhanced Interactive Python.
	?         -> Introduction and overview of IPython's features.
	%quickref -> Quick reference.
	help      -> Python's own help system.
	object?   -> Details about 'object', use 'object??' for extra details.

	Environment:
	  app          The WSGI application.
	  registry     Active Pyramid registry.
	  request      Active request object.
	  root         Root of the default resource tree.
	  root_factory Default root factory used to create `root`.

	Custom Variables:
	  m            bodhi.server.models
	  s            bodhi.server.Session

	In [1]: u = m.Update.query.filter_by(alias='FEDORA-2016-840ff89708').one()

	In [2]: u.request = m.UpdateRequest.stable

	In [3]: s().commit()

When you are done with your Vagrant guest, you can destroy it permanently by running this command on
the host::

    $ vagrant destroy

If you wish to use a custom ``Vagrantfile``, you can set the environment variable
``VAGRANT_VAGRANTFILE`` as a path to a script.


Authentication
^^^^^^^^^^^^^^

The Vagrant environment will configure Bodhi server and Bodhi's CLI to use Fedora's staging Ipsilon
server for authentication. This means you will need to ensure you have an account on Fedora's
staging account system. If you need to make an account, you can do so
`here <https://admin.stg.fedoraproject.org/accounts/>`_. This is done to prevent accidental changes
to Fedora's production instance during development.
