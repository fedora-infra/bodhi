# Created by pyp2rpm-3.3.7
%global pypi_name bodhi-client
%global src_name bodhi_client
%global pypi_version 7.1.1

Name:           %{pypi_name}
Version:        %{pypi_version}
Release:        0%{?dist}
Summary:        Bodhi client

License:        GPLv2+
URL:            https://github.com/fedora-infra/bodhi
Source0:        %{src_name}-%{pypi_version}.tar.gz
BuildArch:      noarch

BuildRequires:  make
BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-devel
BuildRequires:  python3-pytest
BuildRequires:  python3-pytest-cov
BuildRequires:  python3-pytest-mock
BuildRequires:  python3-sphinx

Requires: koji

Obsoletes: python3-bodhi-client <= 5.7.5
# Replace the bodhi metapackage
Obsoletes: bodhi <= 5.7.5

%py_provides python3-bodhi-client

%description
Command-line client for Bodhi, Fedora's update gating system.

%prep
%autosetup -n %{src_name}-%{pypi_version}
# Remove bundled egg-info
rm -rf %{pypi_name}.egg-info

%generate_buildrequires
%pyproject_buildrequires


%build
%pyproject_wheel
make %{?_smp_mflags} -C docs man

%install
%pyproject_install
%pyproject_save_files bodhi

install -d %{buildroot}%{_mandir}/man1
install -pm0644 docs/_build/bodhi.1 %{buildroot}%{_mandir}/man1/
install -d %{buildroot}%{_sysconfdir}/bash_completion.d
install -pm0644 bodhi-client.bash %{buildroot}%{_sysconfdir}/bash_completion.d/bodhi-client.bash

%check
%pyproject_check_import
%{pytest} -v

%files -n %{pypi_name} -f %{pyproject_files}
%{_bindir}/bodhi
%{_mandir}/man1/bodhi.1*
%config(noreplace) %{_sysconfdir}/bash_completion.d/bodhi-client.bash

%changelog
* Sat Mar 18 2023 Mattia Verga <mattia.verga@fedoraproject.org> - 7.1.1-1
- Update to 7.1.1

* Sun Jan 22 2023 Mattia Verga <mattia.verga@fedoraproject.org> - 7.1.0-1
- Update to 7.1.0

* Sat Jan 14 2023 Mattia Verga <mattia.verga@fedoraproject.org> - 7.0.1-1
- Update to 7.0.1

* Sat Nov 26 2022 Mattia Verga <mattia.verga@fedoraproject.org> - 7.0.0-1
- Update to 7.0.0.

* Fri Apr 08 2022 Aurelien Bompard <abompard@fedoraproject.org> - 6.0.0-1
- Update to 6.0.0.

* Wed Feb 23 2022 Ryan Lerch <rlerch@redhat.com> - 5.7.5-0
- Prepare the Bodhi client to be compatible with an OIDC-enabled server. PR#4391.

* Mon Jan 24 2022 Lenka Segura <lsegura@redhat.com> - 5.7.4-2
- rebuilt

* Sat Apr 24 2021 Kevin Fenzi <kevin@scrye.com> - 5.7.0-1
- Update to 5.7.0. Fixes rhbz#1949260

* Tue Jan 26 2021 Fedora Release Engineering <releng@fedoraproject.org> - 5.6.1-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Tue Dec 29 2020 Mattia Verga <mattia.verga@protonmail.com> - 5.6.1-3
- Re-enable docs build
- Re-enable tests
- Increase required test coverage to 98.

* Mon Nov 30 2020 Clément Verna <cverna@fedoraproject.org> - 5.6.1-1
- Update to 5.6.1
  https://github.com/fedora-infra/bodhi/releases/tag/5.6.1
- Remove Graphql from the server.

* Sun Sep 27 2020 Kevin Fenzi <kevin@scrye.com> - 5.5.0-1
- Update to 5.5.0. Fixes bug #1815307

* Sat Aug 01 2020 Fedora Release Engineering <releng@fedoraproject.org> - 5.2.2-4
- Second attempt - Rebuilt for
  https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Mon Jul 27 2020 Fedora Release Engineering <releng@fedoraproject.org> - 5.2.2-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Mon May 25 2020 Miro Hrončok <mhroncok@redhat.com> - 5.2.2-2
- Rebuilt for Python 3.9

* Wed Mar 25 2020 Clément Verna <cverna@fedoraproject.org> - 5.2.2-1
- Update to 5.2.2
  https://github.com/fedora-infra/bodhi/releases/tag/5.2.2

* Mon Mar 23 2020 Clément Verna <cverna@fedoraproject.org> - 5.2.1-1
- Update to 5.2.1
  https://github.com/fedora-infra/bodhi/releases/tag/5.2.1

* Thu Mar 19 2020 Clément Verna <cverna@fedoraproject.org> - 5.2.0-1
- Update to 5.2.0
  https://github.com/fedora-infra/bodhi/releases/tag/5.2.0

* Thu Jan 30 2020 Nils Philippsen <nils@redhat.com> - 5.1.1-1
- Update to 5.1.1.
  https://github.com/fedora-infra/bodhi/releases/tag/5.1.1

* Tue Jan 28 2020 Nils Philippsen <nils@redhat.com> - 5.1.0-3
- remove obsolete patch which caused the build to fail
- relax test coverage requirements

* Tue Jan 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 5.1.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild
