%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%{!?pyver: %define pyver %(%{__python} -c "import sys ; print sys.version[:3]")}

Name:           bodhi
Version:        1.0
Release:        2%{?dist}
Summary:        TODO

Group:          Applications/Internet
License:        GPL
URL:            https://hosted.fedoraproject.org/projects/bodhi
Source0:        bodhi-%{version}.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch:      noarch

BuildRequires:  python-setuptools
Requires:       TurboGears createrepo python-TurboMail tree yum-utils

%description
TODO.

%prep
%setup -q


%build
%{__python} setup.py build


%install
rm -rf $RPM_BUILD_ROOT
%{__python} setup.py install -O1 --skip-build --root $RPM_BUILD_ROOT


%clean
rm -rf $RPM_BUILD_ROOT


%files
%defattr(-,root,root,-)
%doc README
%{_bindir}/start-updatessystem.py*
%{python_sitelib}/%{name}
%{python_sitelib}/%{name}-%{version}-py%{pyver}.egg-info


%changelog
* Fri Jan 19 2007 Luke Macken <lmacken@redhat.com> - 1.0-2
- Rename project to bodhi

* Fri Dec 29 2006 Luke Macken <lmacken@redhat.com> - 1.0-1
- Initial creation
