%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%{!?pyver: %define pyver %(%{__python} -c "import sys ; print sys.version[:3]")}

Name:           bodhi
Version:        0.4.6
Release:        1%{?dist}
Summary:        A modular framework that facilitates publishing software updates
Group:          Applications/Internet
License:        GPLv2+
URL:            https://hosted.fedoraproject.org/projects/bodhi
Source0:        bodhi-%{version}.tar.bz2
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch:      noarch

BuildRequires: python-setuptools-devel TurboGears python-genshi

%description
Bodhi is a modular framework that facilitates the process of publishing
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
Requires: TurboGears createrepo python-TurboMail intltool mash cvs python-fedora
# We need the --repofrompath option from yum-utils
Requires: yum-utils >= 1.1.7

%description server
Bodhi is a modular framework that facilitates the process of publishing
updates for a software distribution.

%prep
%setup -q
rm -rf bodhi/tests bodhi/tools/test-bodhi.py

%build
%{__python} setup.py build --install-conf=%{_sysconfdir} \
        --install-data=%{_datadir}

%install
rm -rf $RPM_BUILD_ROOT
%{__python} setup.py install --skip-build --install-conf=%{_sysconfdir} \
    --install-data=%{_datadir} --root %{buildroot}
%{__install} -D bodhi/tools/bodhi_client.py $RPM_BUILD_ROOT/usr/bin/bodhi
chmod +x $RPM_BUILD_ROOT/%{_datadir}/%{name}/bodhi/tools/{bodhi_client,init,dev_init,pickledb}.py


%clean
rm -rf $RPM_BUILD_ROOT


%files server
%defattr(-,root,root,-)
%doc README COPYING
%{_datadir}/%{name}
%{_bindir}/start-bodhi
%config(noreplace) %{_sysconfdir}/%{name}.cfg

%files client
%doc COPYING README
%{_bindir}/bodhi


%changelog
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
