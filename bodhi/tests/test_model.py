# $Id: test_model.py,v 1.5 2006/12/31 09:10:25 lmacken Exp $

import os
import sys
import time
import shutil
import tempfile
import turbogears

from os.path import join, exists, basename
from turbogears import testutil, database, config
from bodhi.util import mkmetadatadir
from bodhi.model import (Release, Package, PackageUpdate, Bugzilla, CVE,
                         PackageBuild)
from bodhi.exceptions import (DuplicateEntryError, SQLiteIntegrityError,
                              PostgresIntegrityError)

from yum.update_md import UpdateMetadata

database.set_db_uri("sqlite:///:memory:")
turbogears.update_config(configfile='dev.cfg',
                         modulename='bodhi.config')

class TestKoji(testutil.DBTest):

    def test_connectivity(self):
        from bodhi.buildsys import get_session
        koji = get_session()
        assert koji

class TestPackageUpdate(testutil.DBTest):

    def get_pkg(self):
        return Package(name='yum')

    def get_rel(self):
        rel = Release(name='fc7', long_name='Fedora 7', id_prefix='FEDORA',
                      dist_tag='dist-fc7')
        return rel

    def get_build(self, nvr='yum-3.2.1-1.fc7'):
        package = self.get_pkg()
        build = PackageBuild(nvr=nvr, package=package)
        return build

    def get_update(self, name='yum-3.2.1-1.fc7'):
        update = PackageUpdate(title=name,
                               release=self.get_rel(),
                               submitter='foo@bar.com',
                               status='testing',
                               notes='foobar',
                               type='security')
        build = self.get_build(name)
        update.addPackageBuild(build)
        return update

    def get_bug(self):
        return Bugzilla(bz_id=1)

    def get_cve(self):
        return CVE(cve_id="CVE-2007-0000")

    def test_dupe(self):
        update1 = self.get_update()
        try:
            update2 = self.get_update()
        except (DuplicateEntryError, PostgresIntegrityError,
                SQLiteIntegrityError):
            return
        assert False

    def test_creation(self):
        update = self.get_update()
        assert update.title == 'yum-3.2.1-1.fc7'
        assert update.builds[0].package.name == 'yum'
        assert update.release.name == 'fc7'
        assert update.release.updates[0] == update
        assert update.status == 'testing'
        assert update.type == 'security'
        assert update.notes == 'foobar'
        bug = self.get_bug()
        cve = self.get_cve()
        update.addBugzilla(bug)
        update.addCVE(cve)
        assert update.bugs[0].bz_id == 1
        assert update.cves[0].cve_id == 'CVE-2007-0000'

    def test_id(self):
        update = self.get_update()
        update.assign_id()
        assert update.update_id == '%s-%s-0001' % (update.release.id_prefix,
                                                   time.localtime()[0])

    def test_multibuild(self):
        from bodhi import util
        builds = ('yum-3.2.1-1.fc7', 'httpd-2.2.4-4.1.fc7')
        pkg_builds = []
        for build in builds:
            nvr = util.get_nvr(build)
            pkg = Package(name=nvr[0])
            b = PackageBuild(nvr=build, package=pkg)
            pkg_builds.append(b)
        release = self.get_rel()
        update = PackageUpdate(title=','.join(builds), release=release,
                               submitter='foo@bar.com', notes='Testing!',
                               type='bugfix')
        map(update.addPackageBuild, pkg_builds)
        assert update.builds[0].nvr == builds[0]
        assert update.builds[1].nvr == builds[1]
        assert update.title == ','.join(builds)
        assert update.release.name == 'fc7'
        assert release.updates[0] == update
        assert update.status == 'pending'
        assert update.type == 'bugfix'
        assert update.notes == 'Testing!'

    def test_encoding(self, buildnvr='yum-3.2.1-1.fc7'):
        update = PackageUpdate(title=buildnvr,
                               release=self.get_rel(),
                               submitter=u'Foo \xc3\xa9 Bar <foo@bar.com>',
                               notes=u'Testing \u2019t stuff',
                               type='security')
        assert update
        assert update.notes == u'Testing \u2019t stuff'
        assert update.submitter == u'Foo \xc3\xa9 Bar <foo@bar.com>'
        build = self.get_build(buildnvr)
        update.addPackageBuild(build)
        return update

    def _verify_updateinfo(self, update, repo):
        """ Verify that the updateinfo.xml.gz for a given repo matches the
            data for a given update
        """
        print "_verify_updateinfo(%s, %s)" % (update.nvr, repo)
        uinfo = UpdateMetadata()
        uinfo.add(repo)
        notice = uinfo.get_notice(update.nvr)
        assert notice
        assert notice['from'] == 'updates@fedora.com'
        assert notice['title'] == update.nvr
        assert notice['release'] == update.release.long_name
        assert notice['type'] == update.type
        assert notice['status'] == update.status
        assert notice['update_id'] == update.update_id
        assert notice['issued'] == str(update.date_pushed)
        assert notice['description'] == update.notes
        for collection in notice['pkglist']:
            numfiles = 0
            for archfiles in update.filelist.values():
                for file in archfiles:
                    numfiles += 1
            assert len(collection['packages']) == numfiles
            for pkg in collection['packages']:
                assert pkg['arch'] in update.filelist.keys()
                found = False
                for file in update.filelist[pkg['arch']]:
                    if pkg['filename'] in file:
                        found = True
                        break
                assert found

    #def test_push(self):
    #    from init import init_updates_stage
    #    push_stage = tempfile.mkdtemp('bodhi')
    #    update = self.get_update()
    #    init_updates_stage(stage_dir=push_stage)
#
#        update.request = 'push'
#        print "Pushing to temp stage: %s" % push_stage
#        for msg in update.run_request(stage=push_stage):
#            pass
#
#        # Verify that all files got pushed
#        repo = join(push_stage, update.get_repo())
#        self._assert_files(update, repo)
#
#        # Generate repo metadata
###        from bodhi.push import generate_metadata
#        for x in generate_metadata(update.release, update.status == 'testing',
#                                   stage=push_stage): pass
#
#        # Verify the updateinfo.xml.gz
#        for arch in update.filelist.keys():
#            self._verify_updateinfo(update, join(repo, arch, 'repodata',
#                                                 'updateinfo.xml.gz'))
#
#        # Move update from Testing to Final
#        update.request = 'move'
#        print "Pushing to temp stage: %s" % push_stage
#        for msg in update.run_request(stage=push_stage): pass
#
#        # Generate repo metadata
#        from bodhi.push import generate_metadata
#        for x in generate_metadata(update.release, update.status == 'testing',
#                                   stage=push_stage): pass
#
#        # Make sure we're in a different repo now
#        newrepo = join(push_stage, update.get_repo())
#        assert newrepo != repo
#
#        # Verify the updateinfo.xml.gz
#        for arch in update.filelist.keys():
#            self._verify_updateinfo(update, join(newrepo, arch, 'repodata',
#                                                 'updateinfo.xml.gz'))
#
#        # Make sure this update has been removed from the old updateinfo
#        for arch in update.filelist.keys():
#            uinfo = UpdateMetadata()
#            uinfo.add(join(repo, arch, 'repodata', 'updateinfo.xml.gz'))
#            notice = uinfo.get_notice(update.nvr)
#            assert notice == None
#
#        # Make sure files exist at new location
#        self._assert_files(update, newrepo)
#
#        # Make sure files don't exist at old location
#        try:
#            self._assert_files(update, repo)
#        except AssertionError:
#            # At this point, everything should be kosher
#            shutil.rmtree(push_stage)
#            return
#
#        assert False

    def test_email(self):
        from bodhi import mail
        update = self.get_update(name='yum-3.2.1-1.fc7')
        bug = self.get_bug()
        cve = self.get_cve()
        update.addBugzilla(bug)
        update.addCVE(cve)
        update.assign_id()
        templates = mail.get_template(update)
        assert templates
        assert templates[0][0] == u'[SECURITY] Fedora 7 Test Update: yum-3.2.1-1.fc7'
        assert templates[0][1] == u'--------------------------------------------------------------------------------\nFedora Test Update Notification\nFEDORA-2007-0001\nNone\n--------------------------------------------------------------------------------\n\nName        : yum\nProduct     : Fedora 7\nVersion     : 3.2.1\nRelease     : 1.fc7\nURL         : http://linux.duke.edu/yum/\nSummary     : RPM installer/updater\nDescription :\nYum is a utility that can check for and automatically download and\ninstall updated RPM packages. Dependencies are obtained and downloaded\nautomatically prompting the user as necessary.\n\n--------------------------------------------------------------------------------\nUpdate Information:\n\nfoobar\n--------------------------------------------------------------------------------\nChangeLog:\n\n* Thu Jun 21 2007 Seth Vidal <skvidal at fedoraproject.org> - 3.2.1-1\n- bump to 3.2.1\n--------------------------------------------------------------------------------\nReferences:\n\n  [ 1 ] Bug #1 - test bug\n        https://bugzilla.redhat.com/show_bug.cgi?id=1\n  [ 2 ] CVE-2007-0000\n        http://www.cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2007-0000\n--------------------------------------------------------------------------------\nUpdated packages:\n\n96380256a3f70e5ffb23892a5f4d1e6ffce3fe2e yum-3.2.1-1.fc7.src.rpm\nfc5cf7008a48fade1b6526050dbd8d34c3db5467 yum-updatesd-3.2.1-1.fc7.noarch.rpm\na4bbb1defcc3ff182e1a4cb7a32a2972562050e7 yum-3.2.1-1.fc7.noarch.rpm\n\nThis update can be installed with the "yum" update program.  Use \nsu -c \'yum update yum\' \nat the command line.  For more information, refer to "Managing Software\nwith yum", available at http://docs.fedoraproject.org/yum/.\n--------------------------------------------------------------------------------\n'

    def test_latest(self):
        update = self.get_update()
        assert update.builds[0].get_latest() == '/mnt/koji/packages/yum/3.2.0/1.fc7/src/yum-3.2.0-1.fc7.src.rpm'

    def test_changelog(self):
        import rpm
        from bodhi.util import rpm_fileheader
        update = self.get_update()
        oldh = rpm_fileheader(update.builds[0].get_latest())
        oldtime = oldh[rpm.RPMTAG_CHANGELOGTIME]
        text = oldh[rpm.RPMTAG_CHANGELOGTEXT]
        oldtime = oldtime[0]
        assert update.builds[0].get_changelog(oldtime) == '* Thu Jun 21 2007 Seth Vidal <skvidal at fedoraproject.org> - 3.2.1-1\n- bump to 3.2.1\n'


class TestBugzilla(testutil.DBTest):

    def get_model(self):
        return Bugzilla

    def test_creation(self):
        bug = Bugzilla(bz_id=1)

    def test_security_bug(self):
        bug = Bugzilla(bz_id=237533)
        assert bug.title == 'CVE-2007-2165: proftpd auth bypass vulnerability'
        assert bug.security == True
