=====
bodhi
=====

Synopsis
========

``bodhi`` COMMAND SUBCOMMAND [OPTIONS] [ARGS]...


Description
===========

``bodhi`` is the command line interface to bodhi, Fedora's update release management system. It can
be used to create or modify updates and overrides.


Options
=======

Most of the commands will accept these options:

``--debug``

    Some commands accept this flag to show extra debug information.

``--help``

    Show help text and exit.

``--password <text>``

    A password to authenticate as the user given by ``--user``.

``--staging``

    Use the staging bodhi instance instead of the production instance.

``--url <url>``

    Use the Bodhi server at the given URL instead of the default server. This can also be set with
    the ``BODHI_URL`` environment variable. This is ignored if the ``--staging`` flag is set.

``--user <username>``

    Many commands accept this flag to specify a Fedora username to authenticate with. Note that some
    read operations such as querying updates and overrides use this same flag, but as a search
    parameter instead of authentication (as authentication is not required for these operations).

``--version``

    Show version and exit. Not accepted by subcommands.


Commands
========

There are four commands, ``composes``, ``overrides``, ``updates`` and ``releases``. They are described
in more detail in their own sections below.

``bodhi composes <subcommand> [options] [args]``

    Provides an interface to view composes. Supports subcommands ``list`` and ``info``, described below.

``bodhi overrides <subcommand> [options] [args]``

    Provides commands to aid in management of build overrides. Supports subcommands ``query`` and
    ``save``, described below.

``bodhi updates <subcommand> [options] [args]``

    Provides an interface to manage updates. Supports subcommands ``comment``, ``download``,
    ``new``, ``query``, and ``request``, described below.

``bodhi releases <subcommand> [options] [args]``

    Provides an interface to manage releases. Supports subcommands ``create``, ``edit``, ``info`` and
    ``list``, described below.


Composes
========

The ``composes`` command allows users to view composes.

``bodhi composes list [options]``

   The ``list`` subcommand allows you to see the current composes on the Bodhi server. It supports
   the following options:

   ``-v, --verbose``

       Print more detail about the composes.

``bodhi composes info [options] RELEASE REQUEST``

   The ``info`` subcommand allows you to see the compose for release with the given request.


Overrides
=========

The ``overrides`` command allows users to manage build overrides.

``bodhi overrides query [options]``

    The ``query`` subcommand provides an interface for users to query the bodhi server for existing
    overrides.  The ``query`` subcommand supports the following options:

    ``--mine``

        Show only your overrides.

    ``--active``

        Filter for only active overrides

    ``--expired``

        Filter for only expired overrides

    ``--packages <packagename>``

        Query for overrides related to the given packages, given as a comma-separated list.

    ``--releases <releases>``

        Query for overrides related to a list of releases, given as a comma-separated list.
        <releases> is the release shortname, for example: F26 or F26,F25

    ``--builds <builds>``

        Query for overrides for a list of builds, given as a comma-separated list.
        <builds> is the build NVR, for example: corebird-1.3-0.fc24

    ``--user <username>``

        Filter for overrides by a list of usernames, given as a comma-separated list.

    ``--rows <integer>``

        Limits number of results shown per page.

    ``--page <integer>``

        Go to page number.

``bodhi overrides save [options] <nvr>``

    Save the build root given by ``<nvr>`` as a buildroot override. The ``save`` subcommand supports
    the following options:

    ``--duration <days>``

        The number of days the override should exist, given as an integer.

    ``--notes <text>``

        Notes on why this override is in place.

``bodhi overrides edit [options] <nvr>``

    Edit the build root given by ``<nvr>`` as a buildroot override. The ``edit`` subcommand supports
    the same options than the ``save`` command and also the following option:

    ``--expire``
        Force an override to the expired state.

Updates
=======

The ``updates`` command allows users to interact with bodhi updates.

``bodhi updates comment [options] <update> <text>``

    Leave the given text as a comment on a bodhi update. The ``comment`` subcommand
    supports the following options:

    ``--karma [+1 | 0 | -1]``

        The karma value you wish to contribute to the update.

``bodhi updates download [options]``

    Download update(s) given by ID(s) or NVR(s). One of ``--updateid`` or
    ``builds`` is required. The download subcommand supports the following options:

    ``--debuginfo``

        Include debuginfo packages when downloading.

    ``--updateid <ids>``

        A comma-separated list of update IDs you would like to download.

    ``--builds <nvrs>``

        A comma-separated list of NVRs that identify updates you would like to download.

    ``--arch <arch>``

        You can specify an architecture of packages to download. "all" will download packages for all architectures.
        Omitting this option will download packages for the architecture you are currently running.

``bodhi updates new [options] <builds_or_tag>``

    Create a new bodhi update containing the builds, given as a comma separated list of NVRs. The
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

    ``--autotime``

        Enable autotime for this update. Automatically push the update to stable based on the
        time spent in testing.

    ``--stable-karma <integer>``

        Configure the stable karma threshold for the given value.

    ``--unstable-karma <integer>``

        Configure the unstable karma threshold for the given value.

    ``--stable-days <integer>``

        Configure the number of days an update has to spend in testing before
        being automatically pushed to stable.

    ``--suggest [logout | reboot]``

        Suggest that the user logout or reboot upon applying the update.

    ``--file <path>``

        A path to a file containing all the update details.

    ``--requirements <Taskotron tasks>``

        A comma or space-separated list of required Taskotron tasks that must pass for this update
        to reach stable.

    ``--display-name <text>``

        The name of the update

    ``--from-tag``

        If this flag is provided, ``<builds_or_tag>`` will be interpreted as a Koji tag and expand
        to all latest builds in it. Only a single tag can be provided.

``bodhi updates edit [options] <update>``

    Edit an existing bodhi update, given an update id or an update title. The
    ``edit`` subcommand supports the following options:

    ``--addbuilds <builds>``

        Add a comma separated list of build nvr to this update.

    ``--removebuilds <builds>``

        Remove a comma separated list of build nvr from this update.

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

    ``--requirements <Taskotron tasks>``

        A comma or space-separated list of required Taskotron tasks that must pass for this update
        to reach stable.

    ``--display-name <text>``

        The name of the update

    ``--from-tag``

        If given, for updates that were created from a Koji tag, this will update
        the builds to the latest ones in the tag.


``bodhi updates query [options]``

    Query the bodhi server for updates.
    
    If the query returns only one update, a detailed view of the update will be displayed.
    
    If more than one update is returned, the command will display a list showing the packages
    contained in the update, the update content-type (rpm / module / ...), the current status
    of the update (pushed / testing / ...) and the date of the last status change with
    the number of days passed since. A leading ``*`` marks security updates.
    
    The ``query`` subcommand supports the following options:

    ``--updateid <id>``

        Query for the update given by id.

    ``--title <title>``

        Query for the update given by title.

    ``--alias <alias>``

        Query for the update given by alias.

    ``--approved-since <timestamp>``

        Query for updates approved after the given timestamp.

    ``--approved-before <timestamp>``

        Query for updates approved before the given timestamp.

    ``--modified-since <timestamp>``

        Query for updates modified after the given timestamp.

    ``--modified-before <timestamp>``

        Query for updates modified before the given timestamp.

    ``--builds <builds>``

        Query for updates containing the given builds, given as a comma-separated list.

    ``--bugs <bugs>``

        Query for updates related to the given bugs, given as a comma-separated list.

    ``--content-type <content_type>``

        Query for updates of a given content type: either rpm, module, or (in the future) container.

    ``--critpath``

        Query for updates submitted for the critical path.

    ``--mine``

        Show only your updates.

    ``--packages <packages>``

        Query for updates related to the given packages, given as a comma-separated list.

    ``--pushed``

        Query for updates that have been pushed.

    ``--pushed-since <timestamp>``

        Query for updates that have been pushed after the given timestamp.

    ``--pushed-before <timestamp>``

        Query for updates that have been pushed before the given timestamp.

    ``--releases <releases>``

        Query for updates related to a list of releases, given as a comma-separated list.

    ``--locked``

        Query for updates that are currently locked.

    ``--request [testing | stable | unpush]``

        Query for updates marked with the given request type.

    ``--severity [unspecified, urgent, high, medium, low]``

        Query for updates with a specific severity.

    ``--submitted-since <timestamp>``

        Query for updates that were submitted since the given timestamp.

    ``--submitted-before <timestamp>``

        Query for updates that were submitted before the given timestamp.

    ``--status [pending | testing | stable | obsolete | unpushed]``

        Filter by status.

    ``--suggest [logout | reboot]``

        Filter for updates that suggest logout or reboot to the user.

    ``--type [newpackage | security | bugfix | enhancement]``

        Filter by update type.

    ``--user <username>``

        Filter for updates by a list of usernames, given as a comma-separated list.

    ``--rows <integer>``

        Limits number of results shown per page.

    ``--page <integer>``

        Go to page number.

``bodhi updates request [options] <update> <state>``

    Request that the given update be changed to the given state. ``update`` should be given by
    update id, and ``state`` should be one of testing, stable, unpush, obsolete, or revoke.

``bodhi updates waive [options] <update> <comment>``

    Show or waive unsatisfied test requirements on an update.

    The following options are supported:

    ``--show``

        List the unsatisfied test requirements.

    ``--test TEXT``

        Waive the test specified by name in TEXT. all can be used to waive all unsatisfied tests.

    ``--debug``

        Display debugging information.

``bodhi updates trigger-tests [options] <update>``

    Trigger tests for an update. This update must be in testing state.

Releases
=========

The ``releases`` command allows users to manage update releases.

``bodhi releases create [options]``

    The ``create`` command allows administrators to create new releases in Bodhi:

    ``--branch TEXT``

        The git branch that corresponds to this release (e.g., f29).

    ``--candidate-tag TEXT``

        The Koji tag to use to search for update candidates (e.g., f29-updates-candidate).

    ``--composed-by-bodhi, --not-composed-by-bodhi``

        The flag that indicates whether the release is composed by Bodhi or not.

    ``--dist-tag TEXT``

        The Koji dist tag for this release (e.g., f29).

    ``--id-prefix TEXT``

        The release's prefix (e.g., FEDORA).

    ``--long-name TEXT``

        The long name of the release (e.g., Fedora 29).

    ``--name TEXT``

        The name of the release (e.g., F29).

    ``--override-tag TEXT``

        The Koji tag to use for buildroot overrides (e.g., f29-override).

    ``--package-manager [unspecified|dnf|yum]``

        The package manager used by this release. If not specified it defaults to 'unspecified'.

    ``--password TEXT``

        The password to use when authenticating to Bodhi.

    ``--pending-stable-tag TEXT``

        The Koji tag to use on updates that are marked stable (e.g., f29-updates-pending).

    ``--pending-testing-tag TEXT``

        The Koji tag to use on updates that are pending testing (e.g., f29-updates-pending-testing).

    ``--stable-tag TEXT``

        The Koji tag to use for stable updates (e.g., f29-updates).

    ``--state [disabled|pending|frozen|current|archived]``

        The state of the release.

    ``--testing-repository TEXT``

        The name of the testing repository used to test updates. Not required.

    ``--testing-tag TEXT``

        The Koji tag to use for testing updates (e.g., f29-updates-testing).

    ``--username TEXT``

        The username to use when authenticating to Bodhi.

    ``--version TEXT``

        The version of the release (e.g., 29).

``bodhi releases edit [options]``

    The ``edit`` command allows administrators to edit existing releases:

    ``--branch TEXT``

        The git branch that corresponds to this release (e.g., f29).

    ``--candidate-tag TEXT``

        The Koji tag to use to search for update candidates (e.g., f29-updates-candidate).

    ``--composed-by-bodhi, --not-composed-by-bodhi``

        The flag that indicates whether the release is composed by Bodhi or not.

    ``--dist-tag TEXT``

        The Koji dist tag for this release (e.g., f29).

    ``--id-prefix TEXT``

        The release's prefix (e.g., FEDORA).

    ``--long-name TEXT``

        The long name of the release (e.g., Fedora 29).

    ``--name TEXT``

        The name of the release (e.g., F29).

    ``--new-name``

        Change the release's name to a new value (e.g., F29).

    ``--override-tag TEXT``

        The Koji tag to use for buildroot overrides (e.g., f29-override).

    ``--package-manager [unspecified|dnf|yum]``

        The package manager used by this release. If not specified it defaults to 'unspecified'.

    ``--password TEXT``

        The password to use when authenticating to Bodhi.

    ``--pending-stable-tag TEXT``

        The Koji tag to use on updates that are marked stable (e.g., f29-updates-pending).

    ``--pending-testing-tag TEXT``

        The Koji tag to use on updates that are pending testing (e.g., f29-updates-testing-pending).

    ``--stable-tag TEXT``

        The Koji tag to use for stable updates (e.g., f29-updates).

    ``--state [disabled|pending|frozen|current|archived]``

        The state of the release.

    ``--testing-repository TEXT``

        The name of the testing repository used to test updates. Not required.

    ``--testing-tag TEXT``

        The Koji tag to use for testing updates (e.g., f29-updates-testing).

    ``--username TEXT``

        The username to use when authenticating to Bodhi.

    ``--version TEXT``

        The version of the release (e.g., 29).

``bodhi releases info RELEASE_NAME``

    The ``info`` command prints information about the given release.

``bodhi releases list [options]``

    The ``list`` command prints list of releases.

    ``--display-archived``

        Display full list, including archived releases.

    ``--rows <integer>``

        Limits number of results shown per page.

    ``--page <integer>``

        Go to page number.


Examples
========

Create a new update with multiple builds::

    $ bodhi updates new --user bowlofeggs --type bugfix --notes "Fix permission issues during startup." --bugs 1393587 --close-bugs --request testing --autokarma --stable-karma 3 --unstable-karma -3 ejabberd-16.09-2.fc25,erlang-esip-1.0.8-1.fc25,erlang-fast_tls-1.0.7-1.fc25,erlang-fast_yaml-1.0.6-1.fc25,erlang-fast_xml-1.1.15-1.fc25,erlang-iconv-1.0.2-1.fc25,erlang-stringprep-1.0.6-1.fc25,erlang-stun-1.0.7-1.fc25


Help
====

If you find bugs in bodhi (or in the man page), please feel free to file a bug report or a pull
request::

    https://github.com/fedora-infra/bodhi

Bodhi's documentation is available online: https://bodhi.fedoraproject.org/docs
