# Created by pyp2rpm-3.3.7
%global pypi_name bodhi-server
%global pypi_version 5.7.4+devel

Name:           %{pypi_name}
Version:        %{pypi_version}
Release:        1%{?dist}
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
%exclude %{python3_sitelib}/tests
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
%{python3_sitelib}/apache
%{python3_sitelib}/bodhi
%{python3_sitelib}/bodhi_server-%{pypi_version}-py%{python3_version}-*.pth
%{python3_sitelib}/bodhi_server-%{pypi_version}-py%{python3_version}.egg-info

%changelog
* Mon Jan 31 2022 ryanlerch - 5.7.4-1
- Initial package.
