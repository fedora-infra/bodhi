%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%{!?pyver: %global pyver %(%{__python} -c "import sys ; print sys.version[:3]")}

Name:           bodhi
Version:        2.0
Release:        4%{?dist}
Summary:        A modular framework that facilitates publishing software updates
Group:          Applications/Internet
License:        GPLv2+
URL:            https://fedorahosted.org/bodhi
Source0:        https://fedorahosted.org/releases/b/o/bodhi/bodhi-%{version}.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch:      noarch
ExcludeArch:    ppc64 ppc

# For the tests
BuildRequires:   python2
BuildRequires:   python-nose
#BuildRequires:   python-nose-cov
BuildRequires:   python-webtest
BuildRequires:   python-mock

# For the app
BuildRequires:   python-pyramid
BuildRequires:   python-pyramid-mako
#BuildRequires:   python-pyramid-debugtoolbar
BuildRequires:   python-pyramid-tm
BuildRequires:   python-waitress
BuildRequires:   python-colander
BuildRequires:   python-cornice

BuildRequires:   python-openid
BuildRequires:   python-pyramid-fas-openid
BuildRequires:   packagedb-cli

BuildRequires:   python-sqlalchemy
BuildRequires:   python-zope-sqlalchemy

BuildRequires:   python-webhelpers
BuildRequires:   python-progressbar
BuildRequires:   python-bunch

# for captchas
BuildRequires:   python-cryptography
BuildRequires:   python-pillow
BuildRequires:   liberation-mono-fonts
#BuildRequires:   pcaro-hermit-fonts

# Useful tools
BuildRequires:   python-kitchen
BuildRequires:   python-fedora
BuildRequires:   python-pylibravatar
BuildRequires:   python-pydns
BuildRequires:   python-dogpile-cache
BuildRequires:   python-arrow
BuildRequires:   python-markdown
BuildRequires:   python-librepo
BuildRequires:   python-createrepo_c
BuildRequires:   createrepo_c

## i18n, stuff that we're not actually doing yet
#BuildRequires:   python-babel
#BuildRequires:   python-lingua

# External resources
BuildRequires:   python-bugzilla
BuildRequires:   python-simplemediawiki
BuildRequires:   fedmsg

BuildRequires:   python-sphinx

# For the bodhi-client
BuildRequires:   python-click

%if 0%{?rhel} >= 7
BuildRequires:   python-webob1.4
Requires:        python-webob1.4
%endif

Requires:       python-psycopg2
Requires:       python2

%description
Bodhi is a web application that facilitates the process of publishing
updates for a software distribution.

A modular piece of the Fedora Infrastructure stack
* Utilizes the Koji Buildsystem for tracking RPMs
* Creates the update repositories using Mash, which composes a repository based
  on tagged builds in Koji.


%package client
Summary: Bodhi Client
Group: Applications/Internet
Requires: koji yum
Requires: python-fedora >= 0.3.5
Requires: python-kitchen
Requires: python-click

%description client
Client tools for interacting with bodhi

%package server
Summary: A modular framework that facilitates publishing software updates
Group: Applications/Internet

Requires:   mod_wsgi
Requires:   httpd
Requires:   python-psycopg2

Requires:   python-pyramid
Requires:   python-pyramid-mako
#Requires:   python-pyramid-debugtoolbar
Requires:   python-pyramid-tm
Requires:   python-waitress
Requires:   python-colander
Requires:   python-cornice

Requires:   python-openid
Requires:   python-pyramid-fas-openid
Requires:   packagedb-cli

Requires:   python-sqlalchemy
Requires:   python-zope-sqlalchemy

Requires:   python-webhelpers
Requires:   python-progressbar
Requires:   python-bunch

# for captchas
Requires:   python-cryptography
Requires:   python-pillow
Requires:   liberation-mono-fonts
#Requires:   pcaro-hermit-fonts

# Useful tools
Requires:   python-kitchen
Requires:   python-fedora
Requires:   python-pylibravatar
Requires:   python-pydns
Requires:   python-dogpile-cache
Requires:   python-arrow
Requires:   python-markdown
Requires:   python-librepo
Requires:   python-createrepo_c
Requires:   createrepo_c

## i18n, that we're not actually doing yet
#Requires:   python-babel
#Requires:   python-lingua

# External resources
Requires:   python-bugzilla
Requires:   python-simplemediawiki
Requires:   fedmsg

# For cloning comps
Requires:  git
Requires:  libxml2-python
Requires:  intltool

Requires:  mash

Requires:   python-sphinx


%description server
Bodhi is a modular framework that facilitates the process of publishing
updates for a software distribution.

%prep
%setup -q

# Kill some dev deps
sed -i '/pyramid_debugtoolbar/d' setup.py
sed -i '/pyramid_debugtoolbar/d' development.ini
sed -i '/nose-cov/d' setup.py

# Kill this from the egg-info deps so that bodhi-server doesn't demand it.
sed -i '/click/d' setup.py

%build
%{__python} setup.py build #--install-data=%{_datadir}

%install
%{__rm} -rf %{buildroot}
%{__python} setup.py install --skip-build \
    --root %{buildroot} \
    #--install-data=%{_datadir}

%{__mkdir_p} %{buildroot}/var/lib/bodhi
%{__mkdir_p} %{buildroot}/var/cache/bodhi
%{__mkdir_p} %{buildroot}%{_sysconfdir}/httpd/conf.d
%{__mkdir_p} %{buildroot}%{_sysconfdir}/fedmsg.d
%{__mkdir_p} %{buildroot}%{_sysconfdir}/bodhi
%{__mkdir_p} %{buildroot}%{_datadir}/%{name}
%{__mkdir_p} -m 0755 %{buildroot}/%{_localstatedir}/log/bodhi

%{__install} -m 644 apache/%{name}.conf %{buildroot}%{_sysconfdir}/httpd/conf.d/%{name}.conf
%{__install} -m 640 production.ini %{buildroot}%{_sysconfdir}/%{name}/production.ini
%{__install} -m 640 alembic.ini %{buildroot}%{_datadir}/%{name}/alembic.ini
cp -rf alembic/ %{buildroot}%{_datadir}/%{name}/alembic
%{__install} apache/%{name}.wsgi %{buildroot}%{_datadir}/%{name}/%{name}.wsgi

%{__install} -m 644 fedmsg.d/masher.py %{buildroot}%{_sysconfdir}/fedmsg.d/masher.py
%{__install} -m 644 fedmsg.d/bodhi.py %{buildroot}%{_sysconfdir}/fedmsg.d/bodhi.py

# We used to copy in things like this for bodhi1
#%{__install} -m 640 %{name}/config/*mash* %{buildroot}%{_sysconfdir}/%{name}/

%check
PYTHONPATH=. %{__python} setup.py test

%pre server
%{_sbindir}/groupadd -r %{name} &>/dev/null || :
%{_sbindir}/useradd  -r -s /sbin/nologin -d %{_datadir}/%{name} -M \
                     -c 'Bodhi Server' -g %{name} %{name} &>/dev/null || :

%files server
%defattr(-,root,root,-)
%doc README.rst CHANGES.txt
%license COPYING
%{python_sitelib}/%{name}/
%{_bindir}/initialize_bodhi_db
%{_bindir}/bodhi-expire-overrides
%{_bindir}/bodhi-approve-testing
%{_bindir}/bodhi-push
%{_bindir}/bodhi-untag-branched
%{_bindir}/bodhi-manage-releases
%config(noreplace) %{_sysconfdir}/httpd/conf.d/bodhi.conf
%config(noreplace) %{_sysconfdir}/fedmsg.d/*
%dir %{_sysconfdir}/bodhi/
%attr(-,bodhi,root) %{_datadir}/%{name}
%attr(-,bodhi,bodhi) %config(noreplace) %{_sysconfdir}/bodhi/*
%attr(-,bodhi,root) %{_localstatedir}/log/bodhi
%attr(0775,bodhi,bodhi) %{_localstatedir}/cache/bodhi
%{python_sitelib}/%{name}-%{version}-py%{pyver}.egg-info/


%files client
%defattr(-,root,root,-)
%doc README.rst CHANGES.txt
%license COPYING
%{_bindir}/bodhi
# TODO .. get the man page back with help2man or something
#%{_mandir}/man1/bodhi.1.gz


%changelog
* Tue Apr 14 2015 Ralph Bean <rbean@redhat.com> - 2.0-1
- First draft at a spec file for the bodhi2 rewrite.

* Tue Sep 02 2014 Luke Macken <lmacken@redhat.com> - 0.9.12.2-1
- Updated to 0.9.12.2

* Fri Aug 29 2014 Luke Macken <lmacken@redhat.com> - 0.9.11-1
- Updated to 0.9.11 for EPEL-7

* Tue Jun 24 2014 Luke Macken <lmacken@redhat.com> - 0.9.10-1
- Update to 0.9.10
- Add a BR on python-markdown

* Sat Jun 07 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.9.9.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Wed May 14 2014 Luke Macken <lmacken@redhat.com> - 0.9.9.2-1
- Update to 0.9.9.2

* Tue Mar 18 2014 Luke Macken <lmacken@redhat.com> - 0.9.9-2
- Fix the Source URL (#985058)

* Fri Mar 14 2014 Luke Macken <lmacken@redhat.com> - 0.9.9-1
- Update to 0.9.9

* Wed Feb 19 2014 Luke Macken <lmacken@redhat.com> - 0.9.8-2
- Remove the python-simplejson requirement (#1060234)

* Tue Feb 11 2014 Luke Macken <lmacken@redhat.com> - 0.9.8-1
- Update to 0.9.8

* Fri Dec 06 2013 Pierre-Yves Chibon <pingou@pingoured>fr - 0.9.7-2
- Change BR from python-setuptools-devel to python-setuptools
  See https://fedoraproject.org/wiki/Changes/Remove_Python-setuptools-devel

* Tue Sep 10 2013 Luke Macken <lmacken@redhat.com> - 0.9.7-1
- Update to 0.9.7

* Sat Aug 03 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.9.5-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Wed May 29 2013 Luke Macken <lmacken@redhat.com> - 0.9.5-2
- Update the man page

* Mon May 13 2013 Luke Macken <lmacken@redhat.com> - 0.9.5-1
- New bugfix release to work with python-bugzilla 0.8.0

* Fri Feb 22 2013 Luke Macken <lmacken@redhat.com> - 0.9.4-1
- New bugfix release

* Wed Feb 13 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.9.3-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Tue Nov 13 2012 Luke Macken <lmacken@redhat.com> - 0.9.3-1
- 0.9.3 bugfix release

* Wed Aug 08 2012 Luke Macken <lmacken@redhat.com> - 0.9.2-2
- Require python-tgcaptcha2

* Sat Aug 04 2012 Luke Macken <lmacken@redhat.com> - 0.9.2-1
- 0.9.2 bugfix release

* Thu Jul 26 2012 Ralph Bean <rbean@redhat.com> - 0.9.1-3
- "bodhi" now owns datadir, bodhi.cfg, and var/log/bodhi

* Thu Jul 26 2012 Ralph Bean <rbean@redhat.com> - 0.9.1-2
- Fix to "bodhi" user creation.

* Thu Jul 26 2012 Ralph Bean <rbean@redhat.com> - 0.9.1-1
- Creating a 'bodhi' user for mod_wsgi

* Wed Jul 18 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.8.5-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Thu Mar 29 2012 Ralph Bean <rbean@redhat.com> - 0.8.8-1
- Sending messages with fedmsg

* Thu Jan 12 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.8.5-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_17_Mass_Rebuild

* Tue Nov 22 2011 Luke Macken <lmacken@redhat.com> - 0.8.5-1
- Update to the latest upstream release

* Wed Nov 16 2011 Luke Macken <lmacken@redhat.com> - 0.8.4-1
- Update to the latest upstream release

* Mon Oct 24 2011 Luke Macken <lmacken@redhat.com> - 0.8.3-1
- Update to 0.8.3

* Fri Aug 12 2011 Luke Macken <lmacken@redhat.com> - 0.8.1-1
- Update our build requirements to make the test suite happy.
- Pull in the new python-fedora-turbogears subpackage

* Thu Jun 09 2011 Luke Macken <lmacken@redhat.com> - 0.8.0-1
- Update to 0.8.0

* Thu Mar 24 2011 Luke Macken <lmacken@redhat.com> - 0.7.15-1
- Update to 0.7.15

* Fri Mar 11 2011 Luke Macken <lmacken@redhat.com> - 0.7.14-1
- Update to 0.7.14

* Fri Mar 04 2011 Luke Macken <lmacken@redhat.com> - 0.7.13-1
- Update to 0.7.13

* Mon Feb 28 2011 Luke Macken <lmacken@redhat.com> - 0.7.12-1
- Update to 0.7.12

* Thu Feb 24 2011 Luke Macken <lmacken@redhat.com> - 0.7.11-1
- Update to 0.7.11

* Mon Feb 07 2011 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.7.10-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild

* Mon Jan 10 2011 Luke Macken <lmacken@redhat.com> - 0.7.10-1
- 0.7.10 release

* Mon Sep 20 2010 Luke Macken <lmacken@redhat.com> - 0.7.9-1
- 0.7.9 release

* Thu Aug 12 2010 Luke Macken <lmacken@redhat.com> - 0.7.8-1
- 0.7.8 release
- Require python-kitchen

* Wed Aug 04 2010 Orcan Ogetbil <oget[dot]fedora[at]gmail[dot]com> - 0.7.7-2
- Reenable the TurboGears bits

* Tue Aug 03 2010 Luke Macken <lmacken@redhat.com> - 0.7.7-1
- 0.7.7 release

* Sat Jul 31 2010 Toshio Kuratomi <toshio@fedoraproject.org> - 0.7.5-4
- A little strange, the tarball changed on us....

* Tue Jul 27 2010 Toshio Kuratomi <toshio@fedoraproject.org> - 0.7.5-3
- Disable Requirements that are necessary for operation of hte server.  This is
  a temporary change to get the package building on python-2.7.  Need to revert
  this once the TG stack is rebuilt

* Wed Jul 21 2010 David Malcolm <dmalcolm@redhat.com> - 0.7.5-2
- Rebuilt for https://fedoraproject.org/wiki/Features/Python_2.7/MassRebuild

* Tue Jun 29 2010 Luke Macken <lmacken@redhat.com> - 0.7.5-1
- 0.7.5 release

* Thu Mar 04 2010 Luke Macken <lmacken@redhat.com> - 0.7.4-1
- 0.7.4

* Thu Mar 04 2010 Luke Macken <lmacken@redhat.com> - 0.7.3-1
- 0.7.3

* Wed Mar 03 2010 Luke Macken <lmacken@redhat.com> - 0.7.2-1
- 0.7.2 bugfix release

* Tue Feb 16 2010 Luke Macken <lmacken@redhat.com> - 0.7.1-1
- Fix a regression in our metrics controller, and unvail a new
  metrics JSON API

* Tue Feb 16 2010 Luke Macken <lmacken@redhat.com> - 0.7.0-2
- Add the F13 updates-testing mash configuration

* Mon Jan 18 2010 Luke Macken <lmacken@redhat.com> - 0.7.0-1
- 0.7.0 release, prepping for the F13 release
- Critical Path & No Frozen Rawhide proposals implemented
- Many other bugfixes, enhancements, and optimizations

* Fri Nov 06 2009 Luke Macken <lmacken@redhat.com> - 0.6.12-1
- 0.6.12, for F12

* Sat Sep 19 2009 Luke Macken <lmacken@redhat.com> - 0.6.11-1
- 0.6.11

* Fri Sep 18 2009 Luke Macken <lmacken@redhat.com> - 0.6.10-1
- 0.6.10

* Thu Sep 17 2009 Luke Macken <lmacken@redhat.com> - 0.6.9-2
- More CSRF tweaks

* Thu Sep 17 2009 Luke Macken <lmacken@redhat.com> - 0.6.9-1
- 0.6.9

* Mon Sep 14 2009 Luke Macken <lmacken@redhat.com> - 0.6.8-1
- 0.6.8

* Wed Sep 09 2009 Luke Macken <lmacken@redhat.com> - 0.6.7-1
- 0.6.7

* Wed Sep 09 2009 Luke Macken <lmacken@redhat.com> - 0.6.6-1
- 0.6.6

* Wed Sep 09 2009 Luke Macken <lmacken@redhat.com> - 0.6.5-1
- 0.6.5

* Fri Aug 14 2009 Luke Macken <lmacken@redhat.com> - 0.6.4-1
- 0.6.4

* Thu Aug 13 2009 Luke Macken <lmacken@redhat.com> - 0.6.3-1
- 0.6.3

* Fri Jul 10 2009 Luke Macken <lmacken@redhat.com> - 0.6.2-1
- 0.6.2

* Thu Jul 09 2009 Luke Macken <lmacken@redhat.com> - 0.6.1-1
- 0.6.1

* Thu Jul 09 2009 Luke Macken <lmacken@redhat.com> - 0.6.0-1
- 0.6.0 final

* Mon Jul 06 2009 Luke Macken <lmacken@redhat.com> - 0.6.0-0.7.beta
- beta7

* Mon Jul 06 2009 Luke Macken <lmacken@redhat.com> - 0.6.0-0.6.beta
- beta6

* Mon Jul 06 2009 Luke Macken <lmacken@redhat.com> - 0.6.0-0.5.beta
- beta5, with EPEL mash configs

* Fri Jul 03 2009 Luke Macken <lmacken@redhat.com> - 0.6.0-0.4.beta
- beta4

* Fri Jul 03 2009 Luke Macken <lmacken@redhat.com> - 0.6.0-0.3.beta
- beta3

* Fri Jul 03 2009 Luke Macken <lmacken@redhat.com> - 0.6.0-0.2.beta
- beta2
- Make our Bugzilla cookie file configurable

* Thu Jul 02 2009 Luke Macken <lmacken@redhat.com> - 0.6.0-0.1.beta
- 0.6.0 beta

* Mon Jun 22 2009 Luke Macken <lmacken@redhat.com> - 0.5.27-01
- Latest upstream release to bring in fixed mash config files.

* Fri Jun 12 2009 Luke Macken <lmacken@redhat.com> - 0.5.26-1
- Latest upstream release with a variety of fixes and pkgdb-0.4 support.

* Tue May 12 2009 Luke Macken <lmacken@redhat.com> - 0.5.25-1
- Latest upstream bugfix release to work around some TG 1.0.8
  brokenness, and make our masher a bit more robust.

* Tue May 12 2009 Luke Macken <lmacken@redhat.com> - 0.5.24-1
- 0.5.24 bugfix release

* Thu May 07 2009 Luke Macken <lmacken@redhat.com> - 0.5.23-1
- Add mash configs for F11, with deltarpm support.

* Thu Apr 30 2009 Luke Macken <lmacken@redhat.com> - 0.5.22-1
- Remove pagination patch, as Fedora Infrastructure is now TG 1.0.8

* Thu Apr 30 2009 Luke Macken <lmacken@redhat.com> - 0.5.21-1
- Update to TG 1.0.8 API (fixes a @paginate issue)

* Mon Apr 06 2009 Luke Macken <lmacken@redhat.com> - 0.5.20-1
- Fix a bug when sending mash requests through the ProxyClient
- More Python2.4 workarounds

* Mon Apr 06 2009 Luke Macken <lmacken@redhat.com> - 0.5.19-3
- Update to work with Python2.4

* Mon Apr 06 2009 Luke Macken <lmacken@redhat.com> - 0.5.19-2
- Revision bump to bring it up to speed with the fedora infra package

* Sat Mar 21 2009 Luke Macken <lmacken@redhat.com> - 0.5.19-1
- 0.5.19
- Add a patch to get pagination working in TG 1.0.4.4

* Sat Mar 14 2009 Luke Macken <lmacken@redhat.com> - 0.5.17-4
- Require httpd

* Mon Feb 23 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.5.17-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_11_Mass_Rebuild

* Tue Feb 10 2009 Luke Macken <lmacken@redhat.com> - 0.5.18-1
- Bugfix release, and to stop using deprecated python-fedora APIs.

* Mon Feb 2 2009 Toshio Kuratomi <toshio@fedoraproject.org> - 0.5.17-2
- Own the %%{_sysconfdir}/bodhi directory.

* Thu Jan 22 2009 Luke Macken <lmacken@redhat.com> - 0.5.17-1
- Latest upstream bugfix release.

* Mon Jan 05 2009 Luke Macken <lmacken@redhat.com> - 0.5.16-1
- Latest upstream bugfix release.

* Mon Dec 22 2008 Luke Macken <lmacken@redhat.com> - 0.5.15-1
- Latest release, with more masher improvements.

* Fri Dec 19 2008 Luke Macken <lmacken@redhat.com> - 0.5.14-1
- Latest upstream release, containing some masher improvements.

* Wed Dec 10 2008 Luke Macken <lmacken@redhat.com> - 0.5.13-1
- Latest upstream release to fix various metrics/rss issues

* Mon Nov 24 2008 Luke Macken <lmacken@redhat.com> - 0.5.12-1
- Latest upstream release, to fix the 10k bug

* Fri Nov 21 2008 Luke Macken <lmacken@redhat.com> - 0.5.11-1
- Various F10 release tweaks

* Fri Oct 24 2008 Luke Macken <lmacken@redhat.com> - 0.5.10-3
- Latest upstream release

* Wed Oct 15 2008 Luke Macken <lmacken@redhat.com> - 0.5.9-2
- Fix a trivial module import issue

* Tue Oct 14 2008 Luke Macken <lmacken@redhat.com> - 0.5.9-1
- Fix a variety of bugs, including a race-condition when editing.

* Thu Oct 13 2008 Steve 'Ashcrow' Milner <smilner@redhat.com> - 0.5.8-2
- Added default attributes to client files.

* Sun Oct 12 2008 Luke Macken <lmacken@redhat.com> - 0.5.8-1
- Minor release to fix some new update creation bugs

* Thu Oct 09 2008 Luke Macken <lmacken@redhat.com> - 0.5.7-1
- Latest release, containing some API improvements

* Tue Oct 07 2008 Luke Macken <lmacken@redhat.com> - 0.5.6-1
- Latest upstream release.

* Mon Oct 06 2008 Luke Macken <lmacken@redhat.com> - 0.5.5-1
- Latest upstream release.

* Sat Oct 04 2008 Luke Macken <lmacken@redhat.com> - 0.5.4-2
- Make our masher extension point less obtrusive.

* Tue Sep 16 2008 Luke Macken <lmacken@redhat.com> - 0.5.4-1
- Latest upstream release, containing various bugfixes
- Make our python-fedora requirement explicit (#461518)

* Wed Sep 10 2008 Luke Macken <lmacken@redhat.com> - 0.5.3-1
- Latest upstream release

* Wed Sep 03 2008 Luke Macken <lmacken@redhat.com> - 0.5.2-2
- Add the masher deps to BuildRequires, since it now resides
  on the turbogears.extensions entry point and will be
  imported by pkg_resources at build time.

* Wed Sep 03 2008 Luke Macken <lmacken@redhat.com> - 0.5.2-1
- Latest upstream bugfix release

* Fri Aug 29 2008 Luke Macken <lmacken@redhat.com> - 0.5.1-3
- Fix some setuptools issues with our client subpackage

* Mon Aug 25 2008 Luke Macken <lmacken@redhat.com> - 0.5.1-2
- Include the egg-info in the client subpackage.

* Fri Aug 22 2008 Luke Macken <lmacken@redhat.com> - 0.5.1-1
- Latest upstream release

* Sun Jul 06 2008 Luke Macken <lmacken@redhat.com> - 0.5.0-1
- Latest upstream release

* Thu Jun 12 2008 Todd Zullinger <tmz@pobox.com> - 0.4.10-5
- update URL to point to fedorahosted.org

* Fri Apr 04 2008 Luke Macken <lmacken@redhat.com> - 0.4.10-4
- Add python-tgcaptcha to our server requirements

* Tue Feb 26 2008 Luke Macken <lmacken@redhat.com> - 0.4.10-3
- Add python-bugzilla to our server requirements

* Fri Jan 25 2008 Luke Macken <lmacken@redhat.com> - 0.4.10-2
- Add python-elixir to BuildRequires to make the new TG happy

* Fri Jan 25 2008 Luke Macken <lmacken@redhat.com> - 0.4.10-1
- 0.4.10
- Remove yum-utils requirement from bodhi-server

* Sun Jan  6 2008 Luke Macken <lmacken@redhat.com> - 0.4.9-1
- 0.4.9

* Sat Dec  7 2007 Luke Macken <lmacken@redhat.com> - 0.4.8-1
- 0.4.8

* Wed Nov 28 2007 Luke Macken <lmacken@redhat.com> - 0.4.7-1
- 0.4.7

* Tue Nov 20 2007 Luke Macken <lmacken@redhat.com> - 0.4.6-1
- 0.4.6

* Sun Nov 18 2007 Luke Macken <lmacken@redhat.com> - 0.4.5-2
- Add python-genshi to BuildRequires

* Sat Nov 17 2007 Luke Macken <lmacken@redhat.com> - 0.4.5-1
- 0.4.5

* Wed Nov 14 2007 Luke Macken <lmacken@redhat.com> - 0.4.4-1
- 0.4.4

* Mon Nov 12 2007 Luke Macken <lmacken@redhat.com> - 0.4.3-1
- 0.4.3

* Mon Nov 12 2007 Luke Macken <lmacken@redhat.com> - 0.4.2-1
- 0.4.2

* Mon Nov 12 2007 Luke Macken <lmacken@redhat.com> - 0.4.1-1
- 0.4.1

* Sun Nov 11 2007 Luke Macken <lmacken@redhat.com> - 0.4.0-1
- Lots of bodhi-client features

* Wed Nov  7 2007 Luke Macken <lmacken@redhat.com> - 0.3.3-1
- 0.3.3

* Thu Oct 18 2007 Luke Macken <lmacken@redhat.com> - 0.3.2-2
- Add TurboGears to BuildRequires
- Make some scripts executable to silence rpmlint

* Sat Oct 16 2007 Luke Macken <lmacken@redhat.com> - 0.3.2-1
- 0.3.2
- Add COPYING file
- s/python-json/python-simplejson/

* Sat Oct  6 2007 Luke Macken <lmacken@redhat.com> - 0.3.1-1
- 0.3.1

* Wed Oct  3 2007 Luke Macken <lmacken@redhat.com> - 0.2.0-5
- Add python-fedora to bodhi-client Requires

* Mon Sep 17 2007 Luke Macken <lmacken@redhat.com> - 0.2.0-4
- Add python-json to bodhi-client Requires

* Sun Sep 16 2007 Luke Macken <lmacken@redhat.com> - 0.2.0-3
- Add cvs to bodhi-server Requires

* Thu Sep 15 2007 Luke Macken <lmacken@redhat.com> - 0.2.0-2
- Handle python-setuptools-devel changes in Fedora 8
- Update license to GPLv2+

* Thu Sep 13 2007 Luke Macken <lmacken@redhat.com> - 0.2.0-1
- Split spec file into client/server subpackages
