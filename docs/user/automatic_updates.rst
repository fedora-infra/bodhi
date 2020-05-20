=================
Automatic Updates
=================

Updates for releases which haven't yet reached the activation point (e.g. Rawhide) are automatically
created when Koji tags a build in the release candidate tag.

The Update then is processed through the common flow: if gating tests pass, the Update is pushed to
`Testing` and, immediatly after, to `Stable`. Usually it takes seconds or few minutes for the Update
to reach the `Stable` state.

Associate bugs to automatic updates
===================================

Bugs can be associated to automatic updates by using appropriate keyword in the RPM changelog
of a build. The regex used to aquire the bug ids can be set in Bodhi config file. For a default
Bodhi installation this is automatically set to::

    fix(es)|close(s) (fedora|epel|rh|rhbz)#BUG_ID

The regex is performed case insensitive. So, if you want bug number 123456 to be attached to an
automatic update and closed upon update reaching stable, you can add a line to the RPM changelog
like this::

    %changelog
    * Sat Apr 04 2020 Mattia Verga  <mattia@fedoraproject.org> - 0.78-1
    - Update to 0.78
    - Fixes rhbz#123456

Just be sure to use the appropriate format for every bug you want to add. For example, this will
**NOT** work::

   %changelog
    * Sat Apr 04 2020 Mattia Verga  <mattia@fedoraproject.org> - 0.78-1
    - Update to 0.78
    - Fix rhbz#123456, rhbz#987654

Use this instead::

   %changelog
    * Sat Apr 04 2020 Mattia Verga  <mattia@fedoraproject.org> - 0.78-1
    - Update to 0.78
    - Fix rhbz#123456, fix rhbz#987654
