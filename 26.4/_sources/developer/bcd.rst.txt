=================================================
BCD - the Bodhi Container Development environment
=================================================

BCD is an Ansible-orchestrated, Podman-powered container-based development environment for Bodhi.
It lets you quickly and easily test your changes in a live Bodhi environment, without any external
dependencies, root privilege requirements, or virtual machines. It's also convenient for running
the unit tests.

To get started on a Fedora or Enterprise Linux-ish system, do::

    $ sudo dnf install ansible-core ansible-collection-containers-podman podman
    $ ./bcd run

Your newly provisioned bodhi development instance is now available at http://localhost.localdomain:6543/ .

The AMQP message broker web interface is available at http://localhost:15672/. The default username
is ``guest`` and the password is ``guest``.

The Waiverdb web interface is available at http://localhost:6544/ , and the Greenwave web interface
is available at http://localhost:6545/ .

The Ipsilon identity service web interface is available at http://localhost:6546/ (though there
isn't much reason to use it directly in this environment).

Other commands
^^^^^^^^^^^^^^

Other command commands are ``./bcd stop`` to stop all containers, ``./bcd remove`` to remove all
containers, ``./bcd clean`` to do remove plus remove all built images and update all base images,
``bcd logs (container)`` to view the logs for a container, ``bcd shell (container)`` to shell into
a container (the Bodhi container by default), and ``./bcd cis`` to clear Ipsilon's session cache.
This is necessary to log in to Bodhi as a different user - first log out, then run ``./bcd cis``,
then log in again. If you don't clear the session cache Ipsilon will just keep logging you in as
the same user. Run ``./bcd -h`` or ``./bcd (subcommand) -h`` for more help.

Containers
^^^^^^^^^^

Behind the scenes, BCD uses an Ansible playbook that controls a pod of Podman containers. The
pod is called ``bodhi-dev``. The full names of the containers are ``bodhi-dev-database``,
``bodhi-dev-waiverdb``, ``bodhi-dev-greenwave``, ``bodhi-dev-rabbitmq``, ``bodhi-dev-ipsilon`` and
``bodhi-dev-bodhi``. BCD commands which take a container name use shortened names with 'bodhi-dev-'
omitted, for convenience. You can interact with the pod and the containers directly using normal
podman commands if you wish - to start and stop individual containers, for instance.

The 'database' container runs postgresql and is initialized with a dump of real data for waiverdb
and Bodhi, both of which connect to it. The 'waiverdb' and 'greenwave' containers run those services
respectively, which are used by Bodhi for retrieving test results and test waivers and deciding
on the gating status of updates. Note that the 'greenwave' container is configured to connect to
the real, production ResultsDB and forward results from it, so the results shown and the gating
status calculated will change to reflect the real-world state. The 'rabbitmq' container runs an
instance of the RabbitMQ message broker which Bodhi will publish messages to and consume messages
from. The 'ipsilon' container runs the authentication service (see below for details). And, of
course, the 'bodhi' container runs Bodhi itself. It has your source tree mapped as a volume, so
changes you make to your source tree are immediately reflected in the development environment.
The server will automatically reload when any Python source file is changed.

The Bodhi container uses systemd, so you can shell into it and stop or restart the bodhi service
or any of the ancillary services it runs, if you need to.

Refreshing the bcd environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Once you've set up a bcd environment, it's kind of frozen, aside from the bodhi code itself.
All the containers will be built on whatever their 'latest' bases were are the time, but nothing
ever rebuilds or updates them by default. So after a while, your environment will be stale and
may not run newer Bodhi code correctly.

To easily completely refresh the bcd environment, run ``./bcd clean`` then ``./bcd run`` again.
This wipes all the existing containers and custom images, pulls the latest versions of all the
base images, then rebuilds the custom images and the containers.

Of course, any customizations, command history etc. within the containers will be lost. If you
want to do something more granular, you'll have to do it 'behind the scenes' with normal podman
commands to remove the container and/or images, pull base images, and rebuild.

Authentication
^^^^^^^^^^^^^^

The BCD environment uses an instance of the Ipsilon authentication service (as also used for
Fedora authentication in the real world). This instance is configured in testauth mode, which means
you can log in as any user at all with the password 'ipsilon'. If you log in as a user that does
not exist in the Bodhi database, it will be added.

Note that the group memberships and email addresses for real users are not the same as in the real
world. This Ipsilon instance is configured by default to say that all users are members of the
groups "fedora-contributors" and "packagers" and also a group of the same name as their username,
and have the email address "username@example.com". These values will be changed in the Bodhi
database on login.

There is a special mechanism for testing different group memberships. You can login with a username
like 'someuser:groups=somegroup1,somegroup2' to log in as user 'someuser' but with your groups
reported as 'somegroup1' and 'somegroup2' (you will *not* be reported as a member of 'packagers'
or 'fedora-contributors' in this case). You can also take advantage of the 'user is a member of
the group with the same name' mechanism, e.g. by logging in as 'provenpackager' to be reported as
a member of the 'provenpackager' group.

As mentioned above, switching users can be a bit tricky, as Ipsilon likes to cache the session
(this is sort of what it's supposed to do, after all). To switch users, log out, run ``./bcd cis``,
then log in again. If things get really messy you may need to stop and remove the bodhi and ipsilon
containers to get back to a clean state.

Quick tips about the BCD environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can shell into the running Bodhi container like this::

    # Make sure your bodhi checkout is your shell's cwd
    $ ./bcd shell

Note the container must be running, or this will fail. Once you are inside the development
environment, there are a helpful set of commands in your ``.bashrc`` that will be printed to the
screen via the ``/etc/motd`` file. Be sure to familiarize yourself with these:

.. include:: ../../devel/ansible-podman/containers/bodhi/motd
   :literal:

The code from your development host will be mounted in ``/bodhi`` in the Bodhi container.
You can edit this code on the host, and the changes will automatically be reflected in the container.

The development server is run inside the container by the ``bodhi.service`` systemd unit.
You can use ``bodhi-shell`` to get a Python shell quickly set up with a nice environment for you to hack
in. Here's an example where we use ``bodhi-shell`` to set an update's request to stable::

	[root@bodhi-dev bodhi]# bodhi-shell
    Python 3.12.0 (main, Oct  2 2023, 00:00:00) [GCC 13.2.1 20230918 (Red Hat 13.2.1-3)] on linux
    Type "help" for more information.

    Environment:
      app          The WSGI application.
      registry     Active Pyramid registry.
      request      Active request object.
      root         Root of the default resource tree.
      root_factory Default root factory used to create `root`.

    Custom Variables:
      m            bodhi.server.models
      s            bodhi.server.Session

    >>> u = m.Update.query.filter_by(alias='FEDORA-2016-840ff89708').one()
    >>> u.request = m.UpdateRequest.stable
    >>> s().commit()
