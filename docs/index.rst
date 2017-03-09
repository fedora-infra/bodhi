.. bodhi documentation master file, created by
   sphinx-quickstart on Sat Aug 10 09:29:50 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.


Bodhi
=====

Bodhi is designed to democratize the package update testing and release process for RPM based Linux
distributions. It provides an interface for developers to propose updates to a distribution, and an
interface for testers to leave feedback about updates through a +1/-1 karma system.


Features of bodhi
-------------------

* Provides an interface for developers and release engineers to manage pushing out
  package updates for multiple version releases.
* Helps in delivering quality packages and repository sustainment with automated testing.
* Gives community testers an interface to leave feedback about package updates.
* Provides a framework that will allow future integrations to various other QA and
  developer tools.
* Announces the arrival of new packages entering the collection.
* Bodhi publishes end-user release notes known as errata.
* Generates yum repositories.
* Queries ResultsDB for automated test results and displays them on updates.
* Provides pre-release test updates for end user and QA folks/users who wish to test these updates.


Links
^^^^^

* `Online documentation <http://bodhi.readthedocs.io>`_
*  IRC: #bodhi on Freenode
* `Mailing list <https://lists.fedoraproject.org/archives/list/bodhi@lists.fedorahosted.org/>`_
* `Report an issue <https://github.com/fedora-infra/bodhi/issues/new>`_
* `Source code <https://github.com/fedora-infra/bodhi>`_
* `Fedora's production instance <https://bodhi.stg.fedoraproject.org/>`_
* `Fedora's staging instance <https://bodhi.stg.fedoraproject.org/>`_


Contents:

.. toctree::
   :maxdepth: 2

   man_pages/index
   python_bindings
   developer_docs
   rest_api/index
   release_notes


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
