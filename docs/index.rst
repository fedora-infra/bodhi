.. bodhi documentation master file, created by
   sphinx-quickstart on Sat Aug 10 09:29:50 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

=====
Bodhi
=====

Bodhi is designed to democratize the package update testing and release process for RPM based Linux
distributions. It provides an interface for developers to propose updates to a distribution, and an
interface for testers to leave feedback about updates through a +1/-1 karma system.


Bodhi's main features are:

* Provides an interface for developers and release engineers to manage pushing out
  package updates for multiple distribution versions.
* Generates pre-release test repositories for end users and testers to install proposed updates.
* Gives testers an interface to leave feedback about package updates, leading to
  higher quality package updates.
* Announces the arrival of new packages entering the collection.
* Publishes end-user release notes known as errata.
* Generates yum repositories.
* Queries ResultsDB for automated test results and displays them on updates.


User Guide
==========

.. toctree::
   :maxdepth: 2

   user/testing
   user/update_states
   user/buildroot_overrides
   user/man_pages/index

.. toctree::
   :maxdepth: 1

   user/release_notes


API Guide
=========

.. toctree::
   :maxdepth: 2

   server_api/index
   python_bindings


Contributor Guide
=================

.. toctree::
   :maxdepth: 2

   developer/index
   developer/releases
   developer/vagrant
   developer/virtualenv
   developer/models


Admin Guide
===========

.. toctree::
   :maxdepth: 2

   administration


Community
=========

Bodhi is maintained by the Fedora Project and its `source code`_ and `issue tracker`_ are on GitHub.
There is a `mailing list`_ and an IRC channel on `FreeNode`_, ``#bodhi`` for discussion about Bodhi.
Fedora runs a `production instance`_ and `staging instance`_. `Online documentation`_ is available
on both production and staging.


.. _source code: https://github.com/fedora-infra/bodhi
.. _issue tracker: https://github.com/fedora-infra/bodhi/issues
.. _mailing list: https://lists.fedoraproject.org/archives/list/bodhi@lists.fedorahosted.org/
.. _FreeNode: https://freenode.net/
.. _production instance: https://bodhi.fedoraproject.org/
.. _staging instance: https://bodhi.stg.fedoraproject.org/
.. _Online documentation: https://bodhi.fedoraproject.org/docs/

