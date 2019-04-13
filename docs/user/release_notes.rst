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
  data structures, and Bodhi's messages (:issue:`1542`).
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
  ``mashtask.composing``, ``mashtask.complete``, ``mashtask.sync.wait`` and ``mashtask.sync.done``
  was renamed to ``compose.start``, ``compose.composing``, ``compose.complete``, ``compose.sync.wait``
  and ``compose.sync.done``, configuration settings ``mash_dir``, ``mash_stage_dir`` and
  ``max_concurrent_mashes`` was renamed to ``compose_dir``, ``compose_stage_dir`` and
  ``max_concurrent_composes`` (:issue:`2151`).
* The ``bodhi-monitor-composes`` script has been removed (:issue:`2171`).
* The stacks feature has been removed (:issue:`2241`).
* The ``bodhi-manage-releases`` script has been removed (:issue:`2420`).
* Support for anonymous comments was dropped. As a result, the ``anonymous`` field on the Comment
  object was removed and comments query API parameter ``anonymous`` was droped. All ``captcha.*``
  settings were removed (:issue:`2700`).
* Bodhi client and server no longer support Python 2. Python 3.6+ are the only supported Python
  releases (:issue:`2759`).
* Support for the ``ci_url`` on the ``Build`` object was dropped (:issue:`2782`).
* Support for ``active_releases`` parameter in updates query API was droped (:issue:`2815`).
* The ``/updates/ALIAS/TITLE`` API has been removed (:issue:`2869`).
* Support for update's old_updateid was dropped (:issue:`2903`).
* Support for update's greenwave_unsatisfied_requirements was dropped (:issue:`2958`).
* The batching feature was dropped, and thus updates can no longer be in the batched request state.
  As a result, the bodhi-dequeue-stable CLI has also been removed (:issue:`2977`).
* Support for obsolete scripts in ``tools`` folder was dropped (:issue:`2980`).
* Support for update's greenwave_summary_string has been dropped (:issue:`2988`).
* Bug objects no longer include a ``private`` field (:issue:`3016`).
* The CLI now defaults to the ``--wait`` flag when creating or editing buildroot overrides. The old
  behavior can be achieved with the ``--no-wait`` flag.
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


Server upgrade instructions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Bodhi server must be upgraded from Bodhi 3.13.0 or newer to 4.0.0 (i.e., it is not supported to
upgrade a server older than 3.13.0 directly to 4.0.0 as 4.0.0 has trimmed database migrations from
the older releases.

This release contains database migrations. To apply them, run::

    $ sudo -u apache /usr/bin/alembic -c /etc/bodhi/alembic.ini upgrade head


Features
^^^^^^^^


Contributors
^^^^^^^^^^^^

The following developers contributed to Bodhi 4.0.0:

* Randy Barlow


Older releases
==============

.. toctree::
   :maxdepth: 2

   3.x_release_notes
   2.x_release_notes
