=================
bodhi-skopeo-lite
=================

Synopsis
========

``bodhi-skopeo-lite`` COMMAND [OPTIONS] [ARGS]...


Description
===========

``bodhi-skopeo-lite`` is a very limited version of the `skopeo <https://github.com/containers/skopeo>`_
tool, but with support for manifests lists and OCI image indexes. The only command that is supported is
``copy``, and the only supported image references are Docker registry references of the form
``docker://docker-reference``.



Options
=======

``--help``

    Show help text and exit.


Commands
========

There is one command, ``copy``.

``bodhi-skopeo-lite copy [options] source-image destination-image``

The ``copy`` command copies an image from one location to another. It supports
the following options:

``--src-creds, --screds <username>[:<password>]``

    Use ``username`` and ``password`` for accessing the source registry.

``-src-tls-verify <boolean>``

    Require HTTPS and verify certificates when talking to the container
    source registry (defaults to ``true``).

``--src-cert-dir <path>``

    Use certificates at ``path`` (\*.crt, \*.cert, \*.key) to connect to the source registry.

``-dest-creds, --dcreds <username>[:<password>]``

    Use ``username`` and ``password`` for accessing the destination registry.

``--dest-tls-verify <boolean>``

    Require HTTPS and verify certificates when talking to the container
    destination registry (defaults to ``true``).

``--dest-cert-dir <path>``

    Use certificates at ``path`` (\*.crt, \*.cert, \*.key) to connect to the destination
    registry.

``--help``

    Show help text and exit.


Help
====

If you find bugs in bodhi (or in the man page), please feel free to file a bug report or a pull
request::

    https://github.com/fedora-infra/bodhi

Bodhi's documentation is available online: https://bodhi.fedoraproject.org/docs
