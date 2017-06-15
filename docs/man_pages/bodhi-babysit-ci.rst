================
bodhi-babysit-ci
================

Synopsis
========

``bodhi-babysit-ci``


Description
===========

``bodhi-babysit-ci`` iterates over Builds that have non-final CI statuses to see if Bodhi is
missing the scm_url for the Build. If it is, it queries Koji to find out the scm_url and saves it in
the database.


Options
=======

``--help``

    Display help text.

``--version``

    Report the Bodhi version and exit.


Help
====

If you find bugs in bodhi (or in the man page), please feel free to file a bug report or a pull
request:

    https://github.com/fedora-infra/bodhi

Bodhi's documentation is available online: https://bodhi.fedoraproject.org/docs
