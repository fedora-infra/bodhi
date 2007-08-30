# $Id: test_metadata.py,v 1.1 2006/12/31 09:10:25 lmacken Exp $

#import os
#import shutil
#import tempfile
import turbogears

#from os.path import join, isfile
from turbogears import testutil, database
#from bodhi.util import mkmetadatadir
from bodhi.model import (Release, Package, PackageUpdate, Bugzilla, CVE,
                         PackageBuild)
from bodhi.buildsys import get_session
from bodhi.metadata import ExtendedMetadata
from yum.update_md import UpdateMetadata

database.set_db_uri("sqlite:///:memory:")
turbogears.update_config(configfile='dev.cfg', modulename='bodhi.config')

class TestExtendedMetadata(testutil.DBTest):

    def test_extended_metadata(self):
        # grab the name of a build in updates-testing, and create it in our db
        koji = get_session()
        builds = koji.listTagged('dist-fc7-updates-testing', latest=True)

        # Create all of the necessary database entries
        release = Release(name='fc7', long_name='Fedora 7', id_prefix='FEDORA',
                          dist_tag='dist-fc7')
        package = Package(name=builds[0]['package_name'])
        build = PackageBuild(nvr=builds[0]['nvr'], package=package)
        update = PackageUpdate(title=builds[0]['nvr'],
                               release=release,
                               submitter=builds[0]['owner_name'],
                               status='testing',
                               notes='foobar',
                               type='bugfix')
        update.addPackageBuild(build)
        bug = Bugzilla(bz_id=1)
        update.addBugzilla(bug)
        cve = CVE(cve_id="CVE-2007-0000")
        update.addCVE(cve)
        update.assign_id()
        print update

        # Generate the XML
        md = ExtendedMetadata('dist-fc7-updates-testing')
        md.add_update(update)

        # write updateinfo somewhere.. read and verify against UpdateMetadata


#        ## Initialize our temporary repo
#        #push_stage = tempfile.mkdtemp('bodhi')
#        #for arch in up.release.arches:
#        #    mkmetadatadir(join(push_stage, up.get_repo(), arch.name))
#        #mkmetadatadir(join(push_stage, up.get_repo(), 'SRPMS'))
#
#        ## Add update and insert updateinfo.xml.gz into repo
#        md = ExtendedMetadata()
#        md.add_update(up)
#        md.insert_updateinfo()
#
#        ## Make sure the updateinfo.xml.gz actually exists
#        #updateinfo = join(push_stage, up.get_repo(), 'i386',
#        #                  'repodata', 'updateinfo.xml.gz')
#        #assert isfile(updateinfo)
#        return
#
#        ## Attempt to read the metadata
#        uinfo = UpdateMetadata()
#        uinfo.add(str(updateinfo))
#        notice = uinfo.get_notice(('mutt', '1.5.14', '1.fc7'))
#
#        assert notice
#        assert notice['description'] == up.notes
#        assert notice['update_id'] == up.update_id
#        assert notice['status'] == 'testing'
#        assert notice['from'] == 'updates@fedora.redhat.com'
#        assert notice['type'] == up.type
#
#        ## Verify file list
#        files = []
#        map(lambda x: map(lambda y: files.append(y.split('/')[-1]), x),
#                          up.filelist.values())
#        for pkg in notice['pkglist'][0]['packages']:
#            assert pkg['filename'] in files
#
#        ## Remove the update and verify
#        del uinfo
#        assert md.remove_update(up)
#        md.insert_updateinfo()
#        uinfo = UpdateMetadata()
#        uinfo.add(str(updateinfo))
#        notice = uinfo.get_notice('mutt-1.5.14-1.fc7')
#        assert not notice
#
#        ## Clean up
#        shutil.rmtree(push_stage)
