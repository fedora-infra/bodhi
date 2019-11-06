=====
Bodhi
=====

Welcome to Bodhi, Fedora's update gating system.

Bodhi is designed to democratize the package update testing and release process for RPM based Linux
distributions. It provides an interface for developers to propose updates to a distribution, and an
interface for testers to leave feedback about updates through a +1/-1 karma system.

Bodhi’s main features are:


- Provides an interface for developers and release engineers to manage pushing out package updates
  for multiple distribution versions.
- Generates pre-release test repositories for end users and testers to install proposed updates.
- Gives testers an interface to leave feedback about package updates, leading to higher quality
  package updates.
- Announces the arrival of new packages entering the collection.
- Publishes end-user release notes known as errata.
- Generates yum repositories.
- Queries ResultsDB for automated test results and displays them on updates.



Documentation
=============

You can read Bodhi's
`release notes <https://bodhi.fedoraproject.org/docs/user/release_notes.html>`_
and documentation
`online <https://bodhi.fedoraproject.org/docs>`_, or by installing it on your
Fedora system and pointing your browser at
``/usr/share/doc/bodhi-docs/html/index.html``::

    $ sudo dnf install bodhi-docs && firefox /usr/share/doc/bodhi-docs/html/index.html

If you are interested in contributing to Bodhi, you can read the
`developer documentation`_.

.. _developer documentation: https://bodhi.fedoraproject.org/docs/developer/index.html


IRC
===

Come join us on `Freenode <https://webchat.freenode.net/>`_! We've got two channels:

* #bodhi - We use this channel to discuss upstream bodhi development
* #fedora-apps - We use this channel to discuss Fedora's Bodhi deployment (it is more generally
  about all of Fedora's infrastructure applications.)
