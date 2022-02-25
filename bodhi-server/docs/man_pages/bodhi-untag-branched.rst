====================
bodhi-untag-branched
====================

Synopsis
========

``bodhi-untag-branched`` ``CONFIG_URI``


Description
===========

``bodhi-untag-branched`` is used to remove the pending and testing tags from updates in a branched
release.

Since a separate task compose the branched stable repos, this will leave
those stable updates with the testing tags for 1 day before untagging.


Example
=======

``$ bodhi-untag-branched /etc/bodhi/production.ini``


Help
====

If you find bugs in bodhi (or in the man page), please feel free to file a bug report or a pull
request::

    https://github.com/fedora-infra/bodhi

Bodhi's documentation is available online: https://bodhi.fedoraproject.org/docs
