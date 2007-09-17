# $Id: test_model.py,v 1.5 2006/12/31 09:10:25 lmacken Exp $

import turbogears
from turbogears import testutil, database, config
turbogears.update_config(configfile='dev.cfg', modulename='bodhi.config')
database.set_db_uri("sqlite:///:memory:")

import os
import sys
import time
import shutil
import tempfile

from os.path import join, exists, basename
from bodhi.util import mkmetadatadir
from bodhi.model import (Release, Package, PackageUpdate, Bugzilla, CVE,
                         PackageBuild, Comment, User)
from bodhi.exceptions import (DuplicateEntryError, SQLiteIntegrityError,
                              PostgresIntegrityError, RPMNotFound)

from yum.update_md import UpdateMetadata

class TestPackageUpdate(testutil.DBTest):

    def get_pkg(self, name='TurboGears'):
        return Package(name=name)

    def get_rel(self):
        rel = Release(name='fc7', long_name='Fedora 7', id_prefix='FEDORA',
                      dist_tag='dist-fc7')
        return rel

    def get_build(self, nvr='TurboGears-1.0.2.2-2.fc7'):
        package = self.get_pkg('-'.join(nvr.split('-')[:-2]))
        build = PackageBuild(nvr=nvr, package=package)
        return build

    def get_update(self, name='TurboGears-1.0.2.2-2.fc7'):
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

    def get_comment(self, update):
        return Comment(author='bodhi', text='foobar', karma=0, update=update)

    def test_dupe(self):
        update1 = self.get_update()
        try:
            update2 = self.get_update()
        except (DuplicateEntryError, PostgresIntegrityError,
                SQLiteIntegrityError):
            return
        assert False

    def test_mail_notices(self):
        """ Make sure all of our mail notices can expand properly """
        from bodhi.mail import messages
        me = User(user_name='guest', display_name='Guest')
        update = self.get_update()
        self.get_comment(update)
        for title, data in messages.items():
            assert data['body'] % data['fields'](update)

    def test_creation(self):
        update = self.get_update()
        assert update.title == 'TurboGears-1.0.2.2-2.fc7'
        assert update.builds[0].package.name == 'TurboGears'
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

    def test_email(self):
        from bodhi import mail
        update = self.get_update(name='TurboGears-1.0.2.2-2.fc7')
        bug = self.get_bug()
        cve = self.get_cve()
        update.addBugzilla(bug)
        update.addCVE(cve)
        update.assign_id()
        print update
        try:
            templates = mail.get_template(update)
        except RPMNotFound:
            # We're assuming we can find any real packages if we're a
            # development instance.. so just skip this test for now
            if config.get('buildsystem') == 'dev':
                return
            else:
                raise
        assert templates
        from pprint import pprint
        pprint(templates)
        assert templates[0][0] == u'[SECURITY] Fedora 7 Test Update: TurboGears-1.0.2.2-2.fc7'
        assert templates[0][1] == u'--------------------------------------------------------------------------------\nFedora Test Update Notification\nFEDORA-2007-0001\nNone\n--------------------------------------------------------------------------------\n\nName        : TurboGears\nProduct     : Fedora 7\nVersion     : 1.0.2.2\nRelease     : 2.fc7\nURL         : http://www.turbogears.org\nSummary     : Back-to-front web development in Python\nDescription :\nTurboGears brings together four major pieces to create an\neasy to install, easy to use web megaframework. It covers\neverything from front end (MochiKit JavaScript for the browser,\nKid for templates in Python) to the controllers (CherryPy) to\nthe back end (SQLObject).\n\nThe TurboGears project is focused on providing documentation\nand integration with these tools without losing touch\nwith the communities that already exist around those tools.\n\nTurboGears is easy to use for a wide range of web applications.\n\n--------------------------------------------------------------------------------\nUpdate Information:\n\nfoobar\n--------------------------------------------------------------------------------\nReferences:\n\n  [ 1 ] Bug #1 - test bug\n        https://bugzilla.redhat.com/show_bug.cgi?id=1\n  [ 2 ] CVE-2007-0000\n        http://www.cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2007-0000\n--------------------------------------------------------------------------------\nUpdated packages:\n\n57e80ee8eb6d666c79c498e0b2efecd74ab52063 TurboGears-1.0.2.2-2.fc7.src.rpm\n85e05a4d52143ce38f43f7fdd244251e18f9d408 TurboGears-1.0.2.2-2.fc7.noarch.rpm\n\nThis update can be installed with the "yum" update program.  Use \nsu -c \'yum update TurboGears\' \nat the command line.  For more information, refer to "Managing Software\nwith yum", available at http://docs.fedoraproject.org/yum/.\n--------------------------------------------------------------------------------\n' or templates[0][1] == u'--------------------------------------------------------------------------------\nFedora Test Update Notification\nFEDORA-2007-0001\nNone\n--------------------------------------------------------------------------------\n\nName        : TurboGears\nProduct     : Fedora 7\nVersion     : 1.0.2.2\nRelease     : 2.fc7\nURL         : http://www.turbogears.org\nSummary     : Back-to-front web development in Python\nDescription :\nTurboGears brings together four major pieces to create an\neasy to install, easy to use web megaframework. It covers\neverything from front end (MochiKit JavaScript for the browser,\nKid for templates in Python) to the controllers (CherryPy) to\nthe back end (SQLObject).\n\nThe TurboGears project is focused on providing documentation\nand integration with these tools without losing touch\nwith the communities that already exist around those tools.\n\nTurboGears is easy to use for a wide range of web applications.\n\n--------------------------------------------------------------------------------\nUpdate Information:\n\nfoobar\n--------------------------------------------------------------------------------\nReferences:\n\n  [ 1 ] Bug #1 - None\n        https://bugzilla.redhat.com/show_bug.cgi?id=1\n  [ 2 ] CVE-2007-0000\n        http://www.cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2007-0000\n--------------------------------------------------------------------------------\nUpdated packages:\n\n57e80ee8eb6d666c79c498e0b2efecd74ab52063 TurboGears-1.0.2.2-2.fc7.src.rpm\n85e05a4d52143ce38f43f7fdd244251e18f9d408 TurboGears-1.0.2.2-2.fc7.noarch.rpm\n\nThis update can be installed with the "yum" update program.  Use \nsu -c \'yum update TurboGears\' \nat the command line.  For more information, refer to "Managing Software\nwith yum", available at http://docs.fedoraproject.org/yum/.\n--------------------------------------------------------------------------------\n'

    def test_latest(self):
        update = self.get_update(name='yum-3.2.1-1.fc7')
        if config.get('buildsystem') == 'koji':
            latest = update.builds[0].get_latest()
            assert latest
            assert latest == '/mnt/koji/packages/yum/3.2.0/1.fc7/src/yum-3.2.0-1.fc7.src.rpm'

    def test_changelog(self):
        if config.get('buildsystem') != 'koji': return
        import rpm
        from bodhi.util import rpm_fileheader
        update = self.get_update(name='yum-3.2.1-1.fc7')
        oldh = rpm_fileheader(update.builds[0].get_latest())
        oldtime = oldh[rpm.RPMTAG_CHANGELOGTIME]
        text = oldh[rpm.RPMTAG_CHANGELOGTEXT]
        oldtime = oldtime[0]
        changelog = update.builds[0].get_changelog(oldtime)
        assert changelog == '* Thu Jun 21 2007 Seth Vidal <skvidal at fedoraproject.org> - 3.2.1-1\n- bump to 3.2.1\n'


class TestBugzilla(testutil.DBTest):

    def get_model(self):
        return Bugzilla

    def test_creation(self):
        bug = Bugzilla(bz_id=1)

    def test_security_bug(self):
        bug = Bugzilla(bz_id=237533)
        assert bug
        if config.get('bodhi_password'):
            assert bug.title == 'CVE-2007-2165: proftpd auth bypass vulnerability'
            assert bug.security == True
        assert bug.bz_id == 237533
