# $Id: test_model.py,v 1.5 2006/12/31 09:10:25 lmacken Exp $

import datetime
import turbogears

from turbogears import testutil, database
from bodhi.model import (Release, Package, PackageUpdate, Bugzilla,
                                 Comment, CVE, Arch)

database.set_db_uri("sqlite:///:memory:")

turbogears.update_config(configfile='dev.cfg',
                         modulename='bodhi.config')


class TestRelease(testutil.DBTest):
    def get_model(self):
        return Release
    def test_creation(self):
        rel = Release(name='fc6', long_name='Fedora Core 6', codename='Zod')
        assert rel.long_name == 'Fedora Core 6'

class TestPackage(testutil.DBTest):
    def get_model(self):
        return Package
    def test_creation(self):
        pkg = Package(name='nethack')
        assert pkg.name == 'nethack'

class TestPackageUpdate(testutil.DBTest):
    def get_model(self):
        return PackageUpdate
    def test_creation(self):
        pkg = Package(name='foobar')
        arch = Arch(name='i386', subarches=['i686', 'athlon'])
        rel = Release(name='fc5', long_name='Fedora Core 5',
                      codename='Bordeaux')
        rel.addArch(arch)
        up = PackageUpdate(nvr='foobar-1.2-3', package=pkg, release=rel,
                           submitter='lmacken@fedoraproject.org',
                           testing=True, type='security',
                           notes='Update notes and such')
        bug = Bugzilla(bz_id=1234)
        cve = CVE(cve_id="CVE-2006-1234")
        up.addBugzilla(bug)
        up.addCVE(cve)

    def test_filelist(self):
        """ Test out the build_filelist method using a test gaim build.  This
            package is multilib, so we will assert those packages as well
        """
        import sys
        pkg = Package(name='gaim')
        arch = Arch(name='i386', subarches=['i686', 'athlon'])
        rel = Release(name='fc6', long_name='Fedora Core 6',
                      codename='Zod')
        rel.addArch(arch)
        up = PackageUpdate(nvr='gaim-2.0.0-0.9.beta3.fc6', package=pkg,
                           release=rel, submitter='lmacken@fedoraproject.org',
                           testing=True, type='security',
                           notes='Update notes and such')


class TestComment(testutil.DBTest):
    def get_model(self):
        return Comment
    def test_creation(self):
        pkg = Package(name='foobar')
        arch = Arch(name='i386', subarches=['i686', 'athlon'])
        rel = Release(name='fc5', long_name='Fedora Core 5',
                      codename='Bordeaux')
        rel.addArch(arch)
        up = PackageUpdate(nvr='foobar-1.2-3', package=pkg, release=rel,
                           submitter='lmacken@fedoraproject.org',
                           testing=True, type='bugfix',
                           notes='Update notes and such')
        comment = Comment(update=up, user='lmacken@fedoraproject.org',
                          text='Test comment')

class TestCVE(testutil.DBTest):
    def get_model(self):
        return CVE
    def test_creation(self):
        cve = CVE(cve_id="CVE-2006-0000")

class TestBugzilla(testutil.DBTest):
    def get_model(self):
        return Bugzilla
    def test_creation(self):
        bug = Bugzilla(bz_id=1234)
