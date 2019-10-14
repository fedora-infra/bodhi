===============
Release process
===============

This document describes the process for making a Bodhi release.


Branches
========

Bodhi follows `semantic versioning`_, and so `backwards incompatible`_ changes get a major release,
releases with new features get a minor release, and releases that only contain bug fixes get a patch
release.

To aid in maintaining this scheme, Bodhi uses branches named with the scheme ``major.minor`` to keep
track of feature releases. Once a ``major.minor`` branch is created and a release is tagged, only
bugfixes should be added to that branch.

When you wish to make a patch release, simply cherry pick (described below) the patches you wish to
include in the release to the appropriate ``major.minor`` branch.

If you wish to make a minor release, you will need to create a new ``major.minor`` branch.
Typically we would do this by branching from a desired commit on the ``develop`` branch, unless
there are backwards incompatible changes in ``develop``. If ``develop`` has backwards incompatible
commits that we don't want to release with, you should branch from the most recent ``major.minor``
branch, and then cherry pick the desired commits from ``develop``.

Of course, if you want to make a new major release, simply create a ``major.minor`` branch from the
desired commit on ``develop``.


Cherry picking
--------------

To simplify the release process, almost all patches are sent to the ``develop`` branch. Once they
are reviewed and merged, they can be cherry picked to a ``major.minor`` branch if desired. To aid in
this process, we use `Mergify`_'s `patch backporting feature`_. For each actively maintained
release there should be a backporting action in the Mergify config and an associated GitHub label.
For example, as of the time of this writing we have active 3.12 and 3.13 branches, so we have GitHub
labels called ``3.12-backports`` and ``3.13-backports``. Any pull requests tagged with either of
these tags will cause Mergify to backport the associated patch to the relevant branch via a new pull
request.

.. note:: The backporting feature is configured in ``.mergify.yml``.


How to make a release
=====================

Preparation
-----------

If you are making a new major or minor release:

#. Prepare the ``.mergify.yml`` file for the new ``major.minor`` branch as described above.
#. Raise the version to the appropriate value in ``bodhi/__init__.py``.
#. Add missing authors to the release notes fragments by changing to the ``news`` directory and
   running the ``get-authors.py`` script, but check for duplicates and errors
#. Generate the release notes by running ``towncrier``. Be aware that any commits that were cherry
   picked to a previous release branch will show up again, and we wouldn't want to mark those
   commits as being new
#. Add a note to all the associated issues and pull requests to let them know they will be included
   in this release.
#. Push those changes to the upstream repository (via a PR or not)
#. Create the branch protection rule in `GitHub's UI
   <https://github.com/fedora-infra/bodhi/settings/branches>`_ and tick the following boxes:

   * Require pull request reviews before merging
   * Require status checks to pass before merging
   * Require branches to be up to date before merging
   * ``DCO``
   * ``fXX-diff-cover``, ``fXXdocs``, ``fXX-integration``, and ``fXX-unit`` where ``XX`` is the
     Fedora version that this Bodhi release is going to run on.

#. Create the new ``major.minor`` branch in the repository, and switch to that branch.
#. Adjust ``diff-cover`` to use the new ``major.minor`` branch for comparison in
   ``devel/ci/bodhi-ci``. You can find the spot to edit by searching for the ``--compare-branch``
   flag being passed to ``diff-cover``. This change should remain in that release branch only.
#. Push that new branch to the upstream repository

Build a beta
------------

Bodhi uses the `Fedora Rawhide spec file`_ to build production RPMs for the
`Fedora Infrastructure repositories`_. As upstream Bodhi does not have any infrastructure of its own
for beta testing, we use `Fedora's staging instance`_ of Bodhi to do our beta testing. Thus, in
order to build and test the beta using these instructions, you will need administrative access to
the staging Bodhi deployment and you will need access to build in the staging infrastructure
repository.

To build the beta, follow these steps:

#. Clone the Bodhi spec file repository::

   $ fedpkg clone bodhi

#. Alter the spec file to build the commit you want to test rather than a tagged release. Use a
   value less than one for the release field on betas (for example the first might be 0.0, the
   second might be 0.1, and so on). For example, to test
   ``e0ca5bc5d36e8cca5bd126879a036006356645e6`` (which is a 3.13 beta), a patch like this will
   work::

    $ git diff
    diff --git a/bodhi.spec b/bodhi.spec
    index eaf3415..d3684be 100644
    --- a/bodhi.spec
    +++ b/bodhi.spec
    @@ -1,16 +1,21 @@
     %global bashcompdir     %(pkg-config --variable=completionsdir bash-completion 2>/dev/null)
     %global bashcomproot    %(dirname %{bashcompdir} 2>/dev/null)
     
    +%global commit e0ca5bc5d36e8cca5bd126879a036006356645e6
    +%global commit_short %(c=%{commit}; echo ${c:0:7})
    +
     Name:           bodhi
    -Version:        3.12.0
    -Release:        100%{?dist}
    +Version:        3.13.0
    +Release:        0.0.beta.%{commit_short}%{?dist}
     BuildArch:      noarch
     
     License:        GPLv2+
     Summary:        A modular framework that facilitates publishing software updates
     Group:          Applications/Internet
     URL:            https://github.com/fedora-infra/bodhi
    -Source0:        %{url}/archive/%{version}/%{name}-%{version}.tar.gz
    +Source0:        %{url}/archive/%{commit}/%{name}-%{commit}.tar.gz
    +Patch0:         0000-Set-the-version-to-beta-0.patch
     
     BuildRequires: %{py2_dist click}
     BuildRequires: %{py2_dist iniparse}
    @@ -241,7 +248,7 @@ updates for a software distribution.
     
     
     %prep
    -%autosetup -p1 -n bodhi-%{version}
    +%autosetup -p1 -n bodhi-%{commit}
     
     # Kill some dev deps
     sed -i '/pyramid_debugtoolbar/d' setup.py
    @@ -270,7 +277,7 @@ make %{?_smp_mflags} -C docs man
     %install
     %py2_install
     # Let's remove all the server stuff since we don't ship Python 2 version of the server anymore.
    -rm -rf %{buildroot}/%{python2_sitelib}/%{name}_server-%{version}-py%{python2_version}.egg-info
    +rm -rf %{buildroot}/%{python2_sitelib}/%{name}_server-%{version}b0-py%{python2_version}.egg-info
     rm -rf %{buildroot}/%{python2_sitelib}/%{name}/server
     %py3_install
     
    @@ -346,7 +353,7 @@ rm .coveragerc
     %doc README.rst
     %dir %{python2_sitelib}/%{name}/
     %{python2_sitelib}/%{name}/__init__.py*
    -%{python2_sitelib}/%{name}-%{version}-py%{python2_version}.egg-info
    +%{python2_sitelib}/%{name}-%{version}b0-py%{python2_version}.egg-info
     
     
     %files -n python3-bodhi
    @@ -355,21 +362,21 @@ rm .coveragerc
     %dir %{python3_sitelib}/%{name}/
     %{python3_sitelib}/%{name}/__init__.py
     %{python3_sitelib}/%{name}/__pycache__
    -%{python3_sitelib}/%{name}-%{version}-py%{python3_version}.egg-info
    +%{python3_sitelib}/%{name}-%{version}b0-py%{python3_version}.egg-info
     
     
     %files -n python2-bodhi-client
     %license COPYING
     %doc README.rst
     %{python2_sitelib}/%{name}/client
    -%{python2_sitelib}/%{name}_client-%{version}-py%{python2_version}.egg-info
    +%{python2_sitelib}/%{name}_client-%{version}b0-py%{python2_version}.egg-info
     
     
     %files -n python3-bodhi-client
     %license COPYING
     %doc README.rst
     %{python3_sitelib}/%{name}/client
    -%{python3_sitelib}/%{name}_client-%{version}-py%{python3_version}.egg-info
    +%{python3_sitelib}/%{name}_client-%{version}b0-py%{python3_version}.egg-info
     
     
     %files server
    @@ -392,7 +400,7 @@ rm .coveragerc
     %config(noreplace) %{_sysconfdir}/fedmsg.d/*
     %dir %{_sysconfdir}/bodhi/
     %{python3_sitelib}/%{name}/server
    -%{python3_sitelib}/%{name}_server-%{version}-py%{python3_version}.egg-info
    +%{python3_sitelib}/%{name}_server-%{version}b0-py%{python3_version}.egg-info
     %{_mandir}/man1/bodhi-*.1*
     %{_mandir}/man1/initialize_bodhi_db.1*
     %attr(-,bodhi,root) %{_datadir}/%{name}
    @@ -406,6 +414,10 @@ rm .coveragerc
     
     
     %changelog
    +* Fri Jan 11 2019 Randy Barlow <bowlofeggs@fedoraproject.org> - 3.13.0-0.0.beta.e0ca5bc
    +- Update to 3.13.0.
    +- https://github.com/fedora-infra/bodhi/releases/tag/3.13.0
    +
     * Mon Dec 17 2018 Randy Barlow <bowlofeggs@fedoraproject.org> - 3.12.0-100
     - Upgrade to 3.12.0.
     - https://github.com/fedora-infra/bodhi/releases/tag/3.12.0
    $ cat 0000-Set-the-version-to-beta-0.patch 
    From 77f54fee023fcbfb06f7e72b3b993d39f7678efa Mon Sep 17 00:00:00 2001
    From: Randy Barlow <randy@electronsweatshop.com>
    Date: Fri, 11 Jan 2019 09:19:47 -0500
    Subject: [PATCH] Set the version to beta 0.
 
    Signed-off-by: Randy Barlow <randy@electronsweatshop.com>
    ---
     docs/conf.py | 2 +-
     setup.py     | 2 +-
     2 files changed, 2 insertions(+), 2 deletions(-)
 
    diff --git a/docs/conf.py b/docs/conf.py
    index 59edc0a8..1ba87387 100644
    --- a/docs/conf.py
    +++ b/docs/conf.py
    @@ -63,7 +63,7 @@ copyright = u'2007-{}, Red Hat, Inc.'.format(datetime.datetime.utcnow().year)
     # The short X.Y version.
     version = '3.13'
     # The full version, including alpha/beta/rc tags.
    -release = '3.13.0'
    +release = '3.13.0b0'
     
     # The language for content autogenerated by Sphinx. Refer to documentation
     # for a list of supported languages.
    diff --git a/setup.py b/setup.py
    index 44566ff5..74297bb5 100644
    --- a/setup.py
    +++ b/setup.py
    @@ -42,7 +42,7 @@ def get_requirements(requirements_file='requirements.txt'):
     
     here = os.path.abspath(os.path.dirname(__file__))
     README = open(os.path.join(here, 'README.rst')).read()
    -VERSION = '3.13.0'
    +VERSION = '3.13.0b0'
     # Possible options are at https://pypi.python.org/pypi?%3Aaction=list_classifiers
     CLASSIFIERS = [
 	'Development Status :: 5 - Production/Stable',
    -- 
    2.20.1

#. Perform any other spec file alterations that might be needed for this release (such as adding or
   removing dependencies).
#. Build the beta for Fedora Infrastructure's staging repository. At the time of writing, Bodhi runs
   on Fedora 29, so here's an example of building for the f29-infra-stg repository::

    $ rpmbuild --define "dist .fc29.infra" -bs bodhi.spec 
    Wrote: /home/bowlofeggs/rpmbuild/SRPMS/bodhi-3.13.0-0.0.beta.e0ca5bc.fc29.src.rpm
    $ koji build f29-infra /home/bowlofeggs/rpmbuild/SRPMS/bodhi-3.13.0-0.0.beta.e0ca5bc.fc29.src.rpm

#. Build the beta for bowlofegg's bodhi-pre-release Copr repository::

   $ copr build bowlofeggs/bodhi-pre-release /home/bowlofeggs/rpmbuild/SRPMS/bodhi-3.13.0-0.0.beta.e0ca5bc.fc29.src.rpm

#. It's a good idea to also do a scratch build against Fedora Rawhide just to make sure things build
   there::

   $ koji build --scratch rawhide /home/bowlofeggs/rpmbuild/SRPMS/bodhi-3.13.0-0.0.beta.e0ca5bc.fc29.src.rpm


Deploy the beta to staging
--------------------------

To deploy to beta to staging, read the `Fedora Infrastructure Bodhi SOP`_.

Notify people that the beta has been deployed so they can test and provide feedback.
You can notify the tickets that are referenced in the release notes, Fedora IRC channels (
``#bodhi``, ``#fedora-admin``, ``#fedora-apps``, ``#fedora-devel``, ``#fedora-releng``, and
``#fedora-qa``), and the Fedora infrastructure mailing list.


Test the beta
-------------

Testing beta builds in staging can be a bit tricky. One problem you may encounter is that the
staging Koji instance doesn't have all the data from production, and its database most likely wasn't
synchronized with production data at the same time that Bodhi's database was. The latter means that
Bodhi may reference some data that isn't in the staging Koji database. To overcome this problem,
I've found it to be best to make a fresh build of a package in the staging Koji database so I can be
sure that Koji has the RPM and that Bodhi can be synchronized with Koji about the resulting update.

I personally update with a small package that I have ACLs on called `python-rpdb`_. I usually just
bump the release on it and make another build, being careful to do this in the staging git
repository and not production. Then I make an update in staging Bodhi with that build and do my
testing from there. I don't do extremely extensive testing, since that is what our unit and
integration tests are for.

One test I recommend, however, is to run a compose with the newly minted update. At the time of this
writing, our integration test suite does not test integration with Koji or Pungi, and this is a
critical function of Bodhi. To do this, you will need to mark the build as being signed using
``bodhi-shell`` because we don't sign builds in staging. Then run ``bodhi-push`` on
``bodhi-backend01.stg.fedoraproject.org``. As an example, if I had built a test update for
``python-rpdb-2.3-3.fc29`` and I wanted to sign and then compose it, I would run this::

   $ sudo -u apache bodhi-shell
   >>> b = m.Build.query.filter_by(nvr='python-rpdb-2.3-3.fc29').one()
   >>> b.signed = True
   >>> m.Session().commit()
   $ sudo -u apache bodhi-push --builds python-rpdb-2.3-3.fc29

.. note:: We limit to just the build we built for testing here, because a full compose will fail due
          to the issues described earlier between staging and production Koji.

.. note:: If there are existing composes in the database due to the production to staging database
          sync, you will not be able to create a new compose as described above. ``bodhi-push`` will
          force you to resume the existing composes. Unfortunately, they will also fail due to
          referencing builds from production Koji that are not in the staging Koji. You will need to
          use ``bodhi-shell`` to clear our these composes::

             $ sudo -u apache bodhi-shell
             >>> for u in m.Update.query.filter_by(locked=True):
             ...     u.locked = False
             ...
             >>> m.Session().commit()

          Now you should be able to resume the composes, and bodhi-push will see that there's
          nothing to do in any of them and will remove them.

Of course, if you find issues during testing you should fix those issues upstream and produce a new
beta and test again.


Release Bodhi upstream
----------------------

Once you are satisfied with the quality of the beta and the beta has been in staging for a while (a
week is typical) to give people time to test and provide feedback, it is time to make a release.

We start by checking out the branch we want to make a release on, and we use ``git tag`` to create a
tag. Be sure to use the -s flag to sign the commit with your GPG key::

   $ git tag -s 3.13.0

Your ``$EDITOR`` will be opened for you to write the release notes into the tag. You can copy the
release notes into there, and I typically change the format from RST to markdown for this because
it's a little easier to read in plain text, and we will also paste the release notes into GitHub in
a bit and it'll be useful to have a markdown version anyway. You don't need to use markdown if you
prefer not to, it's just a suggestion.

.. note:: If you do use markdown in the git tag notes, don't use the ``#`` character to specify
          headings because git will interpret those lines as comments.

Push the tag up to GitHub::

   $ git push origin --tags

Now go to the releases page in GitHub, click the tags submenu, find the tag you just made, click the
"..."'s next to it, and choose "Create release". I usually just make the title along the lines of
"Bodhi 3.13.0 released". It'd be nice if GitHub used the tag message you just wrote in git, but it
does not. Fortunately, you might have just formatting it with markdown anyway and can copy and paste
it into the GitHub release notes::

   $ git show 3.13.0

The next step is to release Bodhi to PyPI. To do this, we will make a source build::

   $ python3 setup.py sdist

This will drop source tarballs into the ``dist/`` folder for the various bodhi packages. Now you can
use ``twine`` to sign the builds and upload them to PyPI, substituting your GPG key ID where mine is
below::

   $ twine upload -s -i 3BDD2462 dist/*


Release Bodhi downstream
------------------------

Next it is time to release Bodhi downstream. Don't forget to remove the patch you made earlier to
set its version to a beta, and all the code that used commit hashes instead of versions.

#. Build the release for all targeted Fedora versions.

   .. note:: Be sure to consider whether the version you are releasing would be backwards
             incompatible for the various stable releases of Bodhi. Major releases should only go to
             Rawhide.

#. Build the release for bowlofegg's bodhi Copr repository::

   $ copr build bowlofeggs/bodhi /home/bowlofeggs/rpmbuild/SRPMS/bodhi-3.13.0-1.fc29.src.rpm


Deploy the beta to staging and production
-----------------------------------------

As before, read the `Fedora Infrastructure Bodhi SOP`_ for details on how we deploy Bodhi in
Fedora Infrastructure.

It is wise to deploy the real release to staging as a sanity check before deploying to production.


Notifications
-------------

Notify people that the release and deployment are done. You can notify the tickets that are
referenced in the release notes, Fedora IRC channels (``#bodhi``, ``#fedora-admin``,
``#fedora-apps``, ``#fedora-devel``, ``#fedora-releng``, and ``#fedora-qa``), and the Fedora
infrastructure mailing list.


.. _semantic versioning: https://semver.org
.. _Mergify: https://mergify.io
.. _patch backporting feature: https://doc.mergify.io/actions.html#backport
.. _Fedora Rawhide spec file: https://src.fedoraproject.org/rpms/bodhi/blob/master/f/bodhi.spec
.. _Fedora Infrastructure repositories: https://fedora-infra-docs.readthedocs.io/en/latest/sysadmin-guide/sops/infra-repo.html
.. _Fedora's staging instance: https://bodhi.stg.fedoraproject.org
.. _Fedora Infrastructure Bodhi SOP: https://fedora-infra-docs.readthedocs.io/en/latest/sysadmin-guide/sops/bodhi.html#performing-a-bodhi-upgrade
.. _python-rpdb: https://src.stg.fedoraproject.org/rpms/python-rpdb
.. _backwards incompatible: https://www.theonion.com/craftsman-confirms-new-hammer-backwards-compatible-with-1834722479
