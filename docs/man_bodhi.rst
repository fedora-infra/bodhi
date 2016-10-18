==================
bodhi CLI man page
==================

Synopsis
========

``bodhi`` COMMAND SUBCOMMAND [OPTIONS] [ARGS]...


Description
===========

``bodhi`` is the command line interface to bodhi, Fedora's update release management system. It can
be used to create or modify updates and overrides.


Options
=======

Most of the commands will accept these three options:

``--help``

    Show help text and exit.

``--password <text>``

    A password to authenticate as the user given by ``--user``.

``--staging``

    Use the staging bodhi instance instead of the production instance.

``--user <username>``

    Many commands accept this flag to specify which user's updates should be operated upon.

``--version``

    Show version and exit. Not accepted by subcommands.


Commands
========

There are two commands, ``overrides`` and ``updates``. They are described in more detail in their
own sections below.

``bodhi overrides <subcommand> [options] [args]``

    Provides commands to aid in management of build overrides. Supports subcommands ``query`` and
    ``save``, described below.

``bodhi updates <subcommand> [options] [args]``

    Provides an interface to manage updates. Supports subcommands ``comment``, ``download``,
    ``new``, ``query``, and ``request``, described below.


Overrides
=========

The ``overrides`` command allows users to manage build overrides.

``bodhi overrides query [options]``

    The ``query`` subcommand provides an interface for users to query the bodhi server for existing
    overrides.

``bodhi overrides save [options] <nvr>``

    Save the build root given by ``<nvr>`` as a buildroot override. The ``save`` subcommand supports
    the following options:

    ``--duration <days>``

        The number of days the override should exist, given as an integer.

    ``--notes <text>``

        Notes on why this override is in place.


Updates
=======

The ``updates`` command allows users to interact with bodhi updates.

``bodhi updates comment [options] <update> <text>``

    Leave the given text as a comment on a bodhi update. The ``comment`` subcommand
    supports the following options:

    ``--karma [+1 | 0 | -1]``

        The karma value you wish to contribute to the update.

``bodhi updates download [options]``

    Download update(s) given by CVE(s), ID(s), or NVR(s). One of ``--cves``, ``--updateid``, or
    ``builds`` is required. The download subcommand supports the following options:

    ``--cves <cves>``

        A comma-separated list of CVEs that identify updates you would like to download.

    ``--updateid <ids>``

        A comman-separated list of update IDs you would like to download.

    ``--builds <nvrs``

        A comma-separated list of NVRs that identify updates you would like to download.

``bodhi updates new [options] <builds>``

    Create a new bodhi update containing the builds, given as a space separated list of NVRs. The
    ``new`` subcommand supports the following options:

    ``--type [security | bugfix | enhancement | newpackage]``

        The type of the new update.

    ``--notes <text>``

        The description of the update.

    ``--notes-file <path>``

        A path to a file containing a description of the update.

    ``--bugs <bugs>``

        A comma separated list of bugs to associate with this update.

    ``--close-bugs``

        If given, this flag will cause bodhi to close the referenced bugs automatically when the
        update reaches stable.

    ``--request [testing | stable | upush]``

        The repository requested for this update.

    ``--autokarma``

        Enable autokarma for this update.

    ``--stable-karma <integer>``

        Configure the stable karma threshold for the given value.

    ``--unstable-karma <integer>``

        Configure the unstable karma threshold for the given value.

    ``--suggest [logout | reboot]``

        Suggest that the user logout or reboot upon applying the update.

    ``--file <path>``

        A path to a file containing all the update details.

``bodhi updates query [options]``

    Query the bodhi server for updates. The ``query`` subcommand supports the following options:

    ``--updateid <id>``

        Query for the update given by id.

    ``--approved-since <timestamp>``

        Query for updates approved after the given timestamp.

    ``--modified-since <timestamp>``

        Query for updates modified after the given timestamp.

    ``--builds <builds>``

        Query for updates containing the given builds, given as a comma-separated list.

    ``--bugs <bugs>``

        Query for updates related to the given bugs, given as a comma-separated list.

    ``--critpath``

        Query for updates submitted for the critical path.

    ``--cves <cves>``

        Query for updates related to the given CVEs, given as a comma-separated list.

    ``--packages <packages>``

        Query for updates related to the given packages, given as a comma-separated list.

    ``--pushed``

        Query for updates that have been pushed.

    ``--pushed-since <timestamp>``

        Query for updates that have been pushed after the given timestamp.

    ``--releases <releases>``

        Query for updates related to a list of releases, given as a comma-separated list.

    ``--locked``

        Query for updates that are currently locked.

    ``--request [testing | stable | unpush]``

        Query for updates marked with the given request type.

    ``--submitted-since <timestamp>``

        Query for updates that were submitted since the given timestamp.

    ``--status [pending | testing | stable | obsolete | unpushed | processing]``

        Filter by status.

    ``--suggest [logout | reboot]``

        Filter for updates that suggest logout or reboot to the user.

    ``--type [newpackage | security | bugfix | enhancement]``

        Filter by update type.

    ``--user <username>``

        Filter for updates by the given username.

``bodhi updates request [options] <update> <state>``

    Request that the given update be changed to the given state. ``update`` should be given by
    update id, and ``state`` should be one of testing, stable, unpush, obsolete, or revoke.


Bugs
====

If you find bugs in bodhi (or in the mage page), please feel free to file a bug report or a pull
request::

    https://github.com/fedora-infra/bodhi
