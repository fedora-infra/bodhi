Release notes
=============

2.5.0
-----

Bodhi 2.5.0 is a feature and bugfix release.


Features
^^^^^^^^

* The web interface now uses the Fedora Bootstrap theme. The layout of the
  update page has also been revamped to display the information about an update
  in a clearer manner.
  (`#1313 <https://github.com/fedora-infra/bodhi/issues/1313>`_).
* The ``bodhi`` CLI now has a ``--url`` flag that can be used to switch which Bodhi server it
  communicates with. The ``BODHI_URL`` environment can also be used to configure this flag.


Bugs
^^^^
* The position of the Add Comment button is now the bottom right.
  (`#902 <https://github.com/fedora-infra/bodhi/issues/902>`_).


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* The Vagrant development environment automatically configures the BODHI_URL environment
  variable so that the client talks to the local server instead of production or staging.
* Test coverage is up another percentage to 82%.


2.4.0
-----

Bodhi 2.4.0 is a feature and bugfix release.


Features
^^^^^^^^
* The web interface now displays whether an update has autopush enabled
  (`#999 <https://github.com/fedora-infra/bodhi/issues/999>`_).
* Autopush is now disabled on any update that receives authenticated negative karma
  (`#1191 <https://github.com/fedora-infra/bodhi/issues/1191>`_).
* Bodhi now links to Koji builds via TLS instead of plaintext
  (`#1246 <https://github.com/fedora-infra/bodhi/issues/1246>`_).
* Some usage examples have been added to the ``bodhi`` man page.
* Bodhi's server package has a new script called ``bodhi-clean-old-mashes`` that can recursively
  delete any folders with names that end in a dash followed by a string that can be interpreted as a
  float, sparing the newest 10 by lexigraphical sorting. This should help release engineers keep the
  Koji mashing folder clean.
* There is now a ``bodhi.client.bindings`` module provided by the Bodhi client package. It contains
  Python bindings to Bodhi's REST API.
* The ``bodhi`` CLI now prints autokarma and thresholds when displaying updates.
* ``bodhi-push`` now has a ``--version`` flag.
* There are now man pages for ``bodhi-push`` and ``initialize_bodhi_db``.


Bugs
^^^^
* Users' e-mail addresses will now be updated when they log in to Bodhi
  (`#902 <https://github.com/fedora-infra/bodhi/issues/902>`_).
* The masher now tests for ``repomd.xml`` instead of the directory that contains it
  (`#908 <https://github.com/fedora-infra/bodhi/issues/908>`_).
* Users can now only upvote an update once
  (`#1018 <https://github.com/fedora-infra/bodhi/issues/1018>`_).
* Only comment on non-autokarma updates when they meet testing requirements
  (`#1009 <https://github.com/fedora-infra/bodhi/issues/1009>`_).
* Autokarma can no longer be set to NULL
  (`#1048 <https://github.com/fedora-infra/bodhi/issues/1048>`_).
* Users can now be more fickle than ever about karma
  (`#1064 <https://github.com/fedora-infra/bodhi/issues/1064>`_).
* Critical path updates can now be free of past negative karma ghosts
  (`#1065 <https://github.com/fedora-infra/bodhi/issues/1065>`_).
* Bodhi now comments on non-autokarma updates after enough time has passed
  (`#1094 <https://github.com/fedora-infra/bodhi/issues/1094>`_).
* ``bodhi-push`` now does not crash when users abort a push
  (`#1107 <https://github.com/fedora-infra/bodhi/issues/1107>`_).
* ``bodhi-push`` now does not print updates when resuming a push
  (`#1113 <https://github.com/fedora-infra/bodhi/issues/1113>`_).
* Bodhi now says "Log in" and "Log out" instead of "Login" and "Logout"
  (`#1146 <https://github.com/fedora-infra/bodhi/issues/1146>`_).
* Bodhi now configures the Koji client to retry, which should help make the masher more reliable
  (`#1201 <https://github.com/fedora-infra/bodhi/issues/1201>`_).
* Bodhi is now compatible with Pillow-4.0.0
  (`#1262 <https://github.com/fedora-infra/bodhi/issues/1262>`_).
* The bodhi cli no longer prints update JSON when setting the request
  (`#1408195 <https://bugzilla.redhat.com/show_bug.cgi?id=1408195>`_).
* Bodhi's signed handler now skips builds that were not assigned to a release.
* The comps file is now cloned into an explicit path during mashing.
* The buildsystem is now locked during login.


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^
* A great deal of tests were written for Bodhi. Test coverage is now up to 81% and is enforced by
  the test suite.
* Bodhi's server code is now PEP-8 compliant.
* The docs now contain contribution guidelines.
* The build system will now fail with a useful Exception if used without being set up.
* The Vagrantfile is a good bit fancier, with hostname, dnf caching, unsafe but performant disk I/O,
  and more.
* The docs now include a database schema image.
* Bodhi is now run by systemd in the Vagrant guest.
* The Vagrant environment now has several helpful shell aliases and a helpful MOTD to advertise
  them to developers.
* The development environment now uses Fedora 25 by default.
* The test suite is less chatty, as several unicode warnings have been fixed.


Dependency change
^^^^^^^^^^^^^^^^^
* Bodhi server now depends on click for ``bodhi-push``.


Release contributors
^^^^^^^^^^^^^^^^^^^^

The following contributors submitted patches for Bodhi 2.4.0:

* Trishna Guha
* Patrick Uiterwijk
* Jeremy Cline
* Till Mass
* Josef Sukdol
* Clement Verna
* andreas
* Ankit Raj Ojha
* Randy Barlow


2.3.3
-----

Bodhi 2.3.3 converts koji auth to be done with krb5 and fixes one bug:

* Use krb5 for koji
  (`#1129 <https://github.com/fedora-infra/bodhi/pull/1129>`_).
* Disable caching koji sessions during mashing process
  (`#1134 <https://github.com/fedora-infra/bodhi/pull/1134>`_).


Thanks to Patrick Uiterwijk for contributing both of these commits!


2.3.2
-----

Bodhi 2.3.2 is a bugfix release that addresses the following issues:

* ``push.py`` now defaults to the current releases
  (`#1071 <https://github.com/fedora-infra/bodhi/issues/1071>`_).
* Fixed a typo in the masher in sending an ostree compose message
  (`#1072 <https://github.com/fedora-infra/bodhi/pull/1072>`_).
* Fixed a typo in looking up an e-mail template
  (`#1073 <https://github.com/fedora-infra/bodhi/issues/1073>`_).
* The fedmsg name is now passed explicitly
  (`#1079 <https://github.com/fedora-infra/bodhi/pull/1079>`_).
* The man page was corrected to state that builds should be comma separated
  (`#1095 <https://github.com/fedora-infra/bodhi/pull/1095>`_).
* Fixed a race condition between robosignatory and the signed handler
  (`#1111 <https://github.com/fedora-infra/bodhi/issues/1111>`_).
* Fix querying the updates for resumption in ``push.py``
  (`e7cb3f13 <https://github.com/fedora-infra/bodhi/commit/e7cb3f13>`_).
* ``push.py`` now prompts for the username if not given
  (`abeca57e <https://github.com/fedora-infra/bodhi/commit/abeca57e>`_).


Release contributors
^^^^^^^^^^^^^^^^^^^^

The following contributors authored patches for 2.3.2:

* Patrick Uiterwijk
* Randy Barlow


2.3.1
-----

Bodhi 2.3.1 fixes `#1067 <https://github.com/fedora-infra/bodhi/issues/1067>`_,
such that edited updates now tag new builds into the ``pending_signing_tag``
instead of the ``pending_testing_tag``. This is needed for automatic signing
gating to work.


2.3.0
-----

Bodhi 2.3.0 is a feature and bug fix release.

Features
^^^^^^^^

* The package input field is now autofocused when creating new updates
  (`#876 <https://github.com/fedora-infra/bodhi/pull/876>`_).
* Releases now have a ``pending_signing_tag``
  (`3fe3e219 <https://github.com/fedora-infra/bodhi/commit/3fe3e219>`_).
* fedmsg notifications are now sent during ostree compositions
  (`b972cad0 <https://github.com/fedora-infra/bodhi/commit/b972cad0>`_).
* Critical path updates will have autopush disabled if they receive negative karma
  (`b1f71006 <https://github.com/fedora-infra/bodhi/commit/b1f71006>`_).
* The e-mail templates reference dnf for Fedora and yum for Enterprise Linux
  (`1c1f2ab7 <https://github.com/fedora-infra/bodhi/commit/1c1f2ab7>`_).
* Updates are now obsoleted if they reach the unstable threshold while pending
  (`f033c74c <https://github.com/fedora-infra/bodhi/commit/f033c74c>`_).
* Bodhi now gates Updates based on whether they are signed yet or not
  (`#1011 <https://github.com/fedora-infra/bodhi/pull/1011>`_).


Bugs
^^^^

* Candidate builds and bugs are no longer duplicated while searching
  (`#897 <https://github.com/fedora-infra/bodhi/issues/897>`_).
* The Bugzilla connection is only initialized when needed
  (`950eee2c <https://github.com/fedora-infra/bodhi/commit/950eee2c>`_).
* A sorting issue was fixed on the metrics page so the data is presented correctly
  (`487acaaf <https://github.com/fedora-infra/bodhi/commit/487acaaf>`_).
* The Copyright date in the footer of the web interface is updated
  (`1447b6c7 <https://github.com/fedora-infra/bodhi/commit/1447b6c7>`_).
* Bodhi will comment with the required time instead of the elapsed time on updates
  (`#1017 <https://github.com/fedora-infra/bodhi/issues/1017>`_).
* Bodhi will only comment once to say that non-autopush updates have reached the threshold
  (`#1009 <https://github.com/fedora-infra/bodhi/issues/1009>`_).
* ``/masher/`` is now allowed in addition to ``/masher`` for GET requests
  (`cdb621ba <https://github.com/fedora-infra/bodhi/commit/cdb621ba>`_).


Dependencies
^^^^^^^^^^^^

Bodhi now depends on fedmsg-atomic-composer >= 2016.3, which addresses a few issues during mashing.


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

Bodhi 2.3.0 also has a few improvements to the development environment that make it easier to
contribute to Bodhi or improve Bodhi's automated tests:

* Documentation was added to describe how to connect development Bodhi to staging Koji
  (`7f3b5fa2 <https://github.com/fedora-infra/bodhi/commit/7f3b5fa2>`_).
* An unused ``locked_date_for_update()`` method was removed
  (`b87a6395 <https://github.com/fedora-infra/bodhi/commit/b87a6395>`_).
* The development.ini.example base_address was changed to localhost so requests would be allowed
  (`0fd5901d <https://github.com/fedora-infra/bodhi/commit/0fd5901d>`_).
* The ``setup.py`` file has more complete metadata, making it more suitable for submission to PyPI
  (`5c201ac2 <https://github.com/fedora-infra/bodhi/commit/5c201ac2>`_).
* The #bodhi and #fedora-apps channels are now documented in the readme file
  (`52093069 <https://github.com/fedora-infra/bodhi/commit/52093069>`_).
* A new test has been added to enforce PEP-8 style and a few modules have been converted to conform
  (`bbafc9e6 <https://github.com/fedora-infra/bodhi/commit/bbafc9e6>`_).


Release contributors
^^^^^^^^^^^^^^^^^^^^

The following contributors authored patches for 2.3.0:

* Josef Sukdol
* Julio Faracco
* Patrick Uiterwijk
* Randy Barlow
* Richard Fearn
* Trishna Guha


2.2.4
-----

This release fixes two issues:

* `#989 <https://github.com/fedora-infra/bodhi/issues/989>`_, where Karma on
  non-autopush updates would reset the request to None.
* `#994 <https://github.com/fedora-infra/bodhi/issues/994>`_, allowing Bodhi to
  be built on setuptools-28.


2.2.3
-----

This release fixes `#951 <https://github.com/fedora-infra/bodhi/issues/951>`_, which prevented
updates with large numbers of packages to be viewable in web browsers.


2.2.2
-----

This is another in a series of bug fix releases for Bodhi this week. In this release, we've fixed
the following issues:

* Disallow comment text to be set to the NULL value in the database
  (`#949 <https://github.com/fedora-infra/bodhi/issues/949>`_).
* Fix autopush on updates that predate the 2.2.0 release
  (`#950 <https://github.com/fedora-infra/bodhi/issues/950>`_).
* Don't wait on mashes when there aren't any
  (`68de510c <https://github.com/fedora-infra/bodhi/commit/68de510c>`_).


2.2.1
-----

Bodhi 2.2.1 is a bug fix release, primarily focusing on mashing issues:

* Register date locked during mashing (`#952
  <https://github.com/fedora-infra/bodhi/issues/952>`_).
* UTF-8 encode the updateinfo before writing it to disk (`#955
  <https://github.com/fedora-infra/bodhi/issues/955>`_).
* Improved logging during updateinfo generation (`#956
  <https://github.com/fedora-infra/bodhi/issues/956>`_).
* Removed some unused code
  (`07ff664f <https://github.com/fedora-infra/bodhi/commit/07ff664f>`_).
* Fix some incorrect imports
  (`9dd5bdbc <https://github.com/fedora-infra/bodhi/commit/9dd5bdbc>`_ and
  `b1cc12ad <https://github.com/fedora-infra/bodhi/commit/b1cc12ad>`_).
* Rely on self.skip_mash to detect when it is ok to skip a mash
  (`ad65362e <https://github.com/fedora-infra/bodhi/commit/ad65362e>`_).


2.2.0
-----

Bodhi 2.2.0 is a security and feature release, with a few bug fixes as well.


Security
^^^^^^^^

This update addresses `CVE-2016-1000008 <https://github.com/fedora-infra/bodhi/pull/857>`_ by
disallowing the re-use of solved captchas. Additionally, the captcha is
`warped <https://github.com/fedora-infra/bodhi/commit/f0122855>`_ to make it more difficult to
solve through automation. Thanks to Patrick Uiterwijk for discovering and reporting this issue.


Features
^^^^^^^^

* Bodhi's ``approve_testing.py`` script will now comment on updates when they have reached a stable
  karma threshold
  (`5b0d1c7c <https://github.com/fedora-infra/bodhi/commit/5b0d1c7c>`_).
* The web interface now displays a push to stable button when the karma reaches the right level when
  autokarma is disabled
  (`#772 <https://github.com/fedora-infra/bodhi/issues/772>`_ and
  `#796 <https://github.com/fedora-infra/bodhi/issues/796>`_).
* Masher messages now have an "agent", so it is possible to tell which user ran the mash
  (`45e4fc9f <https://github.com/fedora-infra/bodhi/commit/45e4fc9f>`_).
* Locked updates now list the time they were locked
  (`#831 <https://github.com/fedora-infra/bodhi/issues/831>`_).
* Bugs are closed and commented on in the same Bugzilla POST
  (`#404 <https://github.com/fedora-infra/bodhi/issues/404>`_).
* Karma values equal to 0 are no longer displayed with a green background to better distinguish them
  from positive karma reports (`#799 <https://github.com/fedora-infra/bodhi/issues/799>`_).
* Updates display a link to the feedback guidelines
  (`#865 <https://github.com/fedora-infra/bodhi/issues/865>`_).
* The new CLI now has a man page
  (`95574831 <https://github.com/fedora-infra/bodhi/commit/95574831>`_).
* The CLI now has a ``--version`` flag (`#895 <https://github.com/fedora-infra/bodhi/issues/895>`_).


Bugs
^^^^

* Locked updates that aren't part of a current push will now be pushed and warnings will be logged
  (`bf4bdeef <https://github.com/fedora-infra/bodhi/commit/bf4bdeef>`_). This should help us to fix
  `#838 <https://github.com/fedora-infra/bodhi/issues/838>`_.
* Don't show users an option to push to stable on obsoleted updates
  (`#848 <https://github.com/fedora-infra/bodhi/issues/848>`_).
* taskotron updates are shown per build, rather than per update
  (`ce2394c6 <https://github.com/fedora-infra/bodhi/commit/ce2394c6>`_,
  `8e199668 <https://github.com/fedora-infra/bodhi/commit/8e199668>`_).
* The Sphinx documentation now builds again
  (`b3f80b1b <https://github.com/fedora-infra/bodhi/commit/b3f80b1b>`_).
* Validator messages are now more useful and helpful
  (`#630 <https://github.com/fedora-infra/bodhi/issues/630>`_).
* The Bodhi CLI no longer depends on the server code to function
  (`#900 <https://github.com/fedora-infra/bodhi/issues/900>`_).
* Private bugs will no longer prevent the updates consumer from continuing
  (`#905 <https://github.com/fedora-infra/bodhi/issues/905>`_).
* bootstrap is now included in the setuptools manifest for the server package
  (`#919 <https://github.com/fedora-infra/bodhi/issues/919>`_).


Commit log
^^^^^^^^^^

The above lists are the highlights of what changed. For a full list of the changes since 2.1.8,
please see the
`changelog <https://github.com/fedora-infra/bodhi/compare/2.1.8...2.2.0>`_.
