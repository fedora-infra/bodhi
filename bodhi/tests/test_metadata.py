# $Id: test_metadata.py,v 1.1 2006/12/31 09:10:25 lmacken Exp $

import shutil
import tempfile
import turbogears

from os.path import join, exists
from turbogears import testutil, database
from bodhi.util import mkmetadatadir
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

        ## Initialize our temporary repo
        temprepo = tempfile.mkdtemp('bodhi')
        print "Inserting updateinfo into temprepo: %s" % temprepo
        mkmetadatadir(temprepo)
        repodata = join(temprepo, 'repodata')
        assert exists(join(repodata, 'repomd.xml'))
        md.insert_updateinfo(repodata)
        updateinfo = join(repodata, 'updateinfo.xml.gz')
        assert exists(updateinfo)

        ## Read an verify the updateinfo.xml.gz
        uinfo = UpdateMetadata()
        uinfo.add(updateinfo)
        notice = uinfo.get_notice(('mutt', '1.5.14', '1.fc7'))
        assert not notice
        notice = uinfo.get_notice('TurboGears-1.0.2.2-2.fc7')
        assert notice
        print dir(notice)
        from pprint import pprint
        pprint(notice._md)
        assert notice['status'] == update.status
        assert notice['updated'] == update.date_modified
        assert notice['from'] == 'None'
        assert notice['description'] == update.notes
        assert notice['title'] == update.title
        assert notice['issued'] == 'None'
        assert notice['release'] == update.release.long_name
        assert notice['update_id'] == update.update_id
        cve = notice['references'][0]
        assert cve['type'] == 'cve'
        assert cve['href'] == update.cves[0].get_url()
        assert cve['id'] == update.cves[0].cve_id
        assert cve['title'] == None
        bug = notice['references'][1]
        assert bug['href'] == update.bugs[0].get_url()
        assert bug['id'] == '1'
        assert bug['title'] == 'None'
        assert bug['type'] == 'bugzilla'

        ## Clean up
        shutil.rmtree(temprepo)
