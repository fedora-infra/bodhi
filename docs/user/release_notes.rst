=============
Release notes
=============

.. towncrier release notes start

v8.1.1
======



Released on 2024-06-22.
This is a bugfix release, see below for the details.


Bug fixes
^^^^^^^^^

* Builds passed alongside a side-tag in update forms were not validated
  correctly against the side-tag (:pr:`5647`).
* build with spec false: build require python3dist(poetry-core) >= 1 but not in
  spec BuildRequires (:pr:`5678`).
* bodhi server web Incorrect static resource path for httpd, always "python3.7"
  python3_version in /etc/httpd/conf.d/bodhi.conf, fix in bodhi-server.spec
  (:pr:`5680`).
* Fixed the release list web page which was not updated after a release changed
  state (:pr:`5684`).
* Fixed bodhi-server enums initialization in Python 3.13 (:issue:`5685`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* niuwanli
* Mattia Verga


v8.1.0
======



Released on 2024-04-09.
This is a feature release that adds options for running createrepo_c.


Features
^^^^^^^^

* Bodhi can now set a timeout on postgresql database queries (default to 30
  sec) (:pr:`5593`).
* The createrepo_c config file now can accept enabling/disabling sqlite
  metadata generation and using --compatibility flag (:pr:`5617`).
* Builds submission can now be restricted to only specified sources
  (:issue:`5556`).
* A new `/list_releases/` GET endpoint is available to allow retrieving JSON
  data through ajax calls. (:issue:`5587`).

Bug fixes
^^^^^^^^^

* Use urljoin for update URLs construction (:issue:`5566`).
* DRPMs can now be disabled per Release in createrepo_c config file
  (:issue:`5616`).

Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* The Vagrant development environment is entirely removed in favor of BCD, and
  bodhi-shell is fixed in BCD. (:issue:`5600`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Aurélien Bompard
* Adam Williamson
* Mattia Verga


v8.0.2
======


Released on 2024-01-11.
This is a bugfix release.


Bug fixes
^^^^^^^^^

* Fixed Automated Tests table in the web UI not showing missing results or
  remote rule errors correctly (:pr:`5581`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Adam Williamson


v8.0.1
======


Released on 2023-12-24.
This is a bugfix release that fixes an urgent issue about bodhi-server not
honouring cookie authentication settings.


Bug fixes
^^^^^^^^^

* The Bodhi authentication policy wasn't honoring settings from config
  (:pr:`5572`).


Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Mattia Verga


v8.0.0
======



Released on 2023-12-09.
This is a major release that introduces several breaking changes. Please read
the details below and make sure to update any customized value in your config
file.


Backwards incompatible changes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* The 'required testcases' feature is removed, as it mostly just duplicated
  what we do with Greenwave, only worse. The SaveUpdate schema is modified
  (:pr:`5548`).
* The custom `skopeo-light` script has been dropped. Please adjust your config
  file to use the real skopeo command (:issue:`5505`).
* Build NVRs are added to the Bugzilla comment. Please adjust `initial_bug_msg`
  in Bodhi config during upgrade (:issue:`5513`).
* Settings for repodata and updateinfo can now be set by an external config
  file and no more hardcoded. Custom settings can be applied per Release, see
  the `devel/ci/integration/bodhi/createrepo_c.ini` file for reference
  (:issue:`5521`).

Dependency changes
^^^^^^^^^^^^^^^^^^

* libcomps >= 0.20 is required to correctly validate repodata created with
  createrepo_c >= 1.0. Bodhi can now support all compression method available
  in createrepo_c (:pr:`5455`).
* Authentication and Authorization have been ported to Pyramid 2.0 Security
  Policies and session serializer has been switched from PickleSerializer to
  JSONSerializer. Bodhi will now require Pyramid > 2.0. (:issue:`5091`).
* Bodhi now can run with sqlalchemy 2. At the same time the minimum required
  sqlalchemy version is raised to 1.4 (:issue:`5105`).

Server upgrade instructions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

This release contains database migrations. To apply them, run::

    $ sudo -u apache /usr/bin/alembic -c /etc/bodhi/alembic.ini upgrade head


Summary of the migrations:

* The Release model has gained a `released_on` column which reports the date of
  first release.
* The `requirements` column has been removed from both Package and Update
  models.
* The `email` column of the User model has been modified to UnicodeText.


Features
^^^^^^^^

* Support for storing critical path data in PDC is removed, as it is no longer
  needed (:pr:`5431`).
* Server: added a `get_critpath_components` json endpoint to list critical path
  components configured for a Release (:pr:`5484`).
* The release timeline graph now uses logarithmic scale for better display
  (:pr:`5492`).
* The webUI now allows unpushing Rawhide updates which fail gating tests
  (:pr:`5542`).
* Releases can now inherit buildroot override tags from other releases by
  settings in Bodhi config file (:issue:`4737`).
* Update notes are now converted to plaintext when printed in email or messages
  (:issue:`5049`).
* Members of QA groups defined in configuration are now able to waive or
  trigger tests for any update, despite they're packagers/provenpackagers or
  not (:issue:`5448`).
* Make the update.comment message schema more informative (:issue:`5469`).
* Release data now give information about the status of `pre_beta` and
  `post_beta` and of the first date of release (:issue:`5481`).
* Builds associated to unpushed updates can now be moved to other existing
  updates (:issue:`5485`).
* JSON APIs now support quering Releases by multiple states, for example
  `?state=pending&state=frozen` (:issue:`5518`).
* The UpdateReadyForTesting message format is simplified, and the message is
  now published on update creation and edit with changed builds instead of push
  to testing (:issue:`5538`).

Bug fixes
^^^^^^^^^

* Exclude locked updates being composed from being modified by cron tasks
  (:pr:`5524`).
* WebUI will not show the "push to testing" option meanwhile the update is
  waiting for builds to be signed (:pr:`5550`).
* Updates ejected from the composes would remain stuck in pending state due to
  wrong tags applied to thei builds (:issue:`5396`).
* Usernames containing a `-` are now correctly matched when mentioning
  (:issue:`5453`).
* Sidetags in the dropdown of the new update form are now sorted alphabetically
  (:issue:`5470`).
* Fixed "cannot access local variable 'tags'" error when editing flatpak
  updates (:issue:`5503`).
* The new update page now displays a meaningful page title (:issue:`5540`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Aurélien Bompard
* Adam Williamson
* Jonathan Lebon
* Lenka Segura
* Mattia Verga
* Owen W. Taylor
* Ryan Lerch


v7.2.2
======



Released on 2023-10-03.
This is a bugfix release.


Bug fixes
^^^^^^^^^

* Fixed the detection of Flatpak update type (:pr:`5496`).
* Fix handling container tags which aren't valid OCI tags (:pr:`5497`).
* Fixed display of waived failures in the Automated Tests tab (:issue:`5397`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Owen Taylor
* Adam Williamson
* Mattia Verga


v7.2.1
======



Released on 2023-07-30.
This is a bugfix release.


Features
^^^^^^^^

* If an update has got any failing test, an help box is displayed in the
  Automated Tests tab (:pr:`5382`).

Bug fixes
^^^^^^^^^

* On the Automated Tests tab, passed tests that are 'required' now correctly
  show as such (:pr:`5388`).
* client: do not rely on `HOME` being defined in os.environ variables
  (:pr:`5398`).
* server: when resubmitting a pending update to testing, make sure the release
  candidate tag is applied to all builds (:pr:`5400`).
* Fixed wrong update attribution in ready for testing message string
  (:issue:`5415`).
* Fixed missing whitespace in "bodhi update completed push to testing"
  (:issue:`5416`).
* Update testing instruction command is now clearer as it now warns users that
  it may take up to 24 hours for an update to propagate to mirrors
  (:issue:`5428`).

Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* Added support for dnf5 to repository sanity check tests (:issue:`5404`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Aurélien Bompard
* Adam Williamson
* Mattia Verga


v7.2.0
======



Released on 2023-04-30.
This is a bugfix release.


Features
^^^^^^^^

* Bodhi will not try to recalculate the gating status in response to a new
  result or a new waiver if the status is `ignored` (:pr:`5202`).
* `update.edit` messages now include `new_builds` and `removed_builds`
  properties (:pr:`5237`).
* The Releases list webpage now hide inactive (disabled or archived) releases
  by default (:pr:`5264`).

Bug fixes
^^^^^^^^^

* Icons for tests in QUEUED and RUNNING states were not displayed in the webUI
  (:pr:`5187`).
* Updated links to Bodhi extended markdown description page (:pr:`5190`).
* The title in the update webpage now has no more a hyperlink (:issue:`5089`).
* The bundled selectize js component was downgraded to 0.14.0 to solve a bug
  where the bug list was emptied upon editing an update (:issue:`5233`).
* Link to Koji builds are now correctly encoded (:issue:`5272`).

Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* Use functools lru_cache for caching `Release.all_releases()` and
  `Release.get_tags()` instead of a custom implementation (:pr:`5238`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Aurélien Bompard
* Adam Williamson
* Kevin Fenzi
* Mattia Verga
* Mikolaj Izdebski
* Michal Konečný


v7.1.1
======

Released on 2023-03-18.
This is a minor feature release.


Features
^^^^^^^^

* The automated tests tab will now display information about `queued` and
  `running` tests (:pr:`5139`).
* Copy additional config files for pungi (:pr:`5154`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Adam Williamson
* Michal Konečný


v7.1.0
======

Released on 2023-03-11.
This is a feature release.


Dependency changes
^^^^^^^^^^^^^^^^^^

* Bodhi now uses pymediawiki instead of the unmaintained simplemediawiki to
  fetch test cases (:pr:`4852`).

Features
^^^^^^^^

* bodhi-messages is updated to include additional properties in the message
  schemas. The additional properties are: app_name, agent_name, and __str__
  (:issue:`4950`).

Bug fixes
^^^^^^^^^

* Retrieving sidetags list for a user not known to Koji caused an exception in
  bodhi-server (:pr:`4994`).
* Added support for bleach >= 6.0.0 (:pr:`5003`).
* bodhi-client: do not run `koji wait-repo` when expiring a buildroot override
  (:issue:`4830`).
* bodhi-client: fix `--version` option (:issue:`4981`).
* Update notes are now capped to a default of 10k characters, the value can be
  customized in config (:issue:`4982`).
* Fixed webUI template where karma and comment icons where misaligned at highly
  commented discussions (:issue:`4986`).
* Fixed the template of the update details page, where the testcases tab was
  always empty (:issue:`5000`).
* The link to the test gating tab in the update page was fixed (:issue:`5032`).
* The composer is now safer about not triggering stable composes for frozen
  releases (:issue:`5080`).
* Rawhide updates which are obsoleted before being pushed will now not be
  pushed to stable to avoid confusion (:issue:`5113`).
* Frozen releases didn't show up in filters (:issue:`5115`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Kevin Fenzi
* Mattia Verga
* Ryan Lerch


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
