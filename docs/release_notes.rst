Release notes
=============

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
