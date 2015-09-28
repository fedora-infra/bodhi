rpmdev-bumpspec bodhi.spec
cp bodhi.spec ~/rpmbuild/SPECS/
RELEASE=$(grep Release: bodhi.spec | cut -d% -f 1 | cut -d: -f2 | tr -d ' ')
FEDORA=$(cat /etc/fedora-release | cut -d' ' -f3)
python setup.py sdist
mv dist/bodhi-2.0.tar.gz ~/rpmbuild/SOURCES/
rpmbuild -bs ~/rpmbuild/SPECS/bodhi.spec
scp ~/rpmbuild/SRPMS/bodhi-2.0-$RELEASE.fc$FEDORA.src.rpm fedorapeople.org:~/public_html/rpms/
copr-cli build bodhi2 https://lmacken.fedorapeople.org/rpms/bodhi-2.0-$RELEASE.fc$FEDORA.src.rpm
