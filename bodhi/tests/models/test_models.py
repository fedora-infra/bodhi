# -*- coding: utf-8 -*-

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""Test suite for the Bodhi models"""

import time
import cornice
import mock

from nose.tools import eq_, raises
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from pyramid.testing import DummyRequest

from bodhi import models as model, buildsys, mail
from bodhi.models import (UpdateStatus, UpdateType, UpdateRequest,
                          UpdateSeverity, UpdateSuggestion, ReleaseState,
                          BugKarma)
from bodhi.tests.models import ModelTest
from bodhi.config import config
from bodhi.exceptions import BodhiException


class DummyUser(object):
    name = 'guest'


class TestRelease(ModelTest):
    """Unit test case for the ``Release`` model."""
    klass = model.Release
    attrs = dict(
        name=u"F11",
        long_name=u"Fedora 11",
        id_prefix=u"FEDORA",
        version=u'11',
        branch=u'f11',
        dist_tag=u"dist-f11",
        stable_tag=u"dist-f11-updates",
        testing_tag=u"dist-f11-updates-testing",
        candidate_tag=u"dist-f11-updates-candidate",
        pending_testing_tag=u"dist-f11-updates-testing-pending",
        pending_stable_tag=u"dist-f11-updates-pending",
        override_tag=u"dist-f11-override",
        state=model.ReleaseState.current,
        )

    def test_version_int(self):
        eq_(self.obj.version_int, 11)

    def test_all_releases(self):
        releases = model.Release.all_releases(self.db)
        state = ReleaseState.from_string(releases.keys()[0])
        assert 'long_name' in releases[state.value][0], releases
        # Make sure it's the same cached object
        assert releases is model.Release.all_releases(self.db)


class MockWiki(object):
    """ Mocked simplemediawiki.MediaWiki class. """
    def __init__(self, response):
        self.response = response
        self.query = None

    def __call__(self, *args, **kwargs):
        return self

    def call(self, query):
        self.query = query
        return self.response


class TestPackage(ModelTest):
    """Unit test case for the ``Package`` model."""
    klass = model.Package
    attrs = dict(name=u"TurboGears")

    def do_get_dependencies(self):
        return dict(
            committers=[model.User(name=u'lmacken')]
        )

    def test_wiki_test_cases(self):
        """Test querying the wiki for test cases"""

        # Mock out mediawiki so we don't do network calls in our tests
        import simplemediawiki
        response = {
            'query': {
                'categorymembers': [{
                    'title': u'Fake test case',
                }],
            }
        }
        original = simplemediawiki.MediaWiki
        simplemediawiki.MediaWiki = MockWiki(response)

        # Now, our actual test.
        try:
            config['query_wiki_test_cases'] = True
            pkg = model.Package(name=u'gnome-shell')
            pkg.fetch_test_cases(self.db)
            assert pkg.test_cases
        finally:
            # Restore things
            simplemediawiki.MediaWiki = original

    def test_committers(self):
        assert self.obj.committers[0].name == u'lmacken'


class TestBuild(ModelTest):
    """Unit test case for the ``Build`` model."""
    klass = model.Build
    attrs = dict(
        nvr=u"TurboGears-1.0.8-3.fc11",
        inherited=False,
        )

    def do_get_dependencies(self):
        return dict(
                release=model.Release(**TestRelease.attrs),
                package=model.Package(**TestPackage.attrs),
                )

    def test_release_relation(self):
        eq_(self.obj.release.name, u"F11")
        eq_(len(self.obj.release.builds), 1)
        eq_(self.obj.release.builds[0], self.obj)

    def test_package_relation(self):
        eq_(self.obj.package.name, u"TurboGears")
        eq_(len(self.obj.package.builds), 1)
        eq_(self.obj.package.builds[0], self.obj)

    def test_epoch(self):
        self.obj.epoch = '1'
        eq_(self.obj.evr, ("1", "1.0.8", "3.fc11"))

    #def test_latest(self):
    #    # Note, this build is hardcoded in bodhi/buildsys.py:DevBuildsys
    #    eq_(self.obj.get_latest(), u"TurboGears-1.0.8-7.fc11")

    #def test_latest_with_eq_build(self):
    #    self.obj.nvr = 'TurboGears-1.0.8-7.fc11'
    #    eq_(self.obj.get_latest(), None)

    #def test_latest_with_newer_build(self):
    #    self.obj.nvr = 'TurboGears-1.0.8-8.fc11'
    #    eq_(self.obj.get_latest(), None)

    def test_url(self):
        eq_(self.obj.get_url(), u'/TurboGears-1.0.8-3.fc11')

    #def test_get_latest(self):
    #    eq_(self.obj.get_latest(), None)


class TestUpdate(ModelTest):
    """Unit test case for the ``Update`` model."""
    klass = model.Update
    attrs = dict(
        title=u'TurboGears-1.0.8-3.fc11',
        type=UpdateType.security,
        status=UpdateStatus.pending,
        request=UpdateRequest.testing,
        severity=UpdateSeverity.medium,
        suggest=UpdateSuggestion.reboot,
        stable_karma=3,
        unstable_karma=-3,
        close_bugs=True,
        notes=u'foobar',
        karma=0,
        )

    def do_get_dependencies(self):
        release = model.Release(**TestRelease.attrs)
        return dict(
            builds=[model.Build(nvr=u'TurboGears-1.0.8-3.fc11',
                                  package=model.Package(**TestPackage.attrs),
                                  release=release)],
            bugs=[model.Bug(bug_id=1), model.Bug(bug_id=2)],
            cves=[model.CVE(cve_id=u'CVE-2009-0001')],
            release=release,
            user=model.User(name=u'lmacken')
            )

    def get_update(self, name=u'TurboGears-1.0.8-3.fc11'):
        """Return an Update instance for testing."""
        attrs = self.attrs.copy()
        attrs['title'] = name
        pkg = self.db.query(model.Package) \
                .filter_by(name=u'TurboGears').one()
        rel = self.db.query(model.Release) \
                .filter_by(name=u'F11').one()
        attrs.update(dict(
            builds=[model.Build(nvr=name, package=pkg, release=rel)],
            release=rel,
            ))
        return self.klass(**attrs)

    def test_builds(self):
        eq_(len(self.obj.builds), 1)
        eq_(self.obj.builds[0].nvr, u'TurboGears-1.0.8-3.fc11')
        eq_(self.obj.builds[0].release.name, u'F11')
        eq_(self.obj.builds[0].package.name, u'TurboGears')

    @mock.patch('bodhi.models.models.bugtracker.close')
    @mock.patch('bodhi.models.models.bugtracker.comment')
    def test_modify_bugs_stable_close(self, comment, close):
        """Test the modify_bugs() method with a stable status and with close_bugs set to True."""
        update = self.get_update()
        bug_1 = model.Bug(bug_id=1)
        bug_2 = model.Bug(bug_id=2)
        update.bugs.append(bug_1)
        update.bugs.append(bug_2)
        update.close_bugs = True
        update.status = UpdateStatus.stable

        update.modify_bugs()

        # The comment call shouldn't have been made, since the comment should be included with the
        # call to close().
        eq_(comment.call_count, 0)
        # Make sure close() was called correctly.
        eq_([c[1][0] for c in close.mock_calls], [1, 2])
        eq_(all(
            ['to the Fedora 11 stable repository' in c[2]['comment'] for c in close.mock_calls]),
            True)
        eq_(all(
            [c[2]['versions']['TurboGears'] == 'TurboGears-1.0.8-3.fc11'
                for c in close.mock_calls]),
            True)

    @mock.patch('bodhi.models.models.bugtracker.close')
    @mock.patch('bodhi.models.models.bugtracker.comment')
    def test_modify_bugs_stable_no_close(self, comment, close):
        """Test the modify_bugs() method with a stable status and with close_bugs set to False."""
        update = self.get_update()
        bug_1 = model.Bug(bug_id=1)
        bug_2 = model.Bug(bug_id=2)
        update.bugs.append(bug_1)
        update.bugs.append(bug_2)
        update.close_bugs = False
        update.status = UpdateStatus.stable

        update.modify_bugs()

        # Make sure bugs number 1 and 2 were commented on correctly.
        eq_([c[1][0] for c in comment.mock_calls], [1, 2])
        eq_(all(
            ['pushed to the Fedora 11 stable repository' in c[1][1] for c in comment.mock_calls]),
            True)
        # No bugs should have been closed
        eq_(close.call_count, 0)

    def test_unpush_build(self):
        eq_(len(self.obj.builds), 1)
        b = self.obj.builds[0]
        release = self.obj.release
        koji = buildsys.get_session()
        koji.clear()
        koji.__tagged__[b.nvr] = [release.testing_tag,
                                  release.pending_testing_tag,
                                  # Add an unknown tag that we shouldn't touch
                                  release.dist_tag + '-compose']
        self.obj.builds[0].unpush(koji)
        eq_(koji.__moved__, [(u'dist-f11-updates-testing', u'dist-f11-updates-candidate', u'TurboGears-1.0.8-3.fc11')])
        eq_(koji.__untag__, [(u'dist-f11-updates-testing-pending', u'TurboGears-1.0.8-3.fc11')])

    def test_title(self):
        eq_(self.obj.title, u'TurboGears-1.0.8-3.fc11')

    def test_pkg_str(self):
        """ Ensure str(pkg) is correct """
        eq_(str(self.obj.builds[0].package), '================================================================================\n     TurboGears\n================================================================================\n\n Pending Updates (1)\n    o TurboGears-1.0.8-3.fc11\n')

    def test_bugstring(self):
        eq_(self.obj.get_bugstring(), u'1 2')

    def test_cvestring(self):
        eq_(self.obj.get_cvestring(), u'CVE-2009-0001')

    def test_assign_alias(self):
        update = self.obj
        with mock.patch(target='uuid.uuid4', return_value='wat'):
            update.assign_alias()
        year = time.localtime()[0]
        idx = 'a3bbe1a8f2'
        eq_(update.alias, u'%s-%s-%s' % (update.release.id_prefix, year, idx))

        update = self.get_update(name=u'TurboGears-0.4.4-8.fc11')
        with mock.patch(target='uuid.uuid4', return_value='wat2'):
            update.assign_alias()
        idx = '016462d41f'
        eq_(update.alias, u'%s-%s-%s' % (update.release.id_prefix, year, idx))

        ## Create another update for another release that has the same
        ## Release.id_prefix.  This used to trigger a bug that would cause
        ## duplicate IDs across Fedora 10/11 updates.
        update = self.get_update(name=u'nethack-3.4.5-1.fc10')
        otherrel = model.Release(name=u'fc10', long_name=u'Fedora 10',
                                 id_prefix=u'FEDORA', dist_tag=u'dist-fc10',
                                 stable_tag=u'dist-fc10-updates',
                                 testing_tag=u'dist-fc10-updates-testing',
                                 candidate_tag=u'dist-fc10-updates-candidate',
                                 pending_testing_tag=u'dist-fc10-updates-testing-pending',
                                 pending_stable_tag=u'dist-fc10-updates-pending',
                                 override_tag=u'dist-fc10-override',
                                 branch=u'fc10', version=u'10')
        update.release = otherrel
        with mock.patch(target='uuid.uuid4', return_value='wat3'):
            update.assign_alias()
        idx = '0efffa96f7'
        eq_(update.alias, u'%s-%s-%s' % (update.release.id_prefix, year, idx))

        newest = self.get_update(name=u'nethack-2.5.8-1.fc10')
        with mock.patch(target='uuid.uuid4', return_value='wat4'):
            newest.assign_alias()
        idx = '0efffa96f7'
        eq_(update.alias, u'%s-%s-%s' % (update.release.id_prefix, year, idx))

    def test_epel_id(self):
        """ Make sure we can handle id_prefixes that contain dashes.
        eg: FEDORA-EPEL
        """
        # Create a normal Fedora update first
        update = self.obj
        with mock.patch(target='uuid.uuid4', return_value='wat'):
            update.assign_alias()
        idx = 'a3bbe1a8f2'
        eq_(update.alias, u'FEDORA-%s-%s' % (time.localtime()[0], idx))

        update = self.get_update(name=u'TurboGears-2.1-1.el5')
        release = model.Release(name=u'EL-5', long_name=u'Fedora EPEL 5',
                          id_prefix=u'FEDORA-EPEL', dist_tag=u'dist-5E-epel',
                          stable_tag=u'dist-5E-epel',
                          testing_tag=u'dist-5E-epel-testing',
                          candidate_tag=u'dist-5E-epel-testing-candidate',
                          pending_testing_tag=u'dist-5E-epel-testing-pending',
                          pending_stable_tag=u'dist-5E-epel-pending',
                          override_tag=u'dist-5E-epel-override',
                          branch=u'el5', version=u'5')
        update.release = release
        idx = 'a3bbe1a8f2'
        with mock.patch(target='uuid.uuid4', return_value='wat'):
            update.assign_alias()
        eq_(update.alias, u'FEDORA-EPEL-%s-%s' % (time.localtime()[0], idx))

        update = self.get_update(name=u'TurboGears-2.2-1.el5')
        update.release = release
        idx = '016462d41f'
        with mock.patch(target='uuid.uuid4', return_value='wat2'):
            update.assign_alias()
        eq_(update.alias, u'%s-%s-%s' % (
            release.id_prefix, time.localtime()[0], idx))

    @raises(IntegrityError)
    def test_dupe(self):
        self.get_update()
        self.get_update()

    @mock.patch('bodhi.notifications.publish')
    def test_stable_karma(self, publish):
        update = self.obj
        update.request = None
        update.status = UpdateStatus.testing
        eq_(update.karma, 0)
        eq_(update.request, None)
        update.comment(self.db, u"foo", 1, u'foo')
        eq_(update.karma, 1)
        eq_(update.request, None)
        update.comment(self.db, u"foo", 1, u'bar')
        eq_(update.karma, 2)
        eq_(update.request, None)
        update.comment(self.db, u"foo", 1, u'biz')
        eq_(update.karma, 3)
        eq_(update.request, UpdateRequest.stable)
        publish.assert_called_with(topic='update.comment', msg=mock.ANY)
        #publish.assert_called_with(topic='update.request.stable', msg=mock.ANY)

    @mock.patch('bodhi.notifications.publish')
    def test_unstable_karma(self, publish):
        update = self.obj
        update.status = UpdateStatus.testing
        eq_(update.karma, 0)
        eq_(update.status, UpdateStatus.testing)
        update.comment(self.db, u"foo", -1, u'foo')
        eq_(update.status, UpdateStatus.testing)
        eq_(update.karma, -1)
        update.comment(self.db, u"bar", -1, u'bar')
        eq_(update.status, UpdateStatus.testing)
        eq_(update.karma, -2)
        update.comment(self.db, u"biz", -1, u'biz')
        eq_(update.karma, -3)
        eq_(update.status, UpdateStatus.obsolete)
        publish.assert_called_with(topic='update.comment', msg=mock.ANY)

    def test_update_bugs(self):
        update = self.obj
        eq_(len(update.bugs), 2)
        session = self.db

        # try just adding bugs
        bugs = ['1234']
        update.update_bugs(bugs, session)
        eq_(len(update.bugs), 1)
        eq_(update.bugs[0].bug_id, 1234)

        # try just removing
        bugs = []
        update.update_bugs(bugs, session)
        eq_(len(update.bugs), 0)
        eq_(self.db.query(model.Bug)
                .filter_by(bug_id=1234).first(), None)

        # Test new duplicate bugs
        bugs = ['1234', '1234']
        update.update_bugs(bugs, session)
        assert len(update.bugs) == 1

        # Try adding a new bug, and removing the rest
        bugs = ['4321']
        update.update_bugs(bugs, session)
        assert len(update.bugs) == 1
        assert update.bugs[0].bug_id == 4321
        eq_(self.db.query(model.Bug)
                .filter_by(bug_id=1234).first(), None)

        # Try removing a bug when it already has BugKarma
        karma = BugKarma(bug_id=4321, karma=1)
        self.db.add(karma)
        self.db.flush()
        bugs = ['5678']
        update.update_bugs(bugs, session)
        assert len(update.bugs) == 1
        assert update.bugs[0].bug_id == 5678
        eq_(self.db.query(model.Bug)
                .filter_by(bug_id=4321).count(), 1)

    def test_unicode_bug_title(self):
        bug = self.obj.bugs[0]
        bug.title = u'foo\xe9bar'
        from bodhi.util import bug_link
        link = bug_link(None, bug)
        eq_(link, u"<a target='_blank' href='https://bugzilla.redhat.com/show_bug.cgi?id=1'>#1</a> foo\xe9bar")

    def test_set_request_untested_stable(self):
        """
        Ensure that we can't submit an update for stable if it hasn't met the
        minimum testing requirements.
        """
        req = DummyRequest(user=DummyUser())
        req.errors = cornice.Errors()
        req.koji = buildsys.get_session()
        eq_(self.obj.status, UpdateStatus.pending)
        try:
            self.obj.set_request(self.db, UpdateRequest.stable, req.user.name)
            assert False
        except BodhiException, e:
            pass
        eq_(self.obj.request, UpdateRequest.testing)
        eq_(self.obj.status, UpdateStatus.pending)
        eq_(e.message, config.get('not_yet_tested_msg'))

    @mock.patch('bodhi.notifications.publish')
    def test_set_request_stable_after_week_in_testing(self, publish):
        req = DummyRequest()
        req.errors = cornice.Errors()
        req.koji = buildsys.get_session()
        req.user = model.User(name='bob')

        self.obj.status = UpdateStatus.testing
        self.obj.request = None

        # Pretend it's been in testing for a week
        self.obj.comment(
            self.db, u'This update has been pushed to testing.', author=u'bodhi')
        self.obj.date_testing = self.obj.comments[-1].timestamp - timedelta(days=7)
        eq_(self.obj.days_in_testing, 7)
        eq_(self.obj.meets_testing_requirements, True)

        self.obj.set_request(self.db, UpdateRequest.stable, req)
        eq_(self.obj.request, UpdateRequest.stable)
        eq_(len(req.errors), 0)
        publish.assert_called_once_with(
            topic='update.request.stable', msg=mock.ANY)

    @mock.patch('bodhi.notifications.publish')
    def test_set_meets_then_met_requirements(self, publish):
        req = DummyRequest()
        req.errors = cornice.Errors()
        req.koji = buildsys.get_session()
        req.user = model.User(name='bob')

        self.obj.status = UpdateStatus.testing
        self.obj.request = None

        # Pretend it's been in testing for a week
        self.obj.comment(
            self.db, u'This update has been pushed to testing.', author=u'bodhi')
        self.obj.date_testing = self.obj.comments[-1].timestamp - timedelta(days=7)
        eq_(self.obj.days_in_testing, 7)
        eq_(self.obj.meets_testing_requirements, True)
        eq_(self.obj.met_testing_requirements, False)

        text = config.get('testing_approval_msg') % self.obj.days_in_testing
        self.obj.comment(self.db, text, author=u'bodhi')

        eq_(self.obj.meets_testing_requirements, True)
        eq_(self.obj.met_testing_requirements, True)

    @mock.patch('bodhi.notifications.publish')
    def test_set_request_obsolete(self, publish):
        req = DummyRequest(user=DummyUser())
        req.errors = cornice.Errors()
        eq_(self.obj.status, UpdateStatus.pending)
        self.obj.set_request(self.db, UpdateRequest.obsolete, req.user.name)
        eq_(self.obj.status, UpdateStatus.obsolete)
        eq_(len(req.errors), 0)
        publish.assert_called_once_with(
            topic='update.request.obsolete', msg=mock.ANY)

    @mock.patch('bodhi.notifications.publish')
    def test_request_complete(self, publish):
        self.obj.request = None
        eq_(self.obj.date_pushed, None)
        self.obj.request = UpdateRequest.testing
        self.obj.request_complete()
        assert self.obj.date_pushed
        eq_(self.obj.status, UpdateStatus.testing)

    def test_status_comment(self):
        self.obj.status = UpdateStatus.testing
        self.obj.status_comment(self.db)
        eq_(len(self.obj.comments), 1)
        eq_(self.obj.comments[0].user.name, u'bodhi')
        eq_(self.obj.comments[0].text,
                u'This update has been pushed to testing.')
        self.obj.status = UpdateStatus.stable
        self.obj.status_comment(self.db)
        eq_(len(self.obj.comments), 2)
        eq_(self.obj.comments[1].user.name, u'bodhi')
        eq_(self.obj.comments[1].text,
                u'This update has been pushed to stable.')
        assert str(self.obj.comments[1]).endswith(
            'This update has been pushed to stable.')

    @mock.patch('bodhi.notifications.publish')
    def test_anonymous_comment(self, publish):
        self.obj.comment(self.db, u'testing', author='me', anonymous=True, karma=1)
        c = self.obj.comments[-1]
        assert str(c).endswith('testing')
        eq_(c.anonymous, True)
        eq_(c.text, 'testing')
        publish.assert_called_once_with(
            topic='update.comment', msg=mock.ANY)
        args, kwargs = publish.call_args
        eq_(kwargs['msg']['comment']['author'], 'anonymous')

    def test_get_url(self):
        eq_(self.obj.get_url(), u'updates/TurboGears-1.0.8-3.fc11')
        idx = 'a3bbe1a8f2'
        with mock.patch(target='uuid.uuid4', return_value='wat'):
            self.obj.assign_alias()
        expected = u'updates/FEDORA-%s-%s' % (time.localtime()[0], idx)
        eq_(self.obj.get_url(), expected)

    def test_bug(self):
        bug = self.obj.bugs[0]
        eq_(bug.url, 'https://bugzilla.redhat.com/show_bug.cgi?id=1')
        bug.testing(self.obj)
        bug.add_comment(self.obj)
        bug.add_comment(self.obj, comment='testing')
        bug.close_bug(self.obj)
        self.obj.status = UpdateStatus.testing
        bug.add_comment(self.obj)

    def test_cve(self):
        cve = self.obj.cves[0]
        eq_(cve.url, 'http://www.cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2009-0001')

    def test_expand_messages(self):
        """Ensure all messages can be expanded properly"""
        self.obj.comment(self.db, u'test', 0, u'guest')
        for value in mail.MESSAGES.values():
            value['body'] % value['fields']('guest', self.obj)


class TestUser(ModelTest):
    klass = model.User
    attrs = dict(name=u'Bob Vila')

    def do_get_dependencies(self):
        group = model.Group(name=u'proventesters')
        return dict(groups=[group])


class TestGroup(ModelTest):
    klass = model.Group
    attrs = dict(name=u'proventesters')

    def do_get_dependencies(self):
        user = model.User(name=u'bob')
        return dict(users=[user])


class TestBuildrootOverride(ModelTest):
    klass = model.BuildrootOverride
    attrs = dict(notes=u'This is needed to build foobar',
                 expiration_date=datetime.utcnow())

    def do_get_dependencies(self):
        return dict(
            build=model.Build(nvr=u'TurboGears-1.0.8-3.fc11',
                              package=model.Package(**TestPackage.attrs),
                              release=model.Release(**TestRelease.attrs)),
            submitter=model.User(name=u'lmacken'),
            )
