=============
Release notes
=============

.. towncrier release notes start

v7.0.1
======

Released on 2023-01-14.
This is a bugfix release.


Bug fixes
^^^^^^^^^

* Fixed template in overrides list page which prevents the display of filters
  dropdown (:pr:`4844`).
* Fixed a possible XSS attack vector in update_form.js (:pr:`4845`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Mattia Verga


v7.0.0
======

Released on 2022-11-26.
This is a major release that fully enables `frozen` release state in bodhi-server
and adds Kerberos authentication to bodhi-client.


Server upgrade instructions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

This release contains database migrations. To apply them, run::

    $ sudo -u apache /usr/bin/alembic -c /etc/bodhi/alembic.ini upgrade head


Features
^^^^^^^^

* Bodhi client now autenticates using Kerberos by default and falls back to
  browser-based OIDC mechanism. (:pr:`4602`).
* Critical path information can now be read from JSON files (in the form output
  by the releng `critpath.py` script), using config options `critpath.type =
  json` and `critpath.jsonpath` (:pr:`4755`).
* Frozen releases updates will now be forced into testing before being pushed
  to stable (:pr:`4831`).
* The new update form UI will now display a warning when a release is
  approaching EOL (:pr:`4834`).
* Bodhi-push now defaults to push only testing composes for frozen releases
  (:issue:`4478`).

Bug fixes
^^^^^^^^^

* Editing a stuck Rawhide side-tag update (usually when gating tests fail) will
  no more cause builds to be tagged with the release candidate-tag to prevent
  the automatic update consumer from creating an automatic update and breaking
  the side-tag update (:pr:`4745`).
* Bodhi client will not show the secret in terminal when logging in via browser
  (:pr:`4814`).
* The check_signed_builds sometimes failed to unstuck updates due to the use of
  a wrong tag (:pr:`4819`).
* Updateinfo.xml metadata generation has been changed in order to try to fix
  errors reported by yum on EPEL (:issue:`2487`).
* Releases in frozen state will now be listed in the release page and a warning
  box will be showed for updates of those releases (:issue:`4103`).
* The `date_approved` property of the `Update` model is now set when the update
  is ready to be pushed to stable (:issue:`4171`).
* Scenario is now included in request data when waiving test results
  (:issue:`4270`).
* The update page now shows a single combined gating status, instead of listing
  the result of each separate greenwave query (:issue:`4320`).
* Bodhi-client now raises a generic `SysExit` exception instead of
  `click.exceptions.Abort` when a user aborts authentication, so external
  scripts can avoid importing Click in their code (:issue:`4623`).

Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* Bodhi client now supports configuring OIDC storage path. (:pr:`4603`).
* For gating, Bodhi now queries all Greenwave 'decision contexts' together,
  reducing the number of queries needed. (:pr:`4821`).
* References to never used `side_tag_active` and `side_tag_expired` update
  statuses and the `Update.side_tag_locked` property have been removed
  (:pr:`4823`).
* The `date_pushed` database column of the `Update` model has been dropped and
  replaced by a property, no change should be noticeable to users
  (:issue:`4837`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Aurélien Bompard
* Adam Williamson
* Maxwell G
* Mattia Verga
* Matej Focko
* Tomas Tomecek


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
