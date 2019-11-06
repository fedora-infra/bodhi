=============
Release notes
=============

.. towncrier release notes start


v5.0.0
======

This is a major release with many backwards incompatible changes.


Backwards incompatible changes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Celery is introduced to handle the long-running tasks (:issue:`2851`).
* Fedmenu was removed from the UI (:issue:`2194`).
* Remove deprecated ``search_packages`` path (:pr:`3411`).
* Remove ``critpath_karma`` from the UI (:issue:`2194`).
* Remove unused and incorrect ``server.bugs.Bugzilla.get_url()`` function.
* Print errors to stderr in command line tools.


Dependency changes
^^^^^^^^^^^^^^^^^^

* Celery is a new required dependency (:issue:`2851`).


Server upgrade instructions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

This release contains database migrations. To apply them, run::

    $ sudo -u apache /usr/bin/alembic -c /etc/bodhi/alembic.ini upgrade head


Features
^^^^^^^^

* Update fedora-bootstrap to latest 1.5.0.
* Add ctype to the ComposeComplete (:issue:`3297`).
* Add knowledge of branch freezes to the Release model (:issue:`1038`, :issue:`1563`).
* API: Create/edit updates from Koji tags (:issue:`3009`).
* Add javascript confirmation for unpushing updates.
* Use versioned dir name for static files.
* Improve the performance of validate_build_uniqueness.
* Add option to create/edit updates side tags to CLI (:issue:`2325`).
* Overhaul the new update form.
* Mark updates not composed by bodhi as pushed when stable.
* Allow multiple status params for update list views (:issue:`3429`).
* Send a message when an update is ready to be tested (:issue:`3428`).
* Create additional side tags on multi build tag (:issue:`3473`).
* Create comment when CI tests starts, but don't send an email (:issue:`3403`).
* Add support for creating sidetag updates to webui.
* Create a Dashboard for logged in users.
* Clean up Javascript, CSS and fonts.
* Add a new config item, ``automatic_updates_blacklist``, which is a list of
  users to not process auto updates from.
* Document what the update states mean for rawhide.
* Add a filtering/searching interface to the updates query view.
* Add the list of packages in the update description to rss feed.
* Transform markdown code to html for better readability of the rss feed.
* Add frozen release state to bodhi releases list.
* Add API call to retrigger update tests.
* Tidy up the UI.
* Add --user and --password to all actions of the bodhi CLI supporting
  --openid-api (for example: waive and trigger) (:pr:`3550`).
* Update ChartJS package and redesign Release page (:pr:`3671`).
* Automatically created updates (e.g. Fedora Rawhide single package updates)
  now include a changelog entry in the update notes. (:issue:`3192`).
* Move multi build update that failed to merge in rawhide to pending.
  (:issue:`3514`).


Bug fixes
^^^^^^^^^

* Handle connection problems when talking to Wiki (:issue:`3361`).
* Make Bodhi able to clear models.Release._all_releases cache (:issue:`2177`).
* Query Greenwave in batches to avoid timeouts.
* Template, js and style fixes.
* Allow to configure a release without an override tag (:issue:`3447`).
* Determine a release for sidetag updates (:issue:`3480`).
* Change update status to testing if every build is signed (:issue:`3475`).
* Delete additional tags once an side tag update was pushed to stable (:issue:`3476`).
* Turn off autokarma and autotime for automatic updates (:issue:`3424`).
* Make ``display_name`` optional in template (:issue:`3470`).
* Sign new builds to ``<sidetag>-pending-signing`` (:issue:`3485`).
* Allow only 1 update per side tag (:issue:`3484`).
* Disable comments on updates when update is pushed and stable (:issue:`2050`).
* Unify rawhide simple build update with multi build update (:issue:`3513`).
* Prevent crash when compose contains update without builds (:issue:`3471`).
* Added build.update.pushed = True for the signed consumer so that it can be
  unpushed. (:issue:`3625`).


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* Rename bteststyle to blint.
* Update developer documentation.
* Run mypy directly in Vagrant (:issue:`3335`).
* More type annotations.
* Add WaiverDB and Greenwave to development environment (:issue:`3011`).
* Provide authentication in the integration testing environment.
* Make it easier to develop using VS Code.
* Add option to vagrant provisioning to use stg infra.
* Introduction of `Towncrier <https://github.com/hawkowl/towncrier/>`_ to
  manage the release notes (:issue:`3562`).


Other changes
^^^^^^^^^^^^^

* List items in RSS feed starting from the most recent (:pr:`3621`).


Contributors
^^^^^^^^^^^^

The following developers contributed to Bodhi 5.0.0:

* Anatoli Babenia
* Aurélien Bompard
* Randy Barlow
* Clement Verna
* David Fan
* dimitraz
* Lukas Holecek
* Mattia Verga
* Michal Konečný
* Nils Philippsen
* Ondrej Nosek
* Pierre-Yves Chibon
* Rick Elrod
* Ryan Lerch
* Robert Scheck
* Rob Shelly
* Sam Robbins
* Stephen Coady
* siddharthvipul
* subhamkrai
* Sebastian Wojciechowski


v4.1.0
======

This is a feature release that adds single-package gating.

Server upgrade instructions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

This release contains database migrations. To apply them, run::

    $ sudo -u apache /usr/bin/alembic -c /etc/bodhi/alembic.ini upgrade head


Features
^^^^^^^^

* Add autopush and stable_days to an update.  When ``autopush`` is true, the
  approve_testing cronjob will push the update to stable if it has meet the
  testing requirements (``stable_days``).  ``stable_days`` cannot be smaller
  than the release ``mandatory_days_in_testing`` (:issue:`2978`).
* Add a login reminder for posting feedback.
* Add ``package_manager`` enum and ``testing_repository`` string to Release
  model.  No default is provided, so if one wants Bodhi to display the install
  command for an update, they need to manually edit the existing releases after
  the database migration.
* Add a Greenwave message consumer to update the ``test_gating_status`` value.
* Add the flatpak releases to the greenwave config.
* Automatically create Rawhide updates in ``testing`` state.


Bug fixes
^^^^^^^^^

* Log permanent failures for debugging.  Previously, exceptions were raised
  which caused the affected messages to be placed back into the queue
  (:issue:`3306`).
* Fix downloading packages for updates with multiple builds.
* Verify the correct number of received items in the client.
* Do not ask for original_spec_nvr results from greenwave.  This will have for
  effect to improve the performance of bodhi's requests to greenwave.
* Bodhi will now retry for up to 10 minutes if it receives ``koji.AuthError``
  (:issue:`1201`).
* Don't raise Exception on non-existing composes (:issue:`3318`).
* Correct grammar on a comment that Bodhi writes.
* Log unsuccessful attempt to set request as INFO (:issue:`3293`).
* Use update.alias instead of update.title in updates rss link.
* Make sure ``%{uid}`` in krb ccache gets replaced with the effective UID.
* Create composes based on update's alias in bodhi-push (:issue:`3160`).
* User should be able to set ``Update.display_name`` (:issue:`1369`).
* Make ``meets_testing_requirements()`` comply with policy
  (:issue:`1307`, :issue:`1508`, :issue:`1796`, :issue:`3282`).
* Order builds by nvr in all places so the ordering is always consistent.


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* Leave the global log level in peace when testing.
* Update the Developer documentation
* Disable ``warm_cache_on_start`` in unittest (:issue:`3311`).
* Use flake8-import-order to enforce PEP-8 imports.


Contributors
^^^^^^^^^^^^

The following developers contributed to Bodhi 4.1.0:

* Aurélien Bompard
* Clement Verna
* Mattia Verga
* Michal Konečný
* Nils Philippsen
* Patrick Uiterwijk
* Pierre-Yves Chibon
* Randy Barlow
* Sebastian Wojciechowski
* Troy Dawson


v4.0.2
======

This is a bugfix release.


Bug fixes
^^^^^^^^^

* Drop updateinfo <id> tag detection (:issue:`3269`).


Contributors
^^^^^^^^^^^^

The following developers contributed to Bodhi 4.0.2:

* Patrick Uiterwijk


v4.0.1
======

This is a bugfix release.


Bug fixes
^^^^^^^^^

* Fix zchunk updateinfo getting injected as updateinfo_zck (:issue:`3261`).
* Fix a broken template in ``bodhi-push`` (:issue:`3256`).


Contributors
^^^^^^^^^^^^

The following developers contributed to Bodhi 4.0.1:

* Randy Barlow
* Patrick Uiterwijk


v4.0.0
======

This is a major release with many backwards incompatible changes.


Backwards incompatible changes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Values NULL and 0 are not allowed in update's stable_karma and unstable_karma (:issue:`1029`).
* Updates no longer have a ``title`` attribute. This affects many elements of Bodhi's REST API,
  including URLs (update titles can no longer be used to reference updates, only aliases), REST API
  data structures, and Bodhi's messages (:issue:`186`, :issue:`1542`, :issue:`1714`, and
  :issue:`1946`).
* The ``prefer_ssl`` setting has been renamed to ``libravatar_prefer_tls`` and now defaults to
  ``True`` instead of ``None`` (:issue:`1921`).
* Integration with pkgdb is no longer supported (:issue:`1970`).
* The ``/admin/`` API has been removed (:issue:`1985`).
* The relationship between Packages and Users was dropped. As a result, the ``packages``
  parameter in users query API has also been removed (:issue:`1997`).
* Support for CVE tracking was dropped. It was technically not possible to use the feature, so it
  is unlikely to affect any deployments (:issue:`1998`).
* The ``processing`` update status has been removed (:issue:`1999`).
* The ``/masher`` API has been removed (:issue:`2024`).
* Default sqlalchemy.url setting points to PostgreSQL instead of SQLite (:issue:`2040`).
* The ``Masher`` was renamed to ``Composer``. As a result, the ``bodhi-clean-old-mashes`` script
  was renamed to ``bodhi-clean-old-composes``, notification topics ``mashtask.start``,
  ``mashtask.mashing``, ``mashtask.complete``, ``mashtask.sync.wait`` and ``mashtask.sync.done``
  was renamed to ``compose.start``, ``compose.composing``, ``compose.complete``, ``compose.sync.wait``
  and ``compose.sync.done``, configuration settings ``mash_dir``, ``mash_stage_dir`` and
  ``max_concurrent_mashes`` was renamed to ``compose_dir``, ``compose_stage_dir`` and
  ``max_concurrent_composes`` (:issue:`2151`).
* The ``bodhi-monitor-composes`` script has been removed (:issue:`2171`).
* The stacks feature has been removed (:issue:`2241`).
* The ``bodhi-manage-releases`` script has been removed (:issue:`2420`).
* Support for anonymous comments was dropped. As a result, the ``anonymous`` field on the Comment
  object was removed and comments query API parameter ``anonymous`` was dropped. All ``captcha.*``
  settings were removed (:issue:`2700`).
* Bodhi client and server no longer support Python 2. Python 3.6+ are the only supported Python
  releases (:issue:`2759`).
* Support for the ``ci_url`` on the ``Build`` object was dropped (:issue:`2782`).
* Support for ``active_releases`` parameter in updates query API was dropped (:issue:`2815`).
* Support for fedmsg has been dropped (:issue:`2838`).
* The ``/updates/ALIAS/TITLE`` API has been removed (:issue:`2869`).
* Support for update's old_updateid was dropped (:issue:`2903`).
* The UI no longer has fedmsg integrations to show events happening elsewhere in Bodhi
  (:issue:`2913`).
* Support for update's greenwave_unsatisfied_requirements was dropped (:issue:`2958`).
* The batching feature was dropped, and thus updates can no longer be in the batched request state.
  As a result, the bodhi-dequeue-stable CLI has also been removed (:issue:`2977`).
* Support for obsolete scripts in ``tools`` folder was dropped (:issue:`2980`).
* Support for update's greenwave_summary_string has been dropped (:issue:`1339` and :issue:`2988`).
* Bug objects no longer include a ``private`` field (:issue:`3016`).
* The CLI now defaults to the ``--wait`` flag when creating or editing buildroot overrides. The old
  behavior can be achieved with the ``--no-wait`` flag (:issue:`3006`).
* All messages and API responses that serialize updates no longer have a ``submitter`` field. This
  was redundant with the included ``user.name`` field, and was only in place for compatibility with
  Bodhi 1 which was EOL many years ago (:issue:`3144`).
* All of Bodhi's fedmsgs have been changed. A new bodhi.messages packages has been added with new
  published message schemas. Note that only the fields listed in the documented schemas are
  supported in Bodhi 4, even though Bodhi still sends messages similar to the messages it sent in
  the past. Message consumers should not rely on any undocumented fields in these messages. If you
  need information that is not included in the supported schema, please work with the Bodhi project
  to get the schema adjusted accordingly. Bodhi's messages are now documented in
  :doc:`../server_api/index`.
* The ``fedmsg_enabled`` setting was removed, since fedmsg is not used anymore.


Dependency changes
^^^^^^^^^^^^^^^^^^

* pkgdb is no longer required (:issue:`1970`).
* cryptography is no longer required (:issue:`2700`).
* Fonts are no longer required for the captcha (Bodhi previously defaulted to using
  liberation-mono-fonts, but this wasn't a strict requirement since the font was configurable)
  (:issue:`2700`).
* pillow is no longer required (:issue:`2700`).
* six is no longer required for the client or server (:issue:`2759`).
* ``bodhi-server`` now depends on ``bodhi-messages``.
* kitchen is no longer required (:issue:`3094`).
* hawkey is no longer required.
* PyYAML is now a required dependency (:issue:`3174`).
* Bodhi now requires Python 3.6 or greater (:issue:`2856`).
* Bodhi no longer uses or works with ``fedmsg``.
* Backoff is now a required dependency (:issue:`3237`).


Server upgrade instructions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Bodhi server must be upgraded from Bodhi 3.13.0 or newer to 4.0.0 (i.e., it is not supported to
upgrade a server older than 3.13.0 directly to 4.0.0 as 4.0.0 has trimmed database migrations from
the older releases.

This release contains database migrations. To apply them, run::

    $ sudo -u apache /usr/bin/alembic -c /etc/bodhi/alembic.ini upgrade head


Features
^^^^^^^^

* Bodhi now provides a ``RateLimiter`` log filter and documents how to use it. Together with
  ``pyramid_sawing`` it is now possible to get rate limited e-mail tracebacks from the web server
  (:issue:`969`).
* All updates in a release are set to obsolete status when the release is archived (:issue:`2204`).
* Bodhi will now comment on updates when their test gating status changes (:issue:`2210`).
* ``bodhi-push`` now blocks composing retired releases (:issue:`2555`).
* A new ``bodhi.messages`` Python package has been added as a convenience for Python consumers
  who wish to subscribe to Bodhi's messages (:issue:`2842`).
* Bodhi can now create zchunked ``updateinfo.xml`` files (:issue:`2904`).
* The server has a new ``warm_cache_on_start`` setting, defaulting to ``True``. It is mostly
  useful when developing Bodhi and controls whether the Bodhi initialization should build caches or
  not (:issue:`2942`).
* The compose states are now documented (:issue:`2974`).
* Added a database index on ``build.update_id``, which sped up some common queries
  (:issue:`3038`).
* Log messages are emitted when buildroot overrides are expired to explain why they were expired
  (:issue:`3060`).
* A missing database index was discovered on ``comments.update_id``. Adding it improved performance
  of a common query by about 99.7% and as a result many Bodhi operations are much faster now,
  including update retrieval in the API, CLI, and web UI (:issue:`3062` and :issue:`3201`).
* The CLI now allows users to add and remove builds from updates with ``--addbuilds`` and
  ``--removebuilds`` flags (:issue:`3125`).
* Users can now use markdown to easily reference GCC and Sourceware tickets (:issue:`3129`).
* A new log message is emitted when an update is blocked due to test gating (:issue:`3143`).
* The CLI can now download debuginfo with the new ``--debuginfo`` flag (:issue:`3148`).


Bug fixes
^^^^^^^^^

* Since the ``active_releases`` query parameter was dropped, an issue causing strange pagination
  results is no longer present (:issue:`2316`).
* Waiver details are now displayed in the web UI (:issue:`2365`).
* The JavaScript will no longer crash when run in Fedora's staging environment (:issue:`2523`).
* Fixed a crash in Bodhi's error handler (:issue:`2588`).
* Fixed a crash on the HTML rendering of ``/composes/`` when composes were in a particular state
  (:issue:`2826`).
* Correctly handle ``ConnectionResetError`` in the Composer (:issue:`2850`).
* The CLI's composes info subcommand is now documented in its man page (:issue:`2927`).
* The ``mail.templates_basepath`` setting is now documented (:issue:`2931`).
* Fixed pipeline results showing with heading 'undefined' (:issue:`2969`).
* Compare enum values instead of descriptions (:issue:`3012` and :issue:`3119`).
* The ``bodhi-approve-testing`` script is a lot less chatty (:issue:`3021`).
* Bodhi's API can now serialize internal server errors as JSON so that the clients can properly
  display error messages (:issue:`3035`).
* The ``--composed-by-bodhi`` flag is now documented in the ``bodhi`` man page (:issue:`3085`).
* A variety of spelling and grammatical errors were fixed (:issue:`3131`).
* Bodhi's markdown now uses TLS for links to pear in its markdown (:issue:`3173`).
* Stop using an API that ``dnf`` removed (:issue:`3198`).
* Do not crash on invalid RSS requests (:issue:`3227`).


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* Removed flash_log, since it didn't make sense (:issue:`1165`).
* Removed some useless assert statements (:issue:`1200`, :issue:`2848`, and :issue:`2888`).
* An unused enum value was removed (:issue:`1999`).
* The integration tests now run against all supported Fedora releases (:issue:`2824`).
* Bodhi's release process is now documented (:issue:`2918`).
* ``met_testing_requirements()`` got a much needed rename and refactor (:issue:`3158`).
* The Vagrant box now uses the same number of CPUs as the host  (:issue:`3197`).
* Numerous docblock corrections and improvements.
* Introduced type annotation to a few modules and added CI enforcement on them with ``mypy``.
* Numerous improvements have been made to Bodhi's CI tests, including expanded test coverage.
* The Vagrant environment now uses unsafe IO for a small speed boost.
* The integration tests run more efficiently now.


Contributors
^^^^^^^^^^^^

The following developers contributed to Bodhi 4.0.0:

* Adam Williamson
* Anatoli Babenia
* Aurélien Bompard
* Clement Verna
* Jeremy Cline
* Jonathan Dieter
* Josh Soref
* Mattia Verga
* Miro Hrončok
* Nils Philippsen
* Owen W. Taylor
* Patrick Uiterwijk
* Sebastian Wojciechowski
* Troy Dawson
* Randy Barlow


Older releases
==============

.. toctree::
   :maxdepth: 2

   3.x_release_notes
   2.x_release_notes
