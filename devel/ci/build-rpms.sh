#!/usr/bin/bash

# Build the RPMs in CI

set -e

MODULES=$@

set -x

mkdir -p ~/rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}

githash=$(git rev-parse --short HEAD)
versionsuffix=\^$(date -u +%Y%m%d%H%M)git$githash

sed -i "s/\(bodhi-server \${util.version()}\)/\1$versionsuffix/g" bodhi-server/bodhi/server/templates/master.html

for submodule in ${MODULES}; do
    cd $submodule
    /usr/bin/python3 setup.py sdist
    cp dist/* ~/rpmbuild/SOURCES/
    cp $submodule.spec ~/rpmbuild/SPECS/
    moduleversion=$(python3 setup.py --version)
    sed -i "s/^%global pypi_version.*/%global pypi_version $moduleversion/g" ~/rpmbuild/SPECS/$submodule.spec
    sed -i "s/^Version:.*/Version:%{pypi_version}$versionsuffix/g" ~/rpmbuild/SPECS/$submodule.spec
    rpmdev-bumpspec ~/rpmbuild/SPECS/$submodule.spec
    rpmbuild -ba ~/rpmbuild/SPECS/$submodule.spec
    cd ..
done
cp --verbose ~/rpmbuild/SRPMS/*.src.rpm /results/
cp --verbose ~/rpmbuild/RPMS/noarch/*.rpm /results/
