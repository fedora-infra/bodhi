# $Id: test_metadata.py,v 1.1 2006/12/31 09:10:25 lmacken Exp $

import turbogears

from turbogears import testutil, database
from bodhi.metadata import ExtendedMetadata
from bodhi.model import (Release, Package, PackageUpdate, Bugzilla,
                                 CVE, Arch)

database.set_db_uri("sqlite:///:memory:")

turbogears.update_config(configfile='dev.cfg',
                         modulename='bodhi.config')

class TestExtendedMetadata(testutil.DBTest):

    def test_metadata(self):
        """
        Test the creation of a PackageUpdate, and the generation of extended
        metadata for the update.
        """
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
        md = ExtendedMetadata('/home/lmacken/code/cvs.fedoraproject.org/fedora-updates-system/updates-stage/6/i386/')
        md.add_update(up)
