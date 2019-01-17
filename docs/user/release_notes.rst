=============
Release notes
=============

v4.0.0
======

This is a major release with many backwards incompatible changes.


Backwards incompatible changes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Values NULL and 0 are not allowed in update's stable_karma and unstable_karma (:issue:`1029`).
* Integration with pkgdb is no longer supported (:issue:`1970`).
* The ``/admin/`` API has been removed (:issue:`1985`).
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
* Bodhi server no longer supports Python 2. Python 3 is the only supported Python release
  (:issue:`2759`).
* Support for the ``ci_url`` on the ``Build`` object was dropped (:issue:`2782`).
* Support for ``active_releases`` parameter in updates query API was droped (:issue:`2815`).
* The ``/updates/ALIAS/TITLE`` API has been removed (:issue:`2869`).
* Support for update's old_updateid was dropped (:issue:`2903`).
* Support for update's greenwave_unsatisfied_requirements was dropped (:issue:`2958`).
* The batching feature was dropped, and thus updates can no longer be in the batched request state.
  As a result, the bodhi-dequeue-stable CLI has also been removed (:issue:`2977`).
* Support for obsolete scripts in ``tools`` folder was dropped (:issue:`2980`).
* Bug objects no longer include a ``private`` field (:issue:`3016`).


Dependency changes
^^^^^^^^^^^^^^^^^^

* pkgdb is no longer required (:issue:`1970`).
* six is no longer required for the server (:issue:`2759`).


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
