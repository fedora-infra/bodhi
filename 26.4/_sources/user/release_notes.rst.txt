=============
Release notes
=============

.. towncrier release notes start

v26.4.0
=======


Released on 2026-03-25.
This is a feature release that adds support for uploading flatpaks to multiple
registries.


Backwards incompatible changes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Support multiple destination registries for containers:
  `container.destination_registry` config value can now be specified as list
  (:pr:`6077`).

Features
^^^^^^^^

* server: opengraph tags have been added to web pages (:pr:`6050`).
* Bodhi query API now allows to query updates by Koji side tag name
  (:pr:`6078`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Akashdeep Dhar
* Adam Williamson
* FeRD (Frank Dana)
* Mattia Verga
* Michal Konecny
* Nikola Forró
* WillyEverGreen


v25.11.3
========


Released on 2026-01-18.
This is a bugfix release which also brings some minor feature enhancements.


Features
^^^^^^^^

* client: when downloading packages use the `--fallback-unsigned` option to tell
  Koji to fall back to getting unsigned packages if it can't get signed ones
  (:pr:`6039`).
* server: allow retrieving a (Fedora) release by searching for `rawhide`
  (:pr:`6061`).
* server: added an X-Bodhi-Agent header to emails sent on update comments
  (:pr:`6065`).
* server: don't send a comment email notification to the comment author
  (:pr:`6066`).

Bug fixes
^^^^^^^^^

* server: avoid manually setting `TestGatingStatus.waiting` on Update before
  calling `update_test_gating_status()` (:pr:`6044`).
* server: builds with too long NVR (>100 chars) are now ignored by the
  automatic updates consumer (:pr:`6063`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Adam Williamson
* Mattia Verga


v25.11.2
========


Released on 2025-11-23.
This is a bugfix release.


Bug fixes
^^^^^^^^^

* When expiring an override don't require candidate or testing build tags
  (:issue:`5937`).
* bodhi-server: refine logic to avoid stuck side-tag updates for releases not
  composed by bodhi (:issue:`5989`).
* bodhi-server: skip updating the gating status if the current status is
  'waiting', and the message we're handling is for a QUEUED or RUNNING result
  (:issue:`6000`).
* bodhi-server: gating status should be correctly updated to 'waiting' when all
  failed tests on an update are restarted. (:issue:`6001`).

Other changes
^^^^^^^^^^^^^

* server: usage of `os.scandir()` instead of `os.listdir()` in
  clean_old_composes task should give better performance (:pr:`5999`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Adam Williamson
* Mattia Verga


v25.11.1
========


Released on 2025-11-01.
This release fixes a few bugs regarding the display of automated test results
in web pages.


Dependency changes
^^^^^^^^^^^^^^^^^^

* bodhi-server: dependency on waitress now requires a version greater than
  3.0.1 (:pr:`5897`).
* bodhi-server: support for configuring logging through pyramid_sawing has been
  removed (:pr:`5906`).

Features
^^^^^^^^

* User statistics in homepage will now default to show 10 entries. This number
  can be configured in Bodhi's config file. (:pr:`5882`).

Bug fixes
^^^^^^^^^

* client: aliases for Fedora Flatpak updates are now recognized from command
  line (:pr:`5918`).
* Fixed a schema issue which prevented to set the `released_on` property on
  Release (:issue:`5964`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Akashdeep Dhar
* Adam Williamson
* Jens Petersen
* Mattia Verga
* Yaakov Selkowitz

v25.5.1
=======


Released on 2025-05-17.
This adds a couple of features that were not included in the previous release
by mistake.


Features
^^^^^^^^

* The CLI updates download command will now download signed packages, if
  possible. (:pr:`5859`).

Bug fixes
^^^^^^^^^

* `UpdateType.unspecified` that was introduced with PR#3047 has been added to
  the documentation and `constants.UPDATE_TYPES` list. (:pr:`5892`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Adam Williamson
* LuK1337

v25.5
=====


Released on 2025-05-16.
This is mostly a bugfix release, see the following notes for a detailed
description.


Features
^^^^^^^^

* bodhi-server: Updates which fail gating tests are now marked by an icon in
  the update list view (:pr:`5852`).

Bug fixes
^^^^^^^^^

* When creating a new Update, do not add relationships before the Update object
  is in session. Fixes some SQLAlchemy 2.x warnings. (:pr:`5840`).
* The task responsible for unstuck updates ejected from the push has been fixed
  for correct handling side-tag updates (:pr:`5850`).
* The Automated Tests tab now correctly indicates when a required test failure
  was waived if the test case has no 'scenario'. (:pr:`5863`).
* Where available, libdnf5 Python bindings are now used in repository sanity
  checks, otherwise we're forcing dnf-4 usage with the old method
  (:issue:`5820`).
* Builds for rawhide or branched updates are now moved from pending-testing to
  testing tag when the update is moved into testing. Despite being pointless,
  this ensure to not break update flow when a release enters Bodhi activation
  point (:issue:`5830`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Akashdeep Dhar
* Aurélien Bompard
* Adam Williamson
* Peter Oliver
* Mattia Verga

v8.3.0
======



Released on 2024-11-25.
This is a feature release that re-adds the distinction between `min_karma`
and `critpath.min_karma` settings.


Features
^^^^^^^^

* Bodhi now allows setting the min_karma threshold for critical path and
  non-critical path updates separately (:pr:`5802`).
* bcd has a new clean subcommand to completely refresh the bcd environment
  (:pr:`5804`).
* WebUI: the update page now reports both the autopush settings and the minimum
  threshold for the manual push (:pr:`5805`).
* The Release properties `min_karma`, `critpath_min_karma`,
  `mandatory_days_in_testing` and `critpath_mandatory_days_in_testing` are now
  expossed in JSON replies from bodhi-server and can be viewed in bodhi-client
  through the `release requirements` command (:pr:`5807`).

Bug fixes
^^^^^^^^^

* Bodhi documentation on RTD was missing some content generated by external
  scripts (:pr:`5789`).
* When editing an update from APIs it is no more required to specify the old
  bug ids list in sent data if no change is required (:issue:`5800`).

Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* A deprecation warning is now emitted when a value for `karma_critpath` is set
  in a comment (:pr:`5796`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Adam Williamson
* Mattia Verga

v8.2.0
======



Released on 2024-10-26.
This is a feature release that needs configuration file adjustments. See the
following notes for the details.


Backwards incompatible changes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Bodhi's update status checking has been overhauled, and some configuration
  options have changed.

  * `critpath.num_admin_approvals` is removed. This backed the old Fedora "proven
    testers" concept, which has not been used for some years.
  * `critpath.min_karma` is removed and is replaced by a new setting just called
    `min_karma`. This applies to all updates, not just critical path.
  * `critpath.stable_after_days_without_negative_karma` is renamed to
    `critpath.mandatory_days_in_testing` and its behavior has changed: there is no
    longer any check for 'no negative karma'. Critical path updates, like
    non-critical path updates, can now be manually pushed stable after reaching
    this time threshold even if they have negative karma.

  As before, these settings can be specified with prefixes to apply only to
  particular releases and milestones. `min_karma` and
  `(critpath.)mandatory_days_in_testing` now act strictly and consistently as
  minimum requirements for stable push. Any update may be pushed stable once it
  reaches either of those thresholds (and passes gating requirements, if gating
  is enabled). The update's `stable_karma` value is no longer ever considered in
  determining whether it may be pushed stable. `stable_karma` and `stable_days` are
  only used as triggers for automatic stable pushes (but for an update to be
  automatically pushed it must *also* reach either `min_karma` or
  `(critpath.)mandatory_days_in_testing`).

  The most obvious practical result of this change for Fedora is that, during
  phases where the policy minimum karma requirement is +2, you will no longer
  be able to make non-critical path updates pushable with +1 karma by setting
  this as their `stable_karma` value. Additionally:

  * It is no longer possible to set an update's request to 'stable' if it has
    previously met requirements but currently does not
  * Two cases where updates that reached their unstable_karma thresholds were
    not obsoleted are resolved
  * Updates in 'pending' as well as 'testing' status have autopush disabled
    upon receiving any negative karma
  * The `date_approved` property of updates is more consistently set as the
    date the update first became eligible for stable push (:pr:`5630`).

Features
^^^^^^^^

* When searching updates, you can now specify multiple gating statuses by
  passing the 'gating' query arg more than once (:pr:`5658`).
* Bundled fedora-bootstrap has been updated to 5.3.3-0 (:pr:`5711`).
* A packager can now edit a side-tag update even if the side-tag is not owned
  by them, provided they have commit rights on all packages included in the
  side-tag (:pr:`5764`).

Bug fixes
^^^^^^^^^

* The development.ini.example config - on which the BCD config is based - is
  now set up to listen on both IPv4 and IPv6 (:pr:`5659`).
* Openid based login support has been removed from Bodhi. `python-openid` and
  `pyramid-fas-openid` are EOL and we moved to OIDC authentication.
  (:issue:`5601`).
* Fixed a build validation issue which would prevent a sidetag update from
  being submitted in some circumstances (:issue:`5725`).
* Fixed broken pagination for listing updates in webUI and JSON
  (:issue:`5738`).

Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* Calls to `datetime.datetime.utcnow()` have been changed to
  `datetime.datetime.now(datetime.timezone.utc)`. We previously assumed all
  datetimes were UTC based, now this is explicit by using timezone aware
  datetimes (:pr:`5702`).

Documentation improvements
^^^^^^^^^^^^^^^^^^^^^^^^^^

* Bodhi's documentation is now served from ReadTheDocs pages (:pr:`5774`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Adam Williamson
* Mattia Verga
* Nikola Forró
* Ryan Lerch


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


Older releases
==============

Below are the historic release notes of older versions:

.. toctree::
   :maxdepth: 1

   7.x_release_notes.rst
   6.x_release_notes.rst
   5.x_release_notes.rst
   4.x_release_notes.rst
   3.x_release_notes.rst
   2.x_release_notes.rst
