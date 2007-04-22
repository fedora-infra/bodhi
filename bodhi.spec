%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%{!?pyver: %define pyver %(%{__python} -c "import sys ; print sys.version[:3]")}

Name:           bodhi
Version:        1.0
Release:        3%{?dist}
Summary:        TODO

Group:          Applications/Internet
License:        GPL
URL:            https://hosted.fedoraproject.org/projects/bodhi
Source0:        bodhi-%{version}.tar.bz2
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch:      noarch

BuildRequires:  python-setuptools
Requires:       TurboGears createrepo python-TurboMail tree yum-utils

%description
Bodhi is a modular web system that facilitates the process of publishing
updates for a software distribution.

%package utils
Summary: Bodhi Utilities
Group: Applications/Internet
Requires: %{name} = %{version}-%{release}

%description utils
Utilities for the Bodhi update system

%prep
%setup -q


%build
make build


%install
rm -rf $RPM_BUILD_ROOT
make DESTDIR=$RPM_BUILD_ROOT install


%clean
rm -rf $RPM_BUILD_ROOT


%files
%defattr(-,root,root,-)
%doc README
%{_bindir}/start-bodhi.py*
%{python_sitelib}/%{name}
%{python_sitelib}/%{name}-%{version}-py%{pyver}.egg-info

%files utils
%{_bindir}/bodhi


%changelog
* Sun Apr 22 2007 Luke Macken <lmacken@redhat.com> - 1.0-3
- Add utils subpackage

* Fri Jan 19 2007 Luke Macken <lmacken@redhat.com> - 1.0-2
- Rename project to bodhi

* Fri Dec 29 2006 Luke Macken <lmacken@redhat.com> - 1.0-1
- Initial creation
