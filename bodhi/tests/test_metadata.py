# $Id: test_metadata.py,v 1.1 2006/12/31 09:10:25 lmacken Exp $

import turbogears
from turbogears import testutil, database, config
turbogears.update_config(configfile='bodhi.cfg', modulename='bodhi.config')
database.set_db_uri("sqlite:///:memory:")

import glob
import shutil
import tempfile

from datetime import datetime
from hashlib import sha256
from os.path import join, exists, basename
from datetime import datetime
from bodhi.util import mkmetadatadir, get_nvr
from bodhi.model import (Release, Package, PackageUpdate, Bugzilla, CVE,
                         PackageBuild)
from bodhi.buildsys import get_session
from bodhi.metadata import ExtendedMetadata
from yum.update_md import UpdateMetadata


class TestExtendedMetadata(testutil.DBTest):
    def __verify_updateinfo(self, repodata):
        """Verify the updateinfo file

        This is not a test, just a helper function.
        """
        updateinfos = glob.glob(join(repodata, "*-updateinfo.xml.gz"))
        assert len(updateinfos) == 1, "We generated %d updateinfo metadata" % len(updateinfos)

        updateinfo = updateinfos[0]
        hash = basename(updateinfo).split("-", 1)[0]
        hashed = sha256(open(updateinfo).read()).hexdigest()

        assert hash == hashed, "File: %s\nHash: %s" % (basename(updateinfo), hashed)

        return updateinfo

    def test_extended_metadata(self):
        # grab the name of a build in updates-testing, and create it in our db
        koji = get_session()
        builds = koji.listTagged('dist-f13-updates-testing', latest=True)

        # Create all of the necessary database entries
        release = Release(name='F13', long_name='Fedora 13',
                          id_prefix='FEDORA', dist_tag='dist-f13')
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
        print update

        ## Initialize our temporary repo
        temprepo = join(tempfile.mkdtemp('bodhi'), 'f13-updates-testing')
        print "Inserting updateinfo into temprepo: %s" % temprepo
        mkmetadatadir(join(temprepo, 'i386'))
        repodata = join(temprepo, 'i386', 'repodata')
        assert exists(join(repodata, 'repomd.xml'))

        ## Generate the XML
        md = ExtendedMetadata(temprepo)

        ## Insert the updateinfo.xml into the repository
        md.insert_updateinfo()
        updateinfo = self.__verify_updateinfo(repodata)

        ## Read an verify the updateinfo.xml.gz
        uinfo = UpdateMetadata()
        uinfo.add(updateinfo)
        notice = uinfo.get_notice(('mutt', '1.5.14', '1.fc13'))
        assert not notice
        notice = uinfo.get_notice(get_nvr(update.title))
        assert notice
        assert notice['status'] == update.status
        assert notice['updated'] == update.date_modified
        assert notice['from'] == str(config.get('bodhi_email'))
        assert notice['description'] == update.notes
        assert notice['issued'] is not None
        assert notice['update_id'] == update.updateid
        assert notice['epoch'] is None
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
            assert cve['title'] is None

        ## Clean up
        shutil.rmtree(temprepo)

    def test_extended_metadata_updating(self):
        # grab the name of a build in updates-testing, and create it in our db
        koji = get_session()
        builds = koji.listTagged('dist-f13-updates-testing', latest=True)

        # Create all of the necessary database entries
        release = Release(name='F13', long_name='Fedora 13', id_prefix='FEDORA',
                          dist_tag='dist-f13')
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
        bug.title = u'test bug'
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
        updateinfo = self.__verify_updateinfo(repodata)

        ## Read an verify the updateinfo.xml.gz
        uinfo = UpdateMetadata()
        uinfo.add(updateinfo)
        notice = uinfo.get_notice(('mutt', '1.5.14', '1.fc13'))
        assert not notice
        notice = uinfo.get_notice(get_nvr(update.title))
        assert notice
        assert notice['status'] == update.status
        assert notice['updated'] == update.date_modified
        assert notice['from'] == str(config.get('bodhi_email'))
        assert notice['description'] == update.notes
        assert notice['issued'] is not None
        assert notice['update_id'] == update.updateid
        cve = notice['references'][0]
        assert cve['type'] == 'cve'
        assert cve['href'] == update.cves[0].get_url()
        assert cve['id'] == update.cves[0].cve_id
        bug = notice['references'][1]
        assert bug['href'] == update.bugs[0].get_url()
        assert bug['id'] == '1'
        assert bug['type'] == 'bugzilla'
        assert bug['title'] == 'test bug'

        # FC6's yum update metadata parser doesn't know about some stuff
        from yum import __version__
        if __version__ >= '3.0.6':
            assert notice['title'] == update.title
            assert notice['release'] == update.release.long_name
            assert cve['title'] is None

        ## Test out updateinfo.xml updating via our ExtendedMetadata
        md = ExtendedMetadata(temprepo, updateinfo)
        md.insert_updateinfo()
        updateinfo = self.__verify_updateinfo(repodata)

        ## Read an verify the updateinfo.xml.gz
        uinfo = UpdateMetadata()
        uinfo.add(updateinfo)
        notice = uinfo.get_notice(('mutt', '1.5.14', '1.fc13'))
        assert not notice
        notice = uinfo.get_notice(get_nvr(update.title))
        assert notice
        assert notice['status'] == update.status
        assert notice['updated'] == update.date_modified
        assert notice['from'] == str(config.get('bodhi_email'))
        assert notice['description'] == update.notes
        assert notice['issued'] is not None
        assert notice['update_id'] == update.updateid
        cve = notice['references'][0]
        assert cve['type'] == 'cve'
        assert cve['href'] == update.cves[0].get_url()
        assert cve['id'] == update.cves[0].cve_id
        bug = notice['references'][1]
        assert bug['href'] == update.bugs[0].get_url()
        assert bug['id'] == '1'
        assert bug['type'] == 'bugzilla'
        assert bug['title'] == 'test bug', bug

        # FC6's yum update metadata parser doesn't know about some stuff
        from yum import __version__
        if __version__ >= '3.0.6':
            assert notice['title'] == update.title
            assert notice['release'] == update.release.long_name
            assert cve['title'] is None

        ## Clean up
        shutil.rmtree(temprepo)

    def test_extended_metadata_updating_with_edited_update_details(self):
        # grab the name of a build in updates-testing, and create it in our db
        koji = get_session()
        builds = koji.listTagged('dist-f13-updates-testing', latest=True)

        # Create all of the necessary database entries
        release = Release(name='F13', long_name='Fedora 13', id_prefix='FEDORA',
                          dist_tag='dist-f13')
        package = Package(name=builds[0]['package_name'])
        update = PackageUpdate(title=builds[0]['nvr'],
                               release=release,
                               submitter=builds[0]['owner_name'],
                               status='testing',
                               notes='foobar',
                               type='bugfix')
        build = PackageBuild(nvr=builds[0]['nvr'], package=package)
        update.addPackageBuild(build)
        update.assign_id()

        ## Initialize our temporary repo
        temprepo = join(tempfile.mkdtemp('bodhi'), 'f13-updates-testing')
        print "Inserting updateinfo into temprepo: %s" % temprepo
        mkmetadatadir(join(temprepo, 'i386'))
        repodata = join(temprepo, 'i386', 'repodata')
        assert exists(join(repodata, 'repomd.xml'))

        ## Generate the XML
        md = ExtendedMetadata(temprepo)

        ## Insert the updateinfo.xml into the repository
        md.insert_updateinfo()
        updateinfo = self.__verify_updateinfo(repodata)

        ## Read an verify the updateinfo.xml.gz
        uinfo = UpdateMetadata()
        uinfo.add(updateinfo)
        notice = uinfo.get_notice(('mutt', '1.5.14', '1.fc13'))
        assert not notice
        notice = uinfo.get_notice(get_nvr(update.title))
        assert notice
        assert notice['status'] == update.status
        assert notice['updated'] == update.date_modified
        assert notice['from'] == str(config.get('bodhi_email'))
        assert notice['description'] == update.notes
        assert notice['issued'] is not None
        assert notice['update_id'] == update.updateid
        assert notice['title'] == update.title
        assert notice['release'] == update.release.long_name

        ## Edit the update notes
        update.notes = 'blah'
        update.date_modified = datetime.utcnow()

        testutil.capture_log(['bodhi.metadata'])

        ## Test out updateinfo.xml updating via our ExtendedMetadata
        md = ExtendedMetadata(temprepo, updateinfo)
        md.insert_updateinfo()
        updateinfo = self.__verify_updateinfo(repodata)

        ## Read an verify the updateinfo.xml.gz
        uinfo = UpdateMetadata()
        uinfo.add(updateinfo)

        print(testutil.get_log())

        notice = uinfo.get_notice(('TurboGears', '1.0.2.2', '2.fc7'))
        assert notice, uinfo
        assert notice['title'] == update.title
        assert notice['description'] == update.notes

        num_notices = len(uinfo.get_notices())
        assert num_notices == 1, num_notices

        ## Clean up
        shutil.rmtree(temprepo)

    def test_extended_metadata_updating_with_edited_updates(self):
        testutil.capture_log(['bodhi.metadata'])

        # grab the name of a build in updates-testing, and create it in our db
        koji = get_session()
        builds = koji.listTagged('dist-f13-updates-testing', latest=True)

        # Create all of the necessary database entries
        release = Release(name='F13', long_name='Fedora 13', id_prefix='FEDORA',
                          dist_tag='dist-f13')
        package = Package(name=builds[0]['package_name'])
        update = PackageUpdate(title=builds[0]['nvr'],
                               release=release,
                               submitter=builds[0]['owner_name'],
                               status='testing',
                               notes='foobar',
                               type='bugfix')
        build = PackageBuild(nvr=builds[0]['nvr'], package=package)
        update.addPackageBuild(build)
        update.assign_id()

        ## Initialize our temporary repo
        temprepo = join(tempfile.mkdtemp('bodhi'), 'f13-updates-testing')
        print "Inserting updateinfo into temprepo: %s" % temprepo
        mkmetadatadir(join(temprepo, 'i386'))
        repodata = join(temprepo, 'i386', 'repodata')
        assert exists(join(repodata, 'repomd.xml'))

        ## Generate the XML
        md = ExtendedMetadata(temprepo)

        ## Insert the updateinfo.xml into the repository
        md.insert_updateinfo()
        updateinfo = self.__verify_updateinfo(repodata)

        ## Read an verify the updateinfo.xml.gz
        uinfo = UpdateMetadata()
        uinfo.add(updateinfo)
        notice = uinfo.get_notice(('mutt', '1.5.14', '1.fc13'))
        assert not notice
        notice = uinfo.get_notice(get_nvr(update.title))
        assert notice
        assert notice['status'] == update.status
        assert notice['updated'] == update.date_modified
        assert notice['from'] == str(config.get('bodhi_email'))
        assert notice['description'] == update.notes
        assert notice['issued'] is not None
        assert notice['update_id'] == update.updateid
        assert notice['title'] == update.title
        assert notice['release'] == update.release.long_name

        ## Edit the update and bump the build revision
        nvr = 'TurboGears-1.0.2.2-3.fc7'
        newbuild = PackageBuild(nvr=nvr, package=package)
        update.removePackageBuild(build)
        update.addPackageBuild(newbuild)
        update.title = nvr
        update.date_modified = datetime.utcnow()

        # Pretend -2 was unpushed
        assert len(koji.__untag__) == 0
        koji.__untag__.append('TurboGears-1.0.2.2-2.fc7')

        ## Test out updateinfo.xml updating via our ExtendedMetadata
        md = ExtendedMetadata(temprepo, updateinfo)
        md.insert_updateinfo()
        updateinfo = self.__verify_updateinfo(repodata)

        ## Read an verify the updateinfo.xml.gz
        uinfo = UpdateMetadata()
        uinfo.add(updateinfo)

        print(testutil.get_log())

        notice = uinfo.get_notice(('TurboGears', '1.0.2.2', '2.fc7'))
        assert not notice, "Old TG notice did not get pruned: %s" % notice
        notice = uinfo.get_notice(('TurboGears', '1.0.2.2', '3.fc7'))
        assert notice, uinfo
        assert notice['title'] == update.title

        num_notices = len(uinfo.get_notices())
        assert num_notices == 1, num_notices

        ## Clean up
        shutil.rmtree(temprepo)
        del(koji.__untag__[:])

    def test_extended_metadata_updating_with_old_testing_security(self):
        testutil.capture_log(['bodhi.metadata'])

        # grab the name of a build in updates-testing, and create it in our db
        koji = get_session()
        builds = koji.listTagged('dist-f13-updates-testing', latest=True)

        # Create all of the necessary database entries
        release = Release(name='F13', long_name='Fedora 13', id_prefix='FEDORA',
                          dist_tag='dist-f13')
        package = Package(name='TurboGears')
        update = PackageUpdate(title='TurboGears-1.0.2.2-2.fc7',
                               release=release,
                               submitter=builds[0]['owner_name'],
                               status='testing',
                               notes='foobar',
                               type='security')
        build = PackageBuild(nvr='TurboGears-1.0.2.2-2.fc7', package=package)
        update.addPackageBuild(build)

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
        updateinfo = self.__verify_updateinfo(repodata)

        # Create a new non-security update for the same package
        newbuild = 'TurboGears-1.0.2.2-3.fc7'
        update = PackageUpdate(title=newbuild,
                               release=release,
                               submitter=builds[0]['owner_name'],
                               status='testing',
                               notes='foobar',
                               type='enhancement')
        build = PackageBuild(nvr=newbuild, package=package)
        update.addPackageBuild(build)
        update.assign_id()

        koji.__untag__.append('TurboGears-1.0.2.2-2.fc7')

        ## Test out updateinfo.xml updating via our ExtendedMetadata
        md = ExtendedMetadata(temprepo, updateinfo)
        md.insert_updateinfo()
        updateinfo = self.__verify_updateinfo(repodata)

        ## Read an verify the updateinfo.xml.gz
        uinfo = UpdateMetadata()
        uinfo.add(updateinfo)

        print(testutil.get_log())

        assert len(uinfo.get_notices()) == 1, len(uinfo.get_notices())
        assert not uinfo.get_notice(get_nvr('TurboGears-1.0.2.2-2.fc7'))
        notice = uinfo.get_notice(get_nvr(update.title))
        assert notice, 'Cannot find update for %r' % get_nvr(update.title)
        assert notice['status'] == update.status
        assert notice['updated'] == update.date_modified
        assert notice['from'] == str(config.get('bodhi_email'))
        assert notice['description'] == update.notes
        assert notice['issued'] is not None
        assert notice['update_id'] == update.updateid

        ## Clean up
        shutil.rmtree(temprepo)

    def test_extended_metadata_updating_with_old_stable_security(self):
        testutil.capture_log(['bodhi.metadata'])

        koji = get_session()
        del(koji.__untag__[:])
        assert not koji.__untag__, koji.__untag__
        builds = koji.listTagged('dist-f7-updates', latest=True)

        # Create all of the necessary database entries
        release = Release(name='F17', long_name='Fedora 17', id_prefix='FEDORA',
                          dist_tag='dist-f17')
        package = Package(name='TurboGears')
        update = PackageUpdate(title='TurboGears-1.0.2.2-2.fc7',
                               release=release,
                               submitter=builds[0]['owner_name'],
                               status='stable',
                               notes='foobar',
                               type='security')
        build = PackageBuild(nvr='TurboGears-1.0.2.2-2.fc7', package=package)
        update.addPackageBuild(build)

        update.assign_id()
        assert update.updateid

        ## Initialize our temporary repo
        temprepo = join(tempfile.mkdtemp('bodhi'), 'f7-updates')
        print "Inserting updateinfo into temprepo: %s" % temprepo
        mkmetadatadir(join(temprepo, 'i386'))
        repodata = join(temprepo, 'i386', 'repodata')
        assert exists(join(repodata, 'repomd.xml'))

        ## Generate the XML
        md = ExtendedMetadata(temprepo)

        ## Insert the updateinfo.xml into the repository
        md.insert_updateinfo()
        updateinfo = self.__verify_updateinfo(repodata)

        # Create a new non-security update for the same package
        newbuild = 'TurboGears-1.0.2.2-3.fc7'
        update = PackageUpdate(title=newbuild,
                               release=release,
                               submitter=builds[0]['owner_name'],
                               status='stable',
                               notes='foobar',
                               type='enhancement')
        build = PackageBuild(nvr=newbuild, package=package)
        update.addPackageBuild(build)
        update.assign_id()

        koji.__untag__.append('TurboGears-1.0.2.2-2.fc7')

        ## Test out updateinfo.xml updating via our ExtendedMetadata
        md = ExtendedMetadata(temprepo, updateinfo)
        md.insert_updateinfo()
        updateinfo = self.__verify_updateinfo(repodata)

        ## Read an verify the updateinfo.xml.gz
        uinfo = UpdateMetadata()
        uinfo.add(updateinfo)

        print(testutil.get_log())

        assert len(uinfo.get_notices()) == 2, len(uinfo.get_notices())
        assert uinfo.get_notice(get_nvr('TurboGears-1.0.2.2-2.fc7'))
        notice = uinfo.get_notice(get_nvr(update.title))
        assert notice, 'Cannot find update for %r' % get_nvr(update.title)
        assert notice['status'] == update.status
        assert notice['updated'] == update.date_modified
        assert notice['from'] == str(config.get('bodhi_email'))
        assert notice['description'] == update.notes
        assert notice['issued'] is not None
        assert notice['update_id'] == update.updateid

        ## Clean up
        shutil.rmtree(temprepo)
        del(koji.__untag__[:])
