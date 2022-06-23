=============
Release notes
=============

.. towncrier release notes start

v6.0.1
======

Released on 2022-06-23. This is a bugfix release.


Dependency changes
^^^^^^^^^^^^^^^^^^

* Remove the dependency on WhiteNoise since the documentation has moved to
  Github (:pr:`4555`).
* Updated bundled chartJS component to 3.8.0 (:pr:`4561`).

Features
^^^^^^^^

* Allow disabling autokarma, autotime and close-bugs when editing an update by
  CLI (:pr:`4564`).

Bug fixes
^^^^^^^^^

* Fix a small template issue about the karma thumbs display (:pr:`4562`).
* Autokarma, autotime and close-bugs automatisms may have been accidentally
  overridden when editing updates by CLI (:issue:`4563`).
* In very peculiar circumstances, side-tag Rawhide updates may remain stuck if
  a user posts a negative karma or tries to set a request before Bodhi
  automatically pushes the update to stable (:issue:`4566`).
* Don't crash when Ipsilon has no userinfo (:issue:`4569`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Aurélien Bompard
* Mattia Verga


v6.0.0
======

This is a major release that adds authentication with OpenID Connect.


Backwards incompatible changes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Support authentication with OpenID Connect, in addition to OpenID.
  The old OpenID authentication can be accessed by using
  ``/login?method=openid`` as the login URL.
  The bodhi client is switched to OIDC entirely, plain OpenID support has been
  dropped.
  Depending on the OIDC provider's capabilities, users may have to run the
  bodhi client on a host that has a browser. This will not be the case in Fedora
  as OOB support has been recently added to Ipsilon.
  (:issue:`1180`).

Dependency changes
^^^^^^^^^^^^^^^^^^

* Dependencies are now managed by Poetry (:pr:`4376`).
* Enable Dependabot (:pr:`4454`).

Features
^^^^^^^^

* Add 'update' property to ``koji-build-group.build.complete`` messages
  (:pr:`4381`).
* Extend ``save_override()`` to set the expiration date of an override
  directly. (:pr:`4431`).

Bug fixes
^^^^^^^^^

* Handle invalid characters in RSS export (:pr:`4513`).
* Fixed a style issue in the web UI where images posted in comments exceed box
  width (:issue:`4327`).
* Fix the copyright year in the footer going stale by programatially setting
  the year. (:issue:`4401`).
* Bodhi will now obsolete updates being pushed to stable when a newer build is
  pushed to stable (:issue:`4446`).
* Exclude the `composes` property when serializing the Release object to avoid
  recursion (:issue:`4447`).
* Adding or removing builds from a side-tag update by CLI causes the `from_tag`
  property to be removed (:issue:`4452`).
* Updates comments with negative karma are now highlighted in red in the webUI
  (:issue:`4500`).
* The "karma thumb" now will show any mixed combination of positive/negative
  votes, rather than the overall count (:issue:`4501`).
* Fixed a tagging problem when updating the builds list in a side-tag update
  (:issue:`4551`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Adam Saleh
* Aurélien Bompard
* Adam Williamson
* Lenka Segura
* Mattia Verga
* Miro Hrončok
* Ryan Lerch
* Tomáš Hrčka


Older releases
==============

Below are the historic release notes of older versions:

.. toctree::
   :maxdepth: 1

   5.x_release_notes.rst
   4.x_release_notes.rst
   3.x_release_notes.rst
   2.x_release_notes.rst
