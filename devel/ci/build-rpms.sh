#!/usr/bin/bash

# Build the RPMs in CI

set -e

MODULES=$@

mkdir -p ~/rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}

for submodule in ${MODULES}; do
    cd $submodule
    /usr/bin/python3 setup.py sdist
    cp dist/* ~/rpmbuild/SOURCES/
    cp $submodule.spec ~/rpmbuild/SPECS/
    githash=$(git rev-parse --short HEAD)
    moduleversion=$(python3 setup.py --version)
    sed -i "s/^%global pypi_version.*/%global pypi_version $moduleversion/g" ~/rpmbuild/SPECS/$submodule.spec
    sed -i "s/^Version:.*/Version:%{pypi_version}^$(date +%Y%m%d)git$githash/g" ~/rpmbuild/SPECS/$submodule.spec
    rpmdev-bumpspec ~/rpmbuild/SPECS/$submodule.spec
    rpmbuild -ba ~/rpmbuild/SPECS/$submodule.spec
    cp ~/rpmbuild/SRPMS/$submodule*.src.rpm /results/
    cp ~/rpmbuild/RPMS/noarch/$submodule*.rpm /results/
    cd ..
done
