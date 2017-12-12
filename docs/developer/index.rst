=======================
Developer documentation
=======================

This page contains information for developers who wish to contribute to Bodhi.


Contribution guidelines
=======================

Before you submit a pull request to Bodhi, please ensure that it meets these criteria:

* All tests must pass.
* New code must have 100% test coverage. This one is particularly important, as we don't want to
  deploy any broken code into production. After you've run ``btest``, you can verify your new code's
  test coverage with ``bdiff-cover`` in the Vagrant environment, or
  ``diff-cover coverage.xml --compare-branch=origin/develop --fail-under=100`` if you are not using
  Vagrant.
* New functions, methods, and classes must have docblocks that explain what the code block is, and
  describing any parameters it accepts and what it returns (if anything). You can use the
  ``pydocstyle`` utility to automatically check your code for this. There is a
  ``bodhi.tests.test_style.TestStyle.test_code_with_pydocstyle`` test, that is slowly being expanded
  to enforce PEP-257 across the codebase.
* New code must follow `PEP-8 <https://www.python.org/dev/peps/pep-0008/>`_. You can use the
  ``flake8`` utility to automatically check your code. There is a
  ``bodhi.tests.test_style.TestStyle.test_code_with_flake8`` to enforce this style.
* Add an entry to ``docs/release_notes.rst`` for any changes you make that should be in release
  notes.
* Make sure your commits are atomic. Each commit should focus on one improvement or bug fix. If you
  need to build upon changes that are related but aren't atomic, feel free to send more than one
  commit in the same pull request.
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


Easy Fix
========

If you are looking for some easy tasks to get started with Bodhi development, have a look at Bodhi's
`EasyFix`_ tickets.

.. _EasyFix: https://github.com/fedora-infra/bodhi/issues?q=is%3Aopen+is%3Aissue+label%3AEasyFix


CI Tests
========

All Bodhi pull requests are tested in a `Jenkins instance <https://ci.centos.org/job/bodhi-bodhi/>`_
that is graciously hosted for us by the CentOS Project. Sometimes tests fail, and when they do you
can visit the test job that failed and view its console output. This will display the output from
the ``devel/ci/run_tests.sh`` script. That script runs Bodhi's test suite on a variety of
Fedora versions using containers.

It is possible for you to run these same tests locally. There is a ``devel/run_tests.sh`` script
that is used by ``devel/ci/run_tests.sh`` and does the heavy lifting. This script is intended to be
run as root since it uses ``docker``. It has a handy ``-x`` flag that will cause it to exit
immediately upon failure. You can also set the ``RELEASES`` environment variable to a list of Fedora
releases you wish to test in a given run. Thus, if I want to run the tests on only f26 and f27 and I
want it to exit immediately upon failure, I can execute the script like this::

    # RELEASES="f26 f27" ./devel/run_tests.sh

The CI system does not halt immediately upon failure, so that you can see all the problems at once.
Sometimes this makes it difficult to tell where the failure happened when looking at the console
output on the CI server. Some common failures will print out "JENKIES FAIL" to help with this. If
you browse to the console output on a job with failed tests, you can use your browser's text search
feature to find that string in the output to more quickly identify where the failure occurred.


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

.. _Vagrant: https://www.vagrantup.com
.. _Virtualenv: https://virtualenv.pypa.io/en/stable/
