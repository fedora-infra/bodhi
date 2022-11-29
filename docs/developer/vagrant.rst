=======
Vagrant
=======

`Vagrant`_ allows contributors to get quickly up and running with a Bodhi development environment by
automatically configuring a virtual machine. Before you get started, ensure that your host machine
has virtualization extensions enabled in its BIOS so the guest is not slow. To
get started, simply use these commands::

    $ sudo dnf install ansible libvirt vagrant-libvirt vagrant-sshfs vagrant-hostmanager
    $ sudo systemctl enable libvirtd
    $ sudo systemctl start libvirtd

As of 2022, bodhi now uses OpenID Connect (OIDC) for authentication. For the vagrant development environment,
this requires a running FreeIPA and Ipsilon instance. Running tinystage
(https://github.com/fedora-infra/tiny-stage) will set these up. Ensure that tinystage is running before trying
to provision bodhi with vagrant. To set up tinystage::

    $ git clone https://github.com/fedora-infra/tiny-stage
    $ pushd tiny-stage/
	$ vagrant up
	$ popd

Next, check out the bodhi code and run ``vagrant up``::

    $ git clone https://github.com/fedora-infra/bodhi
    $ cd bodhi
    $ vagrant up

Your newly provisioned bodhi development instance is now available at https://bodhi-dev.example.com/.

The Vagrant guest runs an AMQP message broker (RabbitMQ) which has a web interface for monitoring and
administration of the Fedora Messaging queue at http://bodhi-dev.example.com:15672/. The default username
is ``guest`` and the password is ``guest``.


.. _Vagrant: https://www.vagrantup.com


Authentication
^^^^^^^^^^^^^^

The Vagrant environment will configure Bodhi server and Bodhi's CLI to use the tiny-stage Ipsilon
(https://ipsilon.tinystage.test) for authentication. The users are defined in the tiny-stage FreeIPA
instance (https://ipa.tinystage.test). There are many test users defined by default in the tinystage
FreeIPA instance, and the admin user is ``admin`` with a password ``password``.

During the Vagrant provisioning, two users are automatically added to the tinystage instance specifically
for enabling you to test Bodhi: ``tinystage_packager`` and ``tinystage_provenpackager``, both with
password ``password``. If you want to login with your username (or any username of your choice), just
edit the ``fas_username`` variable in the Vagrantfile and re-provision the VM. Be advised that this will
not be a copy of your real fas account, it will just have the same username with the default password
``password`` and fake complementary data.


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
