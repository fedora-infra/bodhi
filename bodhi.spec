%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%{!?pyver: %define pyver %(%{__python} -c "import sys ; print sys.version[:3]")}

Name:           fedora-updates-system
Version:        1.0
Release:        1%{?dist}
Summary:        TODO

Group:          Applications/Internet
License:        GPL
URL:            http://fedoraproject.org/wiki/Infrastructure/UpdatesSystem
Source0:        Fedora-Updates-System-%{version}.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch:      noarch

BuildRequires:  python-setuptools
Requires:       TurboGears createrepo python-TurboMail tree

%description
TODO.

%prep
%setup -q -n Fedora-Updates-System-%{version}


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
%{python_sitelib}/updatessystem
%{python_sitelib}/Fedora_Updates_System-%{version}-py%{pyver}.egg-info


%changelog
* Fri Dec 29 2006 Luke Macken <lmacken@redhat.com> - 1.0-1
- Initial creation
