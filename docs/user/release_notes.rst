=============
Release notes
=============

v4.0.0
======

This is a major release with many backwards incompatible changes.


Backwards incompatible changes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Integration with pkgdb is no longer supported (:issue:`1970`).
* Bodhi server no longer supports Python 2. Python 3 is the only supported Python release
  (:issue:`2759`).


Dependency changes
^^^^^^^^^^^^^^^^^^

* pkgdb is no longer required (:issue:`1970`).
* six is no longer required for the server (:issue:`2759`).


Server upgrade instructions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

No special actions are needed when applying this update.


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
