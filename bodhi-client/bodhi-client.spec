# Created by pyp2rpm-3.3.7
%global pypi_name bodhi-client
%global pypi_version 5.7.4+devel

Name:           %{pypi_name}
Version:        %{pypi_version}
Release:        1%{?dist}
Summary:        Bodhi client

License:        GPLv2+
URL:            https://github.com/fedora-infra/bodhi
Source0:        %{pypi_name}-%{pypi_version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  python3dist(click)
BuildRequires:  python3dist(koji)
BuildRequires:  python3dist(python-fedora) >= 0.9
BuildRequires:  python3dist(setuptools)

%description


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
%{_bindir}/bodhi
%{python3_sitelib}/bodhi
%{python3_sitelib}/bodhi_client-%{pypi_version}-py%{python3_version}-*.pth
%{python3_sitelib}/bodhi_client-%{pypi_version}-py%{python3_version}.egg-info

%changelog
* Tue Feb 01 2022 vagrant - 5.7.4-1
- Initial package.
