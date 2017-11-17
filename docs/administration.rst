==============
Administration
==============


System Requirements
===================

Bodhi is currently only supported on active Fedora releases. It requires PostgreSQL >= 9.2.0.


Configuration
=============

The Bodhi server is configured via an INI file found at ``/etc/bodhi/production.ini``. Bodhi ships
an example ``production.ini`` file that has all settings documented. Most settings have reasonable
defaults if not defined, and the example settings file describes the default values in the
commented settings. Here is a copy of the example config file with in-line documentation:

.. include:: ../production.ini
   :literal:
