=======================
Developer documentation
=======================

This page contains information for developers who wish to contribute to Bodhi.


Contribution guidelines
=======================

Before you submit a pull request to Bodhi, please ensure that it meets these criteria:

* All tests must pass.
* New code must have 100% test coverage. This one is particularly important, as we don't want to
  deploy any broken code into production. At the end of ``btest`` run, you can see your code coverage.
  If you are not using Vagrant environment you can check the code coverage by running
  ``diff-cover coverage.xml --compare-branch=origin/develop --fail-under=100``.
* New functions, methods, and classes must have docblocks that explain what the code block is, and
  describing any parameters it accepts and what it returns (if anything). You can use the
  ``pydocstyle`` utility to automatically check your code for this. You can also run ``pydocstyle bodhi``
  in Vagrant.
* Parameter and return value types should be declared using `type hints`_. You can test this by running
  ``bci mypy`` in Vagrant.
* New code must follow `PEP-8 <https://www.python.org/dev/peps/pep-0008/>`_. You can use the
  ``flake8`` utility to automatically check your code. Alternatively you can run ``flake8-3``
  in Vagrant.
* If you want to run the three above at once you can use ``blint`` alias in Vagrant.
* Make sure your commits are atomic. With only rare exceptions, each improvement or bug fix should
  have exactly one commit. This makes it much easier to peruse the git history to find out which
  changes relate to a feature or bugfix implementation, and is particularly valuable when commits
  need to be cherry picked. If you need to build upon prior unmerged commits while fixing a
  different issue, feel free to send more than one commit in the same pull request.
* Your commit messages must include a Signed-off-by tag with your name and e-mail address,
  indicating that you agree to the
  `Developer Certificate of Origin <https://developercertificate.org/>`_. Bodhi uses version 1.1 of
  the certificate, which reads::

   Developer Certificate of Origin
   Version 1.1

    Copyright (C) 2004, 2006 The Linux Foundation and its contributors.
    1 Letterman Drive
    Suite D4700
    San Francisco, CA, 94129

    Everyone is permitted to copy and distribute verbatim copies of this
    license document, but changing it is not allowed.


    Developer's Certificate of Origin 1.1

    By making a contribution to this project, I certify that:

    (a) The contribution was created in whole or in part by me and I
        have the right to submit it under the open source license
        indicated in the file; or

    (b) The contribution is based upon previous work that, to the best
        of my knowledge, is covered under an appropriate open source
        license and I have the right under that license to submit that
        work with modifications, whether created in whole or in part
        by me, under the same open source license (unless I am
        permitted to submit under a different license), as indicated
        in the file; or

    (c) The contribution was provided directly to me by some other
        person who certified (a), (b) or (c) and I have not modified
        it.

    (d) I understand and agree that this project and the contribution
        are public and that a record of the contribution (including all
        personal information I submit with it, including my sign-off) is
        maintained indefinitely and may be redistributed consistent with
        this project or the open source license(s) involved.

  For example, Randy Barlow's commit messages include this line::

   Signed-off-by: Randy Barlow <randy@electronsweatshop.com>
* Code may be submitted by opening a pull request at
  `github.com/fedora-infra/bodhi <https://github.com/fedora-infra/bodhi/>`_, or you may e-mail a
  patch to the
  `mailing list <https://lists.fedoraproject.org/archives/list/bodhi@lists.fedorahosted.org/>`_.
* If your changes contain database migrations, you must add a file named ``summary.migration``
  in the ``news`` directory, where ``summary`` is a short textual description of the change
  (or the issue number you're fixing).
* If it is not present already, add a file in the ``news`` directory named ``username.author``
  where ``username`` is the first part of your commit's email address, and containing the name
  you want to be credited as.
* If you think that the changes you make should be in release notes, add a file in the ``news``
  directory with the format explained below.

Release Notes
-------------

To add entries to the release notes, create a file in the ``news`` directory in the
``source.type`` name format, where the ``source`` part of the filename is:

* ``42`` when the change is described in issue ``42``
* ``PR42`` when the change has been implemented in pull request ``42``, and
  there is no associated issue
* ``Cabcdef`` when the change has been implemented in changeset ``abcdef``, and
  there is no associated issue or pull request.

And where the extension ``type`` is one of:

* ``bic``: for backwards incompatible changes
* ``dependency``: for dependency changes
* ``feature``: for new features
* ``bug``: for bug fixes
* ``dev``: for development improvements
* ``docs``: for documentation improvements
* ``other``: for other changes

The content of the file will end up in the release notes. It should not end with a ``.``
(full stop). A preview of the release notes can be generated with ``towncrier --draft``.


Issues
======

Bodhi uses GitHub's `issue tracker <https://github.com/fedora-infra/bodhi/issues>`_ and
`kanban boards <https://github.com/fedora-infra/bodhi/projects>`_ to track and plan issues and work.
If you aren't sure what you'd like to work on, take a look at Bodhi's
`labels <https://github.com/fedora-infra/bodhi/labels>`_ which are used to categorize the various
issues. Each label has a short description explaining its purpose.


Easy Fix
--------

If you are looking for some easy tasks to get started with Bodhi development, have a look at Bodhi's
`EasyFix`_ tickets.

.. _EasyFix: https://github.com/fedora-infra/bodhi/issues?q=is%3Aopen+is%3Aissue+label%3AEasyFix


CI Tests
========

All Bodhi pull requests are tested in a `Jenkins instance <https://ci.centos.org/>`_
that is graciously hosted for us by the CentOS Project. Sometimes tests fail, and when they do you
can visit the test job that failed and view its console output by visiting the
`bodhi-pipeline job <https://ci.centos.org/job/bodhi-pipeline/>`_. Links to individual pull request
builds can be found on your pull request on GitHub by clicking the "Details" link next to
``continuous-integration/jenkins/pr-merge``. From there you can inspect the full console output, or
you can click into the "Pipeline Steps" on the left to see the output of each individual job.

Bodhi's CI pipeline workflow is described in `Groovyscript <http://www.groovy-lang.org/>`_ in
``devel/ci/cico.pipeline``. This file is fairly well self-documented, and described to Jenkins how
it should run Bodhi's tests. It defines the various GitHub contexts that our ``.mergify.yml``
configuration is set to block merges on, and it runs the individual build and test jobs in parallel.

It is possible for you to run these same tests locally. There is a ``devel/ci/bodhi-ci`` script
that is used by the pipeline to do the heavy lifting. This script is intended to be
run as root since it uses ``docker`` (or optionally, ``podman``). It has a handy ``-x`` flag that
will cause it to exit immediately upon failure. You can also choose to test specific releases, and
there are a variety of other features. Be sure to check out its ``--help`` flag to learn how to use
it. Thus, if I want to run the tests on only f28 and f29 and I want it to exit immediately upon
failure, I can execute the script like this::

    $ sudo devel/ci/bodhi-ci all -r f28 -r f29 -x

Note that if you are using the Vagrant development environment, there is a handy ``bci`` shell alias
that runs ``sudo devel/ci/bodhi-ci`` for you.


Create a Bodhi development environment
======================================

There are two ways to bootstrap a Bodhi development environment. You can use Vagrant, or you can use
virtualenv on an existing host. `Vagrant`_ allows contributors to get quickly up and running with a
Bodhi development environment by automatically configuring a virtual machine. `Virtualenv`_ is
a more manual option for building a development environment on an existing system. If you aren't
sure which development environment you would like to use, Vagrant is recommended as it get you a
working system more quickly and with less effort. If you would like to use Vagrant, see the
:doc:`Bodhi Vagrant Guide <vagrant>`. If you would like to use Virtualenv, see the
:doc:`Bodhi Virtualenv Guide <virtualenv>`.

.. _docs/user/release_notes.rst: https://github.com/fedora-infra/bodhi/blob/develop/docs/user/release_notes.rst#release-notes
.. _type hints: https://docs.python.org/3/library/typing.html
.. _Vagrant: https://www.vagrantup.com
.. _Virtualenv: https://virtualenv.pypa.io/en/stable/
