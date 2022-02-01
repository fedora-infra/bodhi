# Created by pyp2rpm-3.3.7
%global pypi_name bodhi-messages
%global pypi_version 5.7.4+devel

Name:           %{pypi_name}
Version:        %{pypi_version}
Release:        1%{?dist}
Summary:        JSON schema for messages sent by Bodhi

License:        GPLv2+
URL:            https://github.com/fedora-infra/bodhi
Source0:        %{pypi_name}-%{pypi_version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  python3dist(fedora-messaging)
BuildRequires:  python3dist(setuptools)

%description
Bodhi Messages This package contains the schema for messages published by
Bodhi.


%prep
%autosetup -n %{pypi_name}-%{pypi_version}
# Remove bundled egg-info
rm -rf %{pypi_name}.egg-info

%build
%py3_build

%install
%py3_install

%files -n %{pypi_name}
%exclude %{python3_sitelib}/tests
%doc README.rst
%{python3_sitelib}/bodhi
%{python3_sitelib}/bodhi_messages-%{pypi_version}-py%{python3_version}-*.pth
%{python3_sitelib}/bodhi_messages-%{pypi_version}-py%{python3_version}.egg-info

%changelog
* Tue Feb 01 2022 vagrant - 5.7.4-1
- Initial package.
