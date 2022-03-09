==========
bodhi-push
==========

Synopsis
========

``bodhi-push`` [OPTIONS]


Description
===========

``bodhi-push`` is used to select which packages to push out to the mirror network. It has various
flags that can be used to select the package set, and then it emits a message with the list of
packages to be mirrored.


Options
=======

``--help``

    Show help text and exit.

``--builds TEXT``

    A comma-separated list of builds to include in the push.

``--updates TEXT``

    A comma-separated list of update aliases to include in the push.

``--releases TEXT``

    A comma-separated list of releases to include in this push. By default, current and pending
    releases are selected.

``--request TEXT``

    Push updates for the specified request. Defaults to testing,stable.

``--resume``

    Resume one or more previously failed pushes.

``-y, --yes``

    Answers yes to the various questions.

``--username TEXT``

    Your FAS user id.

``--version``

    Show version and exit.


Help
====

If you find bugs in bodhi (or in the man page), please feel free to file a bug report or a pull
request::

    https://github.com/fedora-infra/bodhi

Bodhi's documentation is available online: https://bodhi.fedoraproject.org/docs