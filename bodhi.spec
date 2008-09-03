%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%{!?pyver: %define pyver %(%{__python} -c "import sys ; print sys.version[:3]")}

Name:           bodhi
Version:        0.5.2
Release:        1%{?dist}
Summary:        A modular framework that facilitates publishing software updates
Group:          Applications/Internet
License:        GPLv2+
URL:            https://fedorahosted.org/bodhi
Source0:        bodhi-%{version}.tar.bz2

BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch:      noarch

BuildRequires: python-setuptools-devel
BuildRequires: python-devel
BuildRequires: TurboGears

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
Requires: python-simplejson python-fedora koji yum

%description client
Client tools for interacting with bodhi


%package server
Summary: A modular framework that facilitates publishing software updates
Group: Applications/Internet
Requires: TurboGears
Requires: python-TurboMail
Requires: intltool
Requires: mash
Requires: cvs
Requires: koji
Requires: python-fedora
Requires: python-bugzilla
Requires: python-imaging
Requires: python-crypto
Requires: python-turboflot
Requires: python-tgcaptcha
Requires: python-decorator
Requires: mod_wsgi


%description server
Bodhi is a modular framework that facilitates the process of publishing
updates for a software distribution.

%prep
%setup -q
rm -rf bodhi/tests bodhi/tools/test-bodhi.py

%build
%{__python} setup.py build --install-data=%{_datadir}

%install
%{__rm} -rf %{buildroot}
%{__python} setup.py install -O1 --skip-build \
    --install-data=%{_datadir} --root %{buildroot}

%{__mkdir_p} %{buildroot}/var/lib/bodhi
%{__mkdir_p} %{buildroot}%{_sysconfdir}/httpd/conf.d
%{__mkdir_p} %{buildroot}%{_sysconfdir}/bodhi
%{__mkdir_p} %{buildroot}%{_datadir}/%{name}
%{__mkdir_p} -m 0755 %{buildroot}/%{_localstatedir}/log/bodhi

%{__install} -m 640 apache/%{name}.conf %{buildroot}%{_sysconfdir}/httpd/conf.d/%{name}.conf
%{__install} -m 640 %{name}.cfg %{buildroot}%{_sysconfdir}/%{name}/
%{__install} -m 640 %{name}/config/*mash* %{buildroot}%{_sysconfdir}/%{name}/
%{__install} apache/%{name}.wsgi %{buildroot}%{_datadir}/%{name}/%{name}.wsgi

%{__install} %{name}/tools/client.py %{buildroot}%{_bindir}/%{name}


%clean
%{__rm} -rf %{buildroot}


%files server
%defattr(-,root,root,-)
%doc README COPYING
%{python_sitelib}/%{name}/
%{_bindir}/start-%{name}
%{_bindir}/%{name}-*
%{_sysconfdir}/httpd/conf.d/bodhi.conf
%attr(-,apache,root) %{_datadir}/%{name}
%attr(-,apache,root) %config(noreplace) %{_sysconfdir}/bodhi/*
%attr(-,apache,root) %{_localstatedir}/log/bodhi
%{python_sitelib}/%{name}-%{version}-py%{pyver}.egg-info/


%files client
%{_bindir}/bodhi
%{_mandir}/man1/bodhi.1.gz


%changelog
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
