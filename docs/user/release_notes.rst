=============
Release notes
=============

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
* Twisted is now required (:issue:`3145`).
* Bodhi now requires Python 3.6 or greater (:issue:`2856`).
* Bodhi no longer uses or works with ``fedmsg``.


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
