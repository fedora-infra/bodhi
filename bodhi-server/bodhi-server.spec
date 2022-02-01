# Created by pyp2rpm-3.3.7
%global pypi_name bodhi-server
%global pypi_version 5.7.4

Name:           %{pypi_name}
Version:        %{pypi_version}
Release:        0%{?dist}
Summary:        Bodhi server

License:        GPLv2+
URL:            https://github.com/fedora-infra/bodhi
Source0:        %{pypi_name}-%{pypi_version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  python3dist(alembic)
BuildRequires:  python3dist(arrow)
BuildRequires:  python3dist(backoff)
BuildRequires:  python3dist(bleach)
BuildRequires:  python3dist(celery) >= 4.2
BuildRequires:  python3dist(click)
BuildRequires:  python3dist(colander)
BuildRequires:  python3dist(cornice) >= 3.1
BuildRequires:  python3dist(dogpile.cache)
BuildRequires:  python3dist(fedora-messaging)
BuildRequires:  python3dist(feedgen) >= 0.7
BuildRequires:  python3dist(jinja2)
BuildRequires:  python3dist(koji)
BuildRequires:  python3dist(markdown)
BuildRequires:  python3dist(prometheus-client)
BuildRequires:  python3dist(psycopg2)
BuildRequires:  python3dist(py3dns)
BuildRequires:  python3dist(pyasn1-modules)
BuildRequires:  python3dist(pylibravatar)
BuildRequires:  python3dist(pyramid) >= 1.7
BuildRequires:  python3dist(pyramid-fas-openid)
BuildRequires:  python3dist(pyramid-mako)
BuildRequires:  python3dist(python-bugzilla)
BuildRequires:  python3dist(python-fedora)
BuildRequires:  python3dist(pyyaml)
BuildRequires:  python3dist(requests)
BuildRequires:  python3dist(responses)
BuildRequires:  python3dist(setuptools)
BuildRequires:  python3dist(simplemediawiki) = 1.2~b2
BuildRequires:  python3dist(sqlalchemy)
BuildRequires:  python3dist(waitress)
BuildRequires:  python3dist(whitenoise)

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
%doc README.rst bodhi/server/migrations/README.rst bodhi/server/static/vendor/fedora-bootstrap/README.rst
%{_bindir}/bodhi-approve-testing
%{_bindir}/bodhi-check-policies
%{_bindir}/bodhi-clean-old-composes
%{_bindir}/bodhi-expire-overrides
%{_bindir}/bodhi-push
%{_bindir}/bodhi-sar
%{_bindir}/bodhi-shell
%{_bindir}/bodhi-skopeo-lite
%{_bindir}/bodhi-untag-branched
%{_bindir}/initialize_bodhi_db
%{python3_sitelib}/bodhi
%{python3_sitelib}/bodhi_server-%{pypi_version}-py%{python3_version}-*.pth
%{python3_sitelib}/bodhi_server-%{pypi_version}-py%{python3_version}.egg-info

%changelog
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
