# Created by pyp2rpm-3.3.7
%global pypi_name bodhi-server
%global pypi_version 6.0.0

Name:           %{pypi_name}
Version:        %{pypi_version}
Release:        0%{?dist}
Summary:        Bodhi server

License:        GPLv2+
URL:            https://github.com/fedora-infra/bodhi
Source0:        %{pypi_name}-%{pypi_version}.tar.gz
BuildArch:      noarch

BuildRequires:  make
BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-devel
BuildRequires:  python3-sphinx

Requires: bodhi-client == %{version}-%{release}
Requires: python3-bodhi-messages == %{version}-%{release}
Requires: fedora-messaging
Requires: git
Requires: httpd
Requires: intltool
Requires: python3-librepo
Requires: python3-mod_wsgi

Provides:  bundled(aajohan-comfortaa-fonts)
Provides:  bundled(abattis-cantarell-fonts)
Provides:  bundled(bootstrap) = 3.0.1
Provides:  bundled(bootstrap) = 3.0.2
Provides:  bundled(bootstrap) = 3.1.1
Provides:  bundled(chrissimpkins-hack-fonts)
Provides:  bundled(fedora-bootstrap) = 1.0.1
Provides:  bundled(fontawesome-fonts-web) = 4.4.0
Provides:  bundled(js-chart)
Provides:  bundled(js-excanvas)
Provides:  bundled(js-jquery) = 1.10.2
Provides:  bundled(js-jquery) = 2.0.3
Provides:  bundled(js-messenger)
Provides:  bundled(js-moment)
Provides:  bundled(js-typeahead.js) = 1.1.1
Provides:  bundled(nodejs-flot)
Provides:  bundled(open-sans-fonts)
Provides:  bundled(xstatic-bootstrap-datepicker-common)

%py_provides python3-bodhi-server

%description
Bodhi is a modular framework that facilitates the process of publishing
updates for a software distribution.


%package -n bodhi-composer
Summary: Bodhi composer backend

Requires: %{py3_dist jinja2}
Requires: bodhi-server == %{version}-%{release}
Requires: pungi >= 4.1.20
Requires: python3-createrepo_c
Requires: skopeo

%description -n bodhi-composer
The Bodhi composer is the component that publishes Bodhi artifacts to
repositories.


%prep
%autosetup -n %{pypi_name}-%{pypi_version}
# Remove bundled egg-info
rm -rf %{pypi_name}.egg-info

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel
make %{?_smp_mflags} -C docs man

%install
%pyproject_install

%{__mkdir_p} %{buildroot}/var/lib/bodhi
%{__mkdir_p} %{buildroot}/var/cache/bodhi
%{__mkdir_p} %{buildroot}%{_sysconfdir}/httpd/conf.d
%{__mkdir_p} %{buildroot}%{_sysconfdir}/bodhi
%{__mkdir_p} %{buildroot}%{_datadir}/bodhi
%{__mkdir_p} -m 0755 %{buildroot}/%{_localstatedir}/log/bodhi

install -m 644 apache/bodhi.conf %{buildroot}%{_sysconfdir}/httpd/conf.d/bodhi.conf
sed -i -s 's/BODHI_VERSION/%{version}/g' %{buildroot}%{_sysconfdir}/httpd/conf.d/bodhi.conf
install -m 640 production.ini %{buildroot}%{_sysconfdir}/bodhi/production.ini
install -m 640 alembic.ini %{buildroot}%{_sysconfdir}/bodhi/alembic.ini
install apache/bodhi.wsgi %{buildroot}%{_datadir}/bodhi/bodhi.wsgi
install -d %{buildroot}%{_mandir}/man1
install -pm0644 docs/_build/*.1 %{buildroot}%{_mandir}/man1/

%check
%{pytest} -v

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
%config(noreplace) %{_sysconfdir}/bodhi/alembic.ini
%config(noreplace) %{_sysconfdir}/httpd/conf.d/bodhi.conf
%dir %{_sysconfdir}/bodhi/
%{python3_sitelib}/bodhi
%{python3_sitelib}/bodhi_server-%{pypi_version}.dist-info
%{_mandir}/man1/bodhi-*.1*
%{_mandir}/man1/initialize_bodhi_db.1*
%attr(-,bodhi,root) %{_datadir}/bodhi
%attr(-,bodhi,bodhi) %config(noreplace) %{_sysconfdir}/bodhi/*
%attr(0775,bodhi,bodhi) %{_localstatedir}/cache/bodhi
# These excluded files are in the bodhi-composer package so don't include them here.
%exclude %{python3_sitelib}/bodhi/server/tasks/composer.py
%exclude %{python3_sitelib}/bodhi/server/tasks/__pycache__/composer.*
%exclude %{python3_sitelib}/bodhi/server/metadata.py
%exclude %{python3_sitelib}/bodhi/server/__pycache__/metadata.*

%files -n bodhi-composer
%license COPYING
%doc README.rst
%pycached %{python3_sitelib}/bodhi/server/tasks/composer.py
%pycached %{python3_sitelib}/bodhi/server/metadata.py

%changelog
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
