=================
Automatic Updates
=================

Updates for releases which haven't yet reached the activation point (e.g. Rawhide) are automatically
created when Koji/robosignatory tags a build in the release candidate tag.

The Update is then processed through the common flow: if gating tests pass, the Update is pushed to
`Testing` and, immediatly after, to `Stable`. Usually it takes seconds or few minutes for the Update
to reach the `Stable` state.

It may happen sometimes that Bodhi misses the fedora-messaging message that announces a build have been tagged in the release candidate tag. In those cases the Update is not automatically created. In this situation the user must avoid creating a manual Update, because that Update will never be processed since it relates to a Release which is not composed by Bodhi. Instead the user should manually re-tag the affected build in the release candidate tag, so that a new fedora-messaging message is sent and Bodhi will (hopefully) catch and process it.

So, for example, assuming `Fedora 33` is Rawhide, if a user builds `foo-1.2.3-1.fc33` and the Update is not automatically created, they can re-tag the build in release candidate tag by using koji CLI with::

    $ koji untag-build f33-updates-candidate foo-1.2.3-1.fc33
    ...
    $ koji tag-build f33-updates-candidate foo-1.2.3-1.fc33

Associate bugs to automatic updates
===================================

Bugs can be associated to automatic updates by using appropriate keyword in the RPM changelog
of a build. The regex used to aquire the bug ids can be set in Bodhi config file. For a default
Bodhi installation this is automatically set to::

    fix(es)|close(s)|resolve(s)(:) (fedora|epel|rh|rhbz)#BUG_ID

The regex is performed case insensitive. So, if you want bug number 123456 to be attached to an
automatic update and closed upon update reaching stable, you can add a line (or more than one) to
the RPM changelog like this::

    %changelog
    * Sat Apr 04 2020 Mattia Verga  <mattia@fedoraproject.org> - 0.78-1
    - Update to 0.78
    - Fixes rhbz#123456
    - Resolves: epel#777777

Fedora Linux specific regex
---------------------------

Fedora (and EPEL) may use a different regex to catch bug IDs from changelog.

The current regex configuration is set to just::

    (fedora|epel|rh|rhbz)#BUG_ID

which means that every occurrence of a bug ID with the appropriate prefix will match, without the need of a particular keyword. So, the former example may be shrinked to::

    %changelog
    * Sat Apr 04 2020 Mattia Verga  <mattia@fedoraproject.org> - 0.78-1
    - Update to 0.78 (rhbz#123456, epel#777777)

If you want to avoid closing a bug, you can put a whitespace between the prefix and the bug ID, like `rhbz #123456`.
