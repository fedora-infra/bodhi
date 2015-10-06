# $Id: test_model.py,v 1.5 2006/12/31 09:10:25 lmacken Exp $

import rpm
import time
import turbogears

from turbogears import testutil, database, config
turbogears.update_config(configfile='bodhi.cfg', modulename='bodhi.config')
database.set_db_uri("sqlite:///:memory:")

from datetime import datetime, timedelta
from sqlobject import SQLObjectNotFound
from sqlobject.dberrors import IntegrityError
from yum.update_md import UpdateMetadata
from nose.tools import raises

from bodhi.jobs import nagmail
from bodhi.util import rpm_fileheader, get_nvr
from bodhi.mail import messages, get_template
from bodhi.model import (Release, Package, PackageUpdate, Bugzilla, CVE,
                         PackageBuild, Comment, User)
from bodhi.exceptions import (DuplicateEntryError, SQLiteIntegrityError,
                              PostgresIntegrityError)


YEAR = datetime.now().year

def get_rel():
    rel = None
    try:
        rel = Release.byName('fc7')
    except SQLObjectNotFound:
        rel = Release(name='fc7', long_name='Fedora 7', id_prefix='FEDORA',
                      dist_tag='dist-fc7')
    return rel


def get_pkg(name='TurboGears'):
    try:
        pkg = Package.byName(name)
    except SQLObjectNotFound:
        pkg = Package(name=name)
    return pkg


def get_build(self, nvr='TurboGears-1.0.2.2-2.fc7'):
    package = get_pkg('-'.join(nvr.split('-')[:-2]))
    package.committers = ['bobvila']
    try:
        build = PackageBuild.byNvr(nvr)
    except SQLObjectNotFound:
        build = PackageBuild(nvr=nvr, package=package)
    return build


class TestPackageUpdate(testutil.DBTest):

    def get_update(self, name='TurboGears-1.0.2.2-2.fc7'):
        update = PackageUpdate(title=name,
                               release=get_rel(),
                               submitter='foo@bar.com',
                               status='testing',
                               notes='foobar',
                               type='security')
        build = get_build(name)
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
                SQLiteIntegrityError, IntegrityError):
            return
        assert False

    # This is currently broken, since we cannot fake the identity
    #def test_mail_notices(self):
    #    """ Make sure all of our mail notices can expand properly """
    #    me = User(user_name='guest', display_name='Guest', password='guest')
    #    update = self.get_update()
    #    self.get_comment(update)
    #    for title, data in messages.items():
    #        assert data['body'] % data['fields'](update)

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
        assert update.updateid == '%s-%s-0001' % (update.release.id_prefix,
                                                  time.localtime()[0])
        assert update.date_pushed
        update = self.get_update(name='TurboGears-0.4.4-8.fc7')
        update.assign_id()
        assert update.updateid == '%s-%s-0002' % (update.release.id_prefix,
                                                  time.localtime()[0])

        # Create another update for another release that has the same
        # Release.id_prefix.  This used to trigger a bug that would cause
        # duplicate IDs across Fedora 10/11 updates.
        update = self.get_update(name='nethack-3.4.5-1.fc11')
        otherrel = Release(name='fc11', long_name='Fedora 11',
                           id_prefix='FEDORA', dist_tag='dist-fc11')
        update.release = otherrel
        update.assign_id()
        assert update.updateid == '%s-%s-0003' % (update.release.id_prefix,
                                                  time.localtime()[0])

        # 10k bug
        update.updateid = 'FEDORA-%s-9999' % YEAR
        newupdate = self.get_update(name='nethack-2.5.6-1.fc10')
        newupdate.assign_id()
        assert newupdate.updateid == 'FEDORA-%s-10000' % YEAR

        newerupdate = self.get_update(name='nethack-2.5.7-1.fc10')
        newerupdate.assign_id()
        assert newerupdate.updateid == 'FEDORA-%s-10001' % YEAR

        # test updates that were pushed at the same time.  assign_id should
        # be able to figure out which one has the highest id.
        now = datetime.utcnow()
        newupdate.date_pushed = now
        newerupdate.date_pushed = now

        newest = self.get_update(name='nethack-2.5.8-1.fc10')
        newest.assign_id()
        assert newest.updateid == 'FEDORA-%s-10002' % YEAR

    @raises(AssertionError)  # Ideally, this shouldn't happen, but it does.
    def test_duplicate_ids(self):
        older = self.get_update(name='nethack-2.5.8-1.fc10')
        older.assign_id()
        assert older.updateid == 'FEDORA-%s-0001' % YEAR, older.updateid

        newest = self.get_update(name='TurboGears-2.5.8-1.fc10')
        newest.assign_id()
        assert newest.updateid == 'FEDORA-%s-0002' % YEAR, newest.updateid

        # Now, pretend 'older' goes from testing->stable, and the date_pushed changes
        older.date_pushed = older.date_pushed + timedelta(days=7)

        up = self.get_update(name='kernel-2.6.9er-1.fc10')
        up.status = 'testing'
        up.assign_id()
        assert up.updateid == 'FEDORA-%s-1003' % YEAR, up.updateid

    def test_epel_id(self):
        """ Make sure we can handle id_prefixes that contain dashes. eg: FEDORA-EPEL """
        # Create a normal Fedora update first
        update = self.get_update()
        update.assign_id()
        assert update.updateid == 'FEDORA-%s-0001' % time.localtime()[0]

        update = self.get_update(name='TurboGears-2.1-1.el5')
        release = Release(name='EL-5', long_name='Fedora EPEL 5',
                          dist_tag='dist-5E-epel', id_prefix='FEDORA-EPEL')
        update.release = release
        update.assign_id()
        assert update.updateid == 'FEDORA-EPEL-%s-0001' % time.localtime()[0]

        update = self.get_update(name='TurboGears-2.2-1.el5')
        update.release = release
        update.assign_id()
        assert update.updateid == '%s-%s-0002' % (release.id_prefix,
                                                  time.localtime()[0]), update.updateid

    def test_url(self):
        update = self.get_update()
        print "URL = ", update.get_url()
        url = lambda update: '/%s' % update.title
        update.status = 'pending'
        assert update.get_url() == url(update)
        update.status = 'testing'
        assert update.get_url() == url(update)

        update.status = 'stable'
        assert update.get_url() == url(update)
        update.assign_id()
        #assert update.get_url() == '/%s/%s' % (update.release.name,
        #                                       update.updateid)
        assert update.get_url() == '/%s/%s' % (update.updateid, update.title)

    def test_multibuild(self):
        builds = ['yum-3.2.1-1.fc7', 'httpd-2.2.4-4.1.fc7']
        package_builds = []
        release = get_rel()
        update = PackageUpdate(title=','.join(builds), release=release,
                               submitter='foo@bar.com', notes='Testing!',
                               type='bugfix')
        for build in builds:
            nvr = get_nvr(build)
            pkg = Package(name=nvr[0])
            b = PackageBuild(nvr=build, package=pkg)
            package_builds.append(b)

        map(update.addPackageBuild, package_builds)

        assert update.builds[0].nvr == builds[0]
        assert update.builds[1].nvr == builds[1]
        assert update.title == ','.join(builds)
        assert update.release.name == 'fc7'
        assert release.updates[0] == update
        assert update.status == 'pending'
        assert update.type == 'bugfix'
        assert update.notes == 'Testing!'

        for build in package_builds:
            assert build.updates[0] == update

    def test_encoding(self, buildnvr='yum-3.2.1-1.fc7'):
        update = PackageUpdate(title=buildnvr,
                               release=get_rel(),
                               submitter=u'Foo \xc3\xa9 Bar <foo@bar.com>',
                               notes=u'Testing \u2019t stuff',
                               type='security')
        assert update
        assert update.notes == u'Testing \u2019t stuff'
        assert update.submitter == u'Foo \xc3\xa9 Bar <foo@bar.com>'
        build = get_build(buildnvr)
        update.addPackageBuild(build)
        update = PackageUpdate.byTitle(buildnvr)
        assert update.builds[0].updates[0] == update
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
        assert notice['update_id'] == update.updateid
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
        update = self.get_update(name='TurboGears-1.0.2.2-2.fc7')
        bug = self.get_bug()
        cve = self.get_cve()
        update.addBugzilla(bug)
        update.addCVE(cve)
        update.assign_id()

        def rpm_header():
            import rpm
            return {
                    rpm.RPMTAG_URL           : 'turbogears.org',
                    rpm.RPMTAG_NAME          : 'TurboGears',
                    rpm.RPMTAG_SUMMARY       : 'summary',
                    rpm.RPMTAG_VERSION       : '1.0.2.2',
                    rpm.RPMTAG_RELEASE       : '2.fc7',
                    rpm.RPMTAG_DESCRIPTION   : 'description',
                    rpm.RPMTAG_CHANGELOGTIME : 0,
                    rpm.RPMTAG_CHANGELOGTEXT : "foo",
            }

        def latest():
            return None

        # Monkey-patch some methods so we don't have to touch RPMs
        for build in update.builds:
            build.get_rpm_header = rpm_header
            build.get_latest = latest

        update.date_pushed = None
        templates = get_template(update)
        assert templates
        assert templates[0][0] == u'[SECURITY] Fedora 7 Test Update: TurboGears-1.0.2.2-2.fc7'
        assert templates[0][1] == u'--------------------------------------------------------------------------------\nFedora Test Update Notification\nFEDORA-%s-0001\nNone\n--------------------------------------------------------------------------------\n\nName        : TurboGears\nProduct     : Fedora 7\nVersion     : 1.0.2.2\nRelease     : 2.fc7\nURL         : turbogears.org\nSummary     : summary\nDescription :\ndescription\n\n--------------------------------------------------------------------------------\nUpdate Information:\n\nfoobar\n--------------------------------------------------------------------------------\nReferences:\n\n  [ 1 ] Bug #1 - None\n        https://bugzilla.redhat.com/show_bug.cgi?id=1\n  [ 2 ] CVE-2007-0000\n        http://www.cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2007-0000\n--------------------------------------------------------------------------------\n\nThis update can be installed with the "yum" update program.  Use\nsu -c \'yum --enablerepo=updates-testing update TurboGears\' at the command line.\nFor more information, refer to "Managing Software with yum",\navailable at http://docs.fedoraproject.org/yum/.\n\nAll packages are signed with the Fedora Project GPG key.  More details on the\nGPG keys used by the Fedora Project can be found at\nhttps://fedoraproject.org/keys\n--------------------------------------------------------------------------------\n' % YEAR, templates[0][1]

    def test_latest(self):
        update = self.get_update(name='yum-3.2.1-1.fc7')
        if config.get('buildsystem') == 'koji':
            latest = update.builds[0].get_latest()
            assert latest
            assert latest == '/mnt/koji/packages/yum/3.2.0/1.fc7/src/yum-3.2.0-1.fc7.src.rpm'

    def test_changelog(self):
        if config.get('buildsystem') != 'koji': return
        update = self.get_update(name='yum-3.2.1-1.fc7')
        oldh = rpm_fileheader(update.builds[0].get_latest())
        oldtime = oldh[rpm.RPMTAG_CHANGELOGTIME]
        text = oldh[rpm.RPMTAG_CHANGELOGTEXT]
        oldtime = oldtime[0]
        changelog = update.builds[0].get_changelog(oldtime)
        assert changelog == '* Thu Jun 21 2007 Seth Vidal <skvidal at fedoraproject.org> - 3.2.1-1\n- bump to 3.2.1\n'

    def test_unstable_karma(self):
        update = self.get_update()
        assert update.karma == 0
        assert update.status == 'testing'
        update.comment("foo", -1, 'foo')
        assert update.status == 'testing'
        assert update.karma == -1
        update.comment("bar", -1, 'bar')
        assert update.status == 'testing'
        assert update.karma == -2
        update.comment("biz", -1, 'biz')
        assert update.karma == -3
        assert update.status == 'obsolete'

    def test_stable_karma(self):
        update = self.get_update()
        assert update.karma == 0
        assert update.request is None
        update.comment("foo", 1, 'foo')
        assert update.karma == 1
        assert update.request is None
        update.comment("foo", 1, 'bar')
        assert update.karma == 2
        assert update.request is None
        update.comment("foo", 1, 'biz')
        assert update.karma == 3
        assert update.request == 'stable'

    def test_maintainers(self):
        update = self.get_update()
        assert 'bobvila' in update.get_maintainers()

    def test_build_tag(self):
        update = self.get_update()
        update.status = 'pending'
        assert update.get_build_tag() == "%s-updates-candidate" % update.release.dist_tag
        update.status = 'testing'
        assert update.get_build_tag() == "%s-updates-testing" % update.release.dist_tag
        update.status = 'stable'
        assert update.get_build_tag() == "%s-updates" % update.release.dist_tag
        update.status = 'obsolete'
        assert update.get_build_tag() == "%s-updates-candidate" % update.release.dist_tag

    def test_update_bugs(self):
        update = self.get_update()

        # try just adding bugs
        bugs = ['1234']
        update.update_bugs(bugs)
        assert len(update.bugs) == 1
        assert update.bugs[0].bz_id == 1234

        # try just removing
        bugs = []
        update.update_bugs(bugs)
        assert len(update.bugs) == 0
        try:
            Bugzilla.byBz_id(1234)
            assert False, "Stray bugzilla!"
        except SQLObjectNotFound:
            pass

        # Test new duplicate bugs
        bugs = ['1234', '1234']
        update.update_bugs(bugs)
        assert len(update.bugs) == 1

        # Try adding a new bug, and removing the rest
        bugs = ['4321']
        update.update_bugs(bugs)
        assert len(update.bugs) == 1
        assert update.bugs[0].bz_id == 4321
        try:
            Bugzilla.byBz_id(1234)
            assert False, "Stray bugzilla!"
        except SQLObjectNotFound:
            pass

    def test_request_complete(self):
        up = self.get_update()
        up.request = 'testing'
        up.status = 'pending'
        up.request_complete()
        assert not up.request
        assert up.pushed
        assert up.date_pushed
        assert up.status == 'testing'
        assert up.updateid == '%s-%s-0001' % (up.release.id_prefix,
                                              time.localtime()[0])

        up.request = 'stable'
        up.request_complete()
        assert not up.request
        assert up.status == 'stable'
        assert up.pushed
        assert up.date_pushed
        assert up.updateid == '%s-%s-0001' % (up.release.id_prefix,
                                              time.localtime()[0])

        up.request = 'obsolete'
        up.request_complete()
        assert not up.request
        assert up.status == 'obsolete'
        assert not up.pushed

    def test_status_comment(self):
        """ Make sure that we can properly add status comments to updates,
            and that they appear in the correct order. """
        up = self.get_update()
        assert len(up.comments) == 0
        up.status = 'testing'
        up.status_comment()
        assert len(up.comments) == 1
        assert 'bodhi' in up.comments[0].author, up.comments[0]
        assert up.comments[0].text == 'This update has been pushed to testing'
        up.status = 'stable'
        up.status_comment()
        assert len(up.comments) == 2
        assert up.comments[1].author == 'bodhi'
        assert up.comments[1].text == 'This update has been pushed to stable'
        up.status = 'obsolete'
        up.status_comment()
        assert len(up.comments) == 3
        assert up.comments[2].author == 'bodhi'
        assert up.comments[2].text == 'This update has been obsoleted'

    def test_anonymous_karma(self):
        """ Make sure that anonymous comments don't effect karma """
        update = self.get_update()
        update.comment('foo', karma=1, author='bob', anonymous=True)
        assert update.karma == 0

    def test_old_testing_nagmail(self):
        update = self.get_update()
        update.status = 'testing'
        update.status_comment()
        assert not update.nagged
        nagmail()
        assert not update.nagged
        update.comments[-1].timestamp = datetime.utcnow() - timedelta(days=20)
        update.date_pushed = datetime.utcnow() - timedelta(days=20)
        testutil.capture_log('bodhi.jobs')
        nagmail()
        log = testutil.get_log()
        assert "[old_testing] Nagging foo@bar.com about TurboGears-1.0.2.2-2.fc7" in log, log
        assert update.nagged, update.nagged
        assert 'old_testing' in update.nagged

        # Make sure it doesn't happen again
        testutil.capture_log('bodhi.jobs')
        nagmail()
        log = testutil.get_log()
        assert not "[old_testing] Nagging foo@bar.com about TurboGears-1.0.2.2-2.fc7" in log

        # Don't nag 6 days later
        newnag = update.nagged
        newnag['old_testing'] = update.nagged['old_testing'] - timedelta(days=6)
        update.nagged = newnag
        testutil.capture_log('bodhi.jobs')
        nagmail()
        log = testutil.get_log()
        assert not "[old_testing] Nagging foo@bar.com about TurboGears-1.0.2.2-2.fc7" in log

        # Nag again 1 week later
        newnag = update.nagged
        newnag['old_testing'] = update.nagged['old_testing'] - timedelta(days=7)
        update.nagged = newnag
        testutil.capture_log('bodhi.jobs')
        nagmail()
        log = testutil.get_log()
        assert "[old_testing] Nagging foo@bar.com about TurboGears-1.0.2.2-2.fc7" in log

    def test_old_pending_nagmail(self):
        update = self.get_update()
        update.status = 'pending'
        assert not update.nagged
        nagmail()
        assert not update.nagged
        update.date_submitted = datetime.utcnow() - timedelta(days=20)
        testutil.capture_log('bodhi.jobs')
        nagmail()
        log = testutil.get_log()
        assert "[old_pending] Nagging foo@bar.com about TurboGears-1.0.2.2-2.fc7" in log
        assert update.nagged, update.nagged
        assert 'old_pending' in update.nagged

        # Make sure it doesn't happen again
        testutil.capture_log('bodhi.jobs')
        nagmail()
        log = testutil.get_log()
        assert not "[old_pending] Nagging foo@bar.com about TurboGears-1.0.2.2-2.fc7" in log

        # Don't nag 6 days later
        newnag = update.nagged
        newnag['old_pending'] = update.nagged['old_pending'] - timedelta(days=6)
        update.nagged = newnag
        testutil.capture_log('bodhi.jobs')
        nagmail()
        log = testutil.get_log()
        assert not "[old_pending] Nagging foo@bar.com about TurboGears-1.0.2.2-2.fc7" in log

        # Nag again 1 week later
        newnag = update.nagged
        newnag['old_pending'] = update.nagged['old_pending'] - timedelta(days=7)
        update.nagged = newnag
        testutil.capture_log('bodhi.jobs')
        nagmail()
        log = testutil.get_log()
        assert "[old_pending] Nagging foo@bar.com about TurboGears-1.0.2.2-2.fc7" in log

    def test_pending_tag_property(self):
        update = self.get_update(name='TurboGears-1.0.2.2-2.fc7')
        assert update.release.candidate_tag == 'dist-fc7-updates-candidate'

    def test_testing_tag_property(self):
        update = self.get_update(name='TurboGears-1.0.2.2-2.fc7')
        assert update.release.testing_tag == 'dist-fc7-updates-testing'

    def test_stable_tag_property(self):
        update = self.get_update(name='TurboGears-1.0.2.2-2.fc7')
        assert update.release.stable_tag == 'dist-fc7-updates'

    def test_stable_tag_property_for_pending_release(self):
        update = self.get_update(name='TurboGears-1.0.2.2-2.fc7')
        update.release.locked = True
        assert update.release.stable_tag == 'dist-fc7'

    def test_testing_tag_property_for_pending_release(self):
        update = self.get_update(name='TurboGears-1.0.2.2-2.fc7')
        update.release.locked = True
        assert update.release.testing_tag == 'dist-fc7-updates-testing'

    def test_pending_tag_property_for_pending_release(self):
        update = self.get_update(name='TurboGears-1.0.2.2-2.fc7')
        update.release.locked = True
        assert update.release.candidate_tag == 'dist-fc7-updates-candidate'

    def _get_epel_release(self):
        rel = Release.select(Release.q.name=='EL5')
        if rel.count():
            rel = rel[0]
        else:
            rel = Release(name='EL5', long_name='Fedora EPEL 5', id_prefix='FEDORA-EPEL',
                          dist_tag='dist-5E-epel')
        return rel

    def test_epel_pending_tag_property(self):
        update = self.get_update(name='TurboGears-1.0.2.2-2.el5')
        update.release = self._get_epel_release()
        assert update.release.candidate_tag == 'dist-5E-epel-testing-candidate'

    def test_epel_testing_tag_property(self):
        update = self.get_update(name='TurboGears-1.0.2.2-2.el5')
        update.release = self._get_epel_release()
        assert update.release.testing_tag == 'dist-5E-epel-testing'

    def test_epel_stable_tag_property(self):
        update = self.get_update(name='TurboGears-1.0.2.2-2.el5')
        update.release = self._get_epel_release()
        assert update.release.stable_tag == 'dist-5E-epel'

    def test_epel7_tags(self):
        el7 = Release(name='EPEL-7', long_name='Fedora EPEL 7',
                      id_prefix='FEDORA-EPEL', dist_tag='epel7')
        assert el7.get_version() == 7
        assert el7.candidate_tag == 'epel7-testing-candidate'
        assert el7.testing_tag == 'epel7-testing'
        assert el7.stable_tag == 'epel7'
        assert el7.stable_repo == 'epel7'

    def test_bullets_in_notes(self):
        update = self.get_update(name='foo-1.2.3-4')
        update.notes = u'\xb7'
        u = PackageUpdate.byTitle('foo-1.2.3-4')
        assert u.notes == u'\xb7'

    def test_broken_notes(self):
        """ Ensure our note encoding works as expected """
        update = self.get_update(name='foo-1.2.3-4')
        update.notes_ = u'update to version 3.09\r\n*\xa0Allow regex replacement variables in HAO commands (Roger Bowler)\r\n*\xa0Prevent duplicate EQID (Gordon Bonorchis)\r\n*\xa0Permit concurrent read access to printer and punch files (Roger Bowler)\r\n*\xa0DFP zoned-conversion facility (Roger Bowler)\r\n*\xa0Execution-hint facility (Roger Bowler)\r\n*\xa0Miscellaneous-instruction-extensions facility (Roger Bowler)\r\n*\xa0Load-and-trap facility (Roger Bowler)\r\n*\xa0Fix for VSAM Extended Format (David "Fish" Trout)\r\n*\xa0APL\\360 2741 patch (Max H. Parke)\r\n*\xa0Fix interval timer repeating interrupt (Ivan Warren, Kevin Leonard)\r\n*\xa0Corrections to build procedures (Mike Frysinger, Dan Horak)\r\n*\xa0Miscellaneous bug fixes (Roger Bowler)\r\n'
        assert False, update.notes
        assert update.notes

    def test_utf8_email(self):
        update = self.get_update(name='TurboGears-1.0.2.2-2.fc7')
        bug = self.get_bug()
        cve = self.get_cve()
        update.addBugzilla(bug)
        update.addCVE(cve)
        update.assign_id()

        def rpm_header():
            import rpm
            return {
                    rpm.RPMTAG_URL           : 'turbogears.org',
                    rpm.RPMTAG_NAME          : 'TurboGears',
                    rpm.RPMTAG_SUMMARY       : 'summary',
                    rpm.RPMTAG_VERSION       : '1.0.2.2',
                    rpm.RPMTAG_RELEASE       : '2.fc7',
                    rpm.RPMTAG_DESCRIPTION   : 'Z\xe2\x80\x99s',
                    rpm.RPMTAG_CHANGELOGTIME : 0,
                    rpm.RPMTAG_CHANGELOGTEXT : "foo",
            }

        def latest():
            return None

        # Monkey-patch some methods so we don't have to touch RPMs
        for build in update.builds:
            build.get_rpm_header = rpm_header
            build.get_latest = latest

        update.date_pushed = None
        templates = get_template(update)
        assert templates
        assert templates[0][0] == u'[SECURITY] Fedora 7 Test Update: TurboGears-1.0.2.2-2.fc7'
        assert templates[0][1] == u'--------------------------------------------------------------------------------\nFedora Test Update Notification\nFEDORA-%s-0001\nNone\n--------------------------------------------------------------------------------\n\nName        : TurboGears\nProduct     : Fedora 7\nVersion     : 1.0.2.2\nRelease     : 2.fc7\nURL         : turbogears.org\nSummary     : summary\nDescription :\nZ\u2019s\n\n--------------------------------------------------------------------------------\nUpdate Information:\n\nfoobar\n--------------------------------------------------------------------------------\nReferences:\n\n  [ 1 ] Bug #1 - None\n        https://bugzilla.redhat.com/show_bug.cgi?id=1\n  [ 2 ] CVE-2007-0000\n        http://www.cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2007-0000\n--------------------------------------------------------------------------------\n\nThis update can be installed with the "yum" update program.  Use\nsu -c \'yum --enablerepo=updates-testing update TurboGears\' at the command line.\nFor more information, refer to "Managing Software with yum",\navailable at http://docs.fedoraproject.org/yum/.\n\nAll packages are signed with the Fedora Project GPG key.  More details on the\nGPG keys used by the Fedora Project can be found at\nhttps://fedoraproject.org/keys\n--------------------------------------------------------------------------------\n' % YEAR

    def test_disable_autokarma_on_autoqa_failure(self):
        """
        Ensure that karma automatism gets disabled upon AutoQA test failures.
        """
        update = self.get_update()
        assert update.karma == 0
        assert update.stable_karma == 3
        assert update.status == 'testing'
        update.comment("foo", 1, 'tester1')
        assert update.karma == 1
        update.comment("foo", 1, 'tester2')
        assert update.karma == 2
        assert update.stable_karma == 3
        update.comment("FAILED", 0, 'autoqa')
        assert update.comments[-1].text == config.get('stablekarma_disabled_comment')
        assert update.stable_karma == 0
        update.comment("foo", 1, 'tester3')
        assert update.karma == 3
        assert update.request != 'stable'
        assert update.stable_karma == 0

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


class TestRelease(testutil.DBTest):

    def get_release(self):
        return Release(name='fc7', long_name='Fedora 7', id_prefix='FEDORA',
                       dist_tag='dist-fc7')

    def test_creation(self):
        rel = self.get_release()
        assert rel
        assert rel.name == 'fc7'
        assert rel.long_name == 'Fedora 7'
        assert rel.id_prefix == 'FEDORA'
        assert rel.dist_tag == 'dist-fc7'

    def test_get_version(self):
        rel = self.get_release()
        assert rel.get_version() == 7

        # test multi-digit releases
        rel.name = 'F10'
        rel.long_name = 'Fedora 10'
        assert rel.get_version() == 10, rel.get_version()

        rel.name = 'F100'
        rel.long_name = 'Fedora 100'
        assert rel.get_version() == 100, rel.get_version()


class TestPackage(testutil.DBTest):

    def get_model(self):
        return Package

    def get_build(self, nvr='TurboGears-1.0.2.2-2.fc7'):
        package = get_pkg('-'.join(nvr.split('-')[:-2]))
        build = PackageBuild(nvr=nvr, package=package)
        return build

    def get_update(self, name='TurboGears-1.0.2.2-2.fc7'):
        update = PackageUpdate(title=name,
                               release=get_rel(),
                               submitter='foo@bar.com',
                               status='testing',
                               notes='foobar',
                               type='security')
        build = get_build(name)
        update.addPackageBuild(build)
        return update

    def test_update_generator(self):
        update = self.get_update()
        pkg = update.builds[0].package
        assert len([up for up in pkg.updates()]) == 1


class TestPackageBuild(testutil.DBTest):

    def test_url(self):
        nvr = 'TurboGears-4.0.3.3-1.fc9'
        build = PackageBuild(nvr=nvr, package=0)
        assert build.get_url() == '/' + nvr
