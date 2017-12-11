===================
initialize_bodhi_db
===================

Synopsis
========

``initialize_bodhi_db`` ``CONFIG_URI``


Description
===========

``initialize_bodhi_db`` is used to create the initial database tables for the Bodhi server. It uses
the given ``CONFIG_URI`` to find the database settings to use.


Example
=======

``$ initialize_bodhi_db /etc/bodhi/production.ini``


Help
====

If you find bugs in bodhi (or in the man page), please feel free to file a bug report or a pull
request::

    https://github.com/fedora-infra/bodhi

Bodhi's documentation is available online: https://bodhi.fedoraproject.org/docs