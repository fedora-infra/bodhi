# $Id: test_metadata.py,v 1.1 2006/12/31 09:10:25 lmacken Exp $

import turbogears
from turbogears import testutil, database, config
turbogears.update_config(configfile='bodhi.cfg', modulename='bodhi.config')
database.set_db_uri("sqlite:///:memory:")

import shutil
import tempfile

from os.path import join, exists
from bodhi.util import mkmetadatadir, get_nvr
from bodhi.model import (Release, Package, PackageUpdate, Bugzilla, CVE,
                         PackageBuild)
from bodhi.buildsys import get_session
from bodhi.metadata import ExtendedMetadata
from yum.update_md import UpdateMetadata


class TestExtendedMetadata(testutil.DBTest):

    def test_extended_metadata(self):
        # grab the name of a build in updates-testing, and create it in our db
        koji = get_session()
        builds = koji.listTagged('dist-fc7-updates-testing', latest=True)

        # Create all of the necessary database entries
        release = Release(name='fc7', long_name='Fedora 7', id_prefix='FEDORA',
                          dist_tag='dist-fc7')
        package = Package(name=builds[0]['package_name'])
        update = PackageUpdate(title=builds[0]['nvr'],
                               release=release,
                               submitter=builds[0]['owner_name'],
                               status='testing',
                               notes='foobar',
                               type='bugfix')
        build = PackageBuild(nvr=builds[0]['nvr'], package=package)
        update.addPackageBuild(update)

        bug = Bugzilla(bz_id=1)
        update.addBugzilla(bug)
        cve = CVE(cve_id="CVE-2007-0000")
        update.addCVE(cve)
        update.assign_id()
        print update

        ## Initialize our temporary repo
        temprepo = join(tempfile.mkdtemp('bodhi'), 'f7-updates-testing')
        print "Inserting updateinfo into temprepo: %s" % temprepo
        mkmetadatadir(join(temprepo, 'i386'))
        repodata = join(temprepo, 'i386', 'repodata')
        assert exists(join(repodata, 'repomd.xml'))

        ## Generate the XML
        md = ExtendedMetadata(temprepo)

        ## Insert the updateinfo.xml into the repository
        md.insert_updateinfo()
        updateinfo = join(repodata, 'updateinfo.xml.gz')
        assert exists(updateinfo)

        ## Read an verify the updateinfo.xml.gz
        uinfo = UpdateMetadata()
        uinfo.add(updateinfo)
        notice = uinfo.get_notice(('mutt', '1.5.14', '1.fc7'))
        assert not notice
        notice = uinfo.get_notice(get_nvr(update.title))
        assert notice
        assert notice['status'] == update.status
        assert notice['updated'] == update.date_modified
        assert notice['from'] == str(config.get('release_team_address'))
        assert notice['description'] == update.notes
        assert notice['issued'] == 'None'
        assert notice['update_id'] == update.updateid
        cve = notice['references'][0]
        assert cve['type'] == 'cve'
        assert cve['href'] == update.cves[0].get_url()
        assert cve['id'] == update.cves[0].cve_id
        bug = notice['references'][1]
        assert bug['href'] == update.bugs[0].get_url()
        assert bug['id'] == '1'
        assert bug['type'] == 'bugzilla'

        # FC6's yum update metadata parser doesn't know about some stuff
        from yum import __version__
        if __version__ >= '3.0.6':
            assert notice['title'] == update.title
            assert notice['release'] == update.release.long_name
            assert cve['title'] == None

        ## Clean up
        shutil.rmtree(temprepo)

    def test_extended_metadata_updating(self):
        # grab the name of a build in updates-testing, and create it in our db
        koji = get_session()
        builds = koji.listTagged('dist-fc7-updates-testing', latest=True)

        # Create all of the necessary database entries
        release = Release(name='fc7', long_name='Fedora 7', id_prefix='FEDORA',
                          dist_tag='dist-fc7')
        package = Package(name=builds[0]['package_name'])
        update = PackageUpdate(title=builds[0]['nvr'],
                               release=release,
                               submitter=builds[0]['owner_name'],
                               status='testing',
                               notes='foobar',
                               type='bugfix')
        build = PackageBuild(nvr=builds[0]['nvr'], package=package)
        update.addPackageBuild(build)

        bug = Bugzilla(bz_id=1)
        update.addBugzilla(bug)
        cve = CVE(cve_id="CVE-2007-0000")
        update.addCVE(cve)
        update.assign_id()

        ## Initialize our temporary repo
        temprepo = join(tempfile.mkdtemp('bodhi'), 'f7-updates-testing')
        print "Inserting updateinfo into temprepo: %s" % temprepo
        mkmetadatadir(join(temprepo, 'i386'))
        repodata = join(temprepo, 'i386', 'repodata')
        assert exists(join(repodata, 'repomd.xml'))

        ## Generate the XML
        md = ExtendedMetadata(temprepo)

        ## Insert the updateinfo.xml into the repository
        md.insert_updateinfo()
        updateinfo = join(repodata, 'updateinfo.xml.gz')
        assert exists(updateinfo)

        ## Read an verify the updateinfo.xml.gz
        uinfo = UpdateMetadata()
        uinfo.add(updateinfo)
        notice = uinfo.get_notice(('mutt', '1.5.14', '1.fc7'))
        assert not notice
        notice = uinfo.get_notice(get_nvr(update.title))
        assert notice
        assert notice['status'] == update.status
        assert notice['updated'] == update.date_modified
        assert notice['from'] == str(config.get('release_team_address'))
        assert notice['description'] == update.notes
        assert notice['issued'] == 'None'
        assert notice['update_id'] == update.updateid
        cve = notice['references'][0]
        assert cve['type'] == 'cve'
        assert cve['href'] == update.cves[0].get_url()
        assert cve['id'] == update.cves[0].cve_id
        bug = notice['references'][1]
        assert bug['href'] == update.bugs[0].get_url()
        assert bug['id'] == '1'
        assert bug['type'] == 'bugzilla'

        # FC6's yum update metadata parser doesn't know about some stuff
        from yum import __version__
        if __version__ >= '3.0.6':
            assert notice['title'] == update.title
            assert notice['release'] == update.release.long_name
            assert cve['title'] == None

        ## Test out updateinfo.xml updating via our ExtendedMetadata
        md = ExtendedMetadata(temprepo, updateinfo)
        md.insert_updateinfo()
        updateinfo = join(repodata, 'updateinfo.xml.gz')
        assert exists(updateinfo)

        ## Read an verify the updateinfo.xml.gz
        uinfo = UpdateMetadata()
        uinfo.add(updateinfo)
        notice = uinfo.get_notice(('mutt', '1.5.14', '1.fc7'))
        assert not notice
        notice = uinfo.get_notice(get_nvr(update.title))
        assert notice
        assert notice['status'] == update.status
        assert notice['updated'] == update.date_modified
        assert notice['from'] == str(config.get('release_team_address'))
        assert notice['description'] == update.notes
        assert notice['issued'] == 'None'
        assert notice['update_id'] == update.updateid
        cve = notice['references'][0]
        assert cve['type'] == 'cve'
        assert cve['href'] == update.cves[0].get_url()
        assert cve['id'] == update.cves[0].cve_id
        bug = notice['references'][1]
        assert bug['href'] == update.bugs[0].get_url()
        assert bug['id'] == '1'
        assert bug['type'] == 'bugzilla'

        # FC6's yum update metadata parser doesn't know about some stuff
        from yum import __version__
        if __version__ >= '3.0.6':
            assert notice['title'] == update.title
            assert notice['release'] == update.release.long_name
            assert cve['title'] == None

        ## Clean up
        shutil.rmtree(temprepo)
