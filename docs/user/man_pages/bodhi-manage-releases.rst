=====================
bodhi-manage-releases
=====================

Synopsis
========

``bodhi-manage-releases`` COMMAND [OPTIONS] [ARGS]...


Description
===========

``bodhi-manage-releases`` is used by Bodhi administrators to create or edit releases in Bodhi. It
can also be used to list information about an existing release.


Options
=======

Most of the commands will accept these options:

``--help``

    Show help text and exit.

``--url <url>``

    Use the Bodhi server at the given URL instead of the default server. This can also be set with
    the ``BODHI_URL`` environment variable.


Commands
========

There are three commands, ``create``, ``edit`` and ``info``.


create/edit
-----------

The ``create`` command allows administrators to create new releases in Bodhi. The ``edit`` command
allows administrators to edit existing releases. They both support the following options, with the
exception that only ``edit`` supports ``--new-name``:

``--branch TEXT``

    The git branch that corresponds to this release (e.g., f29).

``--candidate-tag TEXT``

    The Koji tag to use to search for update candidates (e.g., f29-updates-candidate).

``--dist-tag TEXT``

    The Koji dist tag for this release (e.g., f29).

``--id-prefix TEXT``

    The release's prefix (e.g., FEDORA).

``--long-name TEXT``

    The long name of the release (e.g., Fedora 29).

``--name TEXT``

    The name of the release (e.g., F29).

``--new-name``

    Change the release's name to a new value (e.g., F29). Only supported by ``edit``, and not
    ``create.``

``--override-tag TEXT``

    The Koji tag to use for buildroot overrides (e.g., f29-override).

``--password TEXT``

    The password to use when authenticating to Bodhi.

``--pending-stable-tag TEXT``

    The Koji tag to use on updates that are marked stable (e.g., f29-updates-pending).

``--pending-testing-tag TEXT``

    The Koji tag to use on updates that are pending testing (e.g., f29-updates-testing-pending).

``--stable-tag TEXT``

    The Koji tag to use for stable updates (e.g., f29-updates).

``--state [disabled|pending|current|archived]``

    The state of the release.

``--testing-tag TEXT``

    The Koji tag to use for testing updates (e.g., f29-updates-testing).

``--username TEXT``

    The username to use when authenticating to Bodhi.

``--version TEXT``

    The version of the release (e.g., 29).


info
====

``bodhi-manage-releases info RELEASE_NAME``

The ``info`` command prints information about the given release.


Help
====

If you find bugs in bodhi (or in the man page), please feel free to file a bug report or a pull
request::

    https://github.com/fedora-infra/bodhi

Bodhi's documentation is available online: https://bodhi.fedoraproject.org/docs
