# $Id: test_metadata.py,v 1.1 2006/12/31 09:10:25 lmacken Exp $

import os
import shutil
import tempfile
import turbogears

from pprint import pprint
from os.path import join, isfile
from turbogears import testutil, database
from bodhi.util import mkmetadatadir
from bodhi.model import (Release, Package, PackageUpdate, Bugzilla, CVE,
                         PackageBuild)
from bodhi.metadata import ExtendedMetadata
from yum.update_md import UpdateMetadata

database.set_db_uri("sqlite:///:memory:")
turbogears.update_config(configfile='dev.cfg', modulename='bodhi.config')

class TestExtendedMetadata(testutil.DBTest):

    def test_metadata(self):
        """
        Test the creation of a PackageUpdate, and the generation of extended
        metadata for the update.
        """
        return
        ## Create an update
        pkg = Package(name='foobar')
        #arch = Arch(name='i386', subarches=['i386'])
        rel = Release(name='fc7', long_name='Fedora Core 7',
                      id_prefix='FEDORA', dist_tag='dist-fc7')
        #rel.addArch(arch)
        up = PackageUpdate(title='mutt-1.5.14-1.fc7', release=rel,
                           submitter='foo@bar.com', status='testing',
                           type='security', notes='This is a long update advisory because I need to test the yum.update_md.UpdateNotice.__str__ to make sure it can wrap this properly and whatnot.  blah.')
        build = PackageBuild(nvr='mutt-1.5.14-1.fc7', package=pkg)
        up.addPackageBuild(build)

        ## Add some references
        map(up.addBugzilla, map(lambda x: Bugzilla(bz_id=x), (1234, 4321, 1)))
        map(up.addCVE, map(lambda x: CVE(cve_id=x), ("CVE-2006-1234",
                                                     "CVE-2007-4321")))
        up.assign_id()

        assert up.update_id == '%s-2007-0001' % rel.id_prefix

        ## Initialize our temporary repo
        #push_stage = tempfile.mkdtemp('bodhi')
        #for arch in up.release.arches:
        #    mkmetadatadir(join(push_stage, up.get_repo(), arch.name))
        #mkmetadatadir(join(push_stage, up.get_repo(), 'SRPMS'))

        ## Add update and insert updateinfo.xml.gz into repo
        md = ExtendedMetadata()
        md.add_update(up)
        md.insert_updateinfo()

        ## Make sure the updateinfo.xml.gz actually exists
        #updateinfo = join(push_stage, up.get_repo(), 'i386',
        #                  'repodata', 'updateinfo.xml.gz')
        #assert isfile(updateinfo)
        return

        ## Attempt to read the metadata
        uinfo = UpdateMetadata()
        uinfo.add(str(updateinfo))
        notice = uinfo.get_notice(('mutt', '1.5.14', '1.fc7'))

        assert notice
        assert notice['description'] == up.notes
        assert notice['update_id'] == up.update_id
        assert notice['status'] == 'testing'
        assert notice['from'] == 'updates@fedora.redhat.com'
        assert notice['type'] == up.type

        ## Verify file list
        files = []
        map(lambda x: map(lambda y: files.append(y.split('/')[-1]), x),
                          up.filelist.values())
        for pkg in notice['pkglist'][0]['packages']:
            assert pkg['filename'] in files

        ## Remove the update and verify
        del uinfo
        assert md.remove_update(up)
        md.insert_updateinfo()
        uinfo = UpdateMetadata()
        uinfo.add(str(updateinfo))
        notice = uinfo.get_notice('mutt-1.5.14-1.fc7')
        assert not notice

        ## Clean up
        shutil.rmtree(push_stage)
