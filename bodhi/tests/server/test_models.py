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
"""Test suite for bodhi.server.models"""
from datetime import datetime, timedelta
import json
import time
import unittest

from nose.tools import assert_equals, eq_, raises
from pyramid.testing import DummyRequest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension
import cornice
import mock

from bodhi.server import models as model, bugs, buildsys, mail, util
from bodhi.server.config import config
from bodhi.server.exceptions import BodhiException
from bodhi.server.models import (
    Base, BugKarma, get_db_factory, ReleaseState, UpdateRequest, UpdateSeverity, UpdateStatus,
    UpdateSuggestion, UpdateType)


class DummyUser(object):
    name = 'guest'


class ModelTest(object):
    """Base unit test case for the models."""

    klass = None
    attrs = {}

    def setUp(self):
        bugs.set_bugtracker()
        buildsys.setup_buildsystem({'buildsystem': 'dev'})
        engine = create_engine('sqlite://')
        Session = scoped_session(
            sessionmaker(extension=ZopeTransactionExtension(keep_session=True)))
        Session.configure(bind=engine)
        self.db = Session()
        Base.metadata.create_all(engine)
        try:
            new_attrs = {}
            new_attrs.update(self.attrs)
            new_attrs.update(self.do_get_dependencies())
            self.obj = self.klass(**new_attrs)
            self.db.add(self.obj)
            self.db.flush()
            return self.obj
        except:
            self.db.rollback()
            raise

    def tearDown(self):
        self.db.close()

    def do_get_dependencies(self):
        """ Use this method to pull in other objects that need to be
        created for this object to be built properly.
        """

        return {}

    def test_create_obj(self):
        pass

    def test_query_obj(self):
        for key, value in self.attrs.iteritems():
            assert_equals(getattr(self.obj, key), value)

    def test_json(self):
        """ Ensure our models can return valid JSON """
        assert json.dumps(self.obj.__json__())

    def test_get(self):
        for col in self.obj.__get_by__:
            eq_(self.klass.get(getattr(self.obj, col), self.db), self.obj)


class TestComment(unittest.TestCase):
    def test_text_not_nullable(self):
        """Assert that the text column does not allow NULL values.

        For history about why this is important, see
        https://github.com/fedora-infra/bodhi/issues/949.
        """
        self.assertEqual(model.Comment.__table__.columns['text'].nullable, False)


class TestGetDBFactory(unittest.TestCase):
    """
    This class contains tests for the get_db_factory() function.
    """
    def test_return_type(self):
        """
        """
        Session = get_db_factory()

        self.assertEqual(type(Session), util.TransactionalSessionMaker)


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
        pending_signing_tag=u"dist-f11-updates-testing-signing",
        pending_testing_tag=u"dist-f11-updates-testing-pending",
        pending_stable_tag=u"dist-f11-updates-pending",
        override_tag=u"dist-f11-override",
        state=model.ReleaseState.current)

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
    attrs = dict(nvr=u"TurboGears-1.0.8-3.fc11", inherited=False)

    def do_get_dependencies(self):
        return dict(release=model.Release(**TestRelease.attrs),
                    package=model.Package(**TestPackage.attrs))

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

    def test_url(self):
        eq_(self.obj.get_url(), u'/TurboGears-1.0.8-3.fc11')


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
        notes=u'foobar')

    def do_get_dependencies(self):
        release = model.Release(**TestRelease.attrs)
        return dict(
            builds=[model.Build(nvr=u'TurboGears-1.0.8-3.fc11',
                                package=model.Package(**TestPackage.attrs), release=release)],
            bugs=[model.Bug(bug_id=1), model.Bug(bug_id=2)],
            cves=[model.CVE(cve_id=u'CVE-2009-0001')],
            release=release,
            user=model.User(name=u'lmacken'))

    def get_update(self, name=u'TurboGears-1.0.8-3.fc11'):
        """Return an Update instance for testing."""
        attrs = self.attrs.copy()
        attrs['title'] = name
        pkg = self.db.query(model.Package).filter_by(name=u'TurboGears').one()
        rel = self.db.query(model.Release).filter_by(name=u'F11').one()
        attrs.update(dict(
            builds=[model.Build(nvr=name, package=pkg, release=rel)],
            release=rel))
        return self.klass(**attrs)

    def test_autokarma_not_nullable(self):
        """Assert that the autokarma column does not allow NULL values.

        For history about why this is important, see
        https://github.com/fedora-infra/bodhi/issues/1048
        """
        eq_(model.Update.__table__.columns['autokarma'].nullable, False)

    def test_builds(self):
        eq_(len(self.obj.builds), 1)
        eq_(self.obj.builds[0].nvr, u'TurboGears-1.0.8-3.fc11')
        eq_(self.obj.builds[0].release.name, u'F11')
        eq_(self.obj.builds[0].package.name, u'TurboGears')

    def test_days_to_stable_meets_testing_requirements(self):
        """
        The Update.days_to_stable() method should return 0 if Update.meets_testing_requirements()
        returns True.
        """
        update = self.obj
        update.autokarma = False
        update.stable_karma = 1
        update.comment(self.db, u'I found $100 after applying this update.', karma=1,
                       author=u'bowlofeggs')
        # Assert that our preconditions from the docblock are correct.
        eq_(update.meets_testing_requirements, True)

        eq_(update.days_to_stable, 0)

    def test_days_to_stable_not_meets_testing_requirements_no_date_testing(self):
        """
        The Update.days_to_stable() method should return 0 if Update.meets_testing_requirements()
        returns False but the Update's date_testing attribute is not truthy.
        """
        update = self.get_update()
        # Assert that our preconditions from the docblock are correct.
        eq_(update.meets_testing_requirements, False)
        eq_(update.date_testing, None)

        eq_(update.days_to_stable, 0)

    def test_days_to_stable_not_meets_testing_requirements_with_date_testing(self):
        """
        The Update.days_to_stable() method should return a positive integer if
        Update.meets_testing_requirements() returns False and the Update's date_testing attribute is
        truthy.
        """
        update = self.get_update()
        update.date_testing = datetime.utcnow() + timedelta(days=-4)
        # Assert that our preconditions from the docblock are correct.
        eq_(update.meets_testing_requirements, False)

        eq_(update.days_to_stable, 3)

    @mock.patch('bodhi.server.models.bugs.bugtracker.close')
    @mock.patch('bodhi.server.models.bugs.bugtracker.comment')
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

    @mock.patch('bodhi.server.models.bugs.bugtracker.close')
    @mock.patch('bodhi.server.models.bugs.bugtracker.comment')
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
                                  release.pending_signing_tag,
                                  release.pending_testing_tag,
                                  # Add an unknown tag that we shouldn't touch
                                  release.dist_tag + '-compose']
        self.obj.builds[0].unpush(koji)
        eq_(koji.__moved__, [(u'dist-f11-updates-testing', u'dist-f11-updates-candidate',
                              u'TurboGears-1.0.8-3.fc11')])
        eq_(koji.__untag__, [(u'dist-f11-updates-testing-signing', u'TurboGears-1.0.8-3.fc11'),
                             (u'dist-f11-updates-testing-pending', u'TurboGears-1.0.8-3.fc11')])

    def test_title(self):
        eq_(self.obj.title, u'TurboGears-1.0.8-3.fc11')

    def test_pkg_str(self):
        """ Ensure str(pkg) is correct """
        eq_(str(self.obj.builds[0].package),
            ('================================================================================\n   '
             '  TurboGears\n======================================================================='
             '=========\n\n Pending Updates (1)\n    o TurboGears-1.0.8-3.fc11\n'))

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

        # Create another update for another release that has the same
        # Release.id_prefix.  This used to trigger a bug that would cause
        # duplicate IDs across Fedora 10/11 updates.
        update = self.get_update(name=u'nethack-3.4.5-1.fc10')
        otherrel = model.Release(name=u'fc10', long_name=u'Fedora 10',
                                 id_prefix=u'FEDORA', dist_tag=u'dist-fc10',
                                 stable_tag=u'dist-fc10-updates',
                                 testing_tag=u'dist-fc10-updates-testing',
                                 candidate_tag=u'dist-fc10-updates-candidate',
                                 pending_signing_tag=u'dist-fc10-updates-testing-signing',
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
        release = model.Release(
            name=u'EL-5', long_name=u'Fedora EPEL 5', id_prefix=u'FEDORA-EPEL',
            dist_tag=u'dist-5E-epel', stable_tag=u'dist-5E-epel',
            testing_tag=u'dist-5E-epel-testing', candidate_tag=u'dist-5E-epel-testing-candidate',
            pending_signing_tag=u'dist-5E-epel-testing-signing',
            pending_testing_tag=u'dist-5E-epel-testing-pending',
            pending_stable_tag=u'dist-5E-epel-pending', override_tag=u'dist-5E-epel-override',
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

    def test_karma_no_comments(self):
        """Check that karma returns the correct value with one negative and two positive comments.
        """
        eq_(self.obj.karma, 0)

    def test_karma_one_negative_two_positive(self):
        """Check that karma returns the correct value with one negative and two positive comments.
        """
        self.obj.comment(self.db, u"foo", 1, u'foo')
        self.obj.comment(self.db, u"foo", -1, u'bar')
        self.obj.comment(self.db, u"foo", 1, u'biz')

        eq_(self.obj.karma, 1)

    def test_karma_two_negative_one_positive(self):
        """Check that karma returns the correct value with two negative and one positive comments.
        """
        self.obj.comment(self.db, u"foo", -1, u'foo')
        self.obj.comment(self.db, u"foo", -1, u'bar')
        self.obj.comment(self.db, u"foo", 1, u'biz')

        eq_(self.obj.karma, -1)

    def test__composite_karma_ignores_anonymous_karma(self):
        """Assert that _composite_karma ignores anonymous karma."""
        self.obj.comment(self.db, u"foo", -1, u'foo')
        self.obj.comment(self.db, u"foo", -1, u'bar')
        # This one shouldn't get counted
        self.obj.comment(self.db, u"foo", 1, u'biz', anonymous=True)

        eq_(self.obj._composite_karma, (0, -2))

    def test__composite_karma_ignores_comments_before_new_build(self):
        """Assert that _composite_karma ignores karma from before a new build karma reset event."""
        self.obj.comment(self.db, u"foo", -1, u'foo')
        self.obj.comment(self.db, u"foo", -1, u'bar')
        # This is a "karma reset event", so the above comments should not be counted in the karma.
        self.obj.comment(self.db, u"New build", 0, u'bodhi')
        self.obj.comment(self.db, u"foo", 1, u'biz')

        eq_(self.obj._composite_karma, (1, 0))

    def test__composite_karma_ignores_comments_before_removed_build(self):
        """Assert that _composite_karma ignores karma from before a removed build karma reset event.
        """
        self.obj.comment(self.db, u"foo", 1, u'foo')
        self.obj.comment(self.db, u"foo", 1, u'bar')
        # This is a "karma reset event", so the above comments should not be counted in the karma.
        self.obj.comment(self.db, u"Removed build", 0, u'bodhi')
        self.obj.comment(self.db, u"foo", -1, u'biz')

        eq_(self.obj._composite_karma, (0, -1))

    def test__composite_karma_ignores_comments_without_karma(self):
        """
        Assert that _composite_karma ignores comments that don't carry karma.

        See https://github.com/fedora-infra/bodhi/issues/829
        """
        self.obj.comment(self.db, u"It ate my ostree", -1, u'dusty')
        self.obj.comment(self.db, u"i love it push to stable now", 1, u'ididntreallytestitlol')
        # In bug #829, this comment would have overridden dusty's earlier -1 changing his vote to be
        # 0.
        self.obj.comment(self.db, u"plz no don't… my ostreeeeee!", 0, u'dusty')

        # The composite karma should be 1, -1 since dusty's earlier vote should still count.
        eq_(self.obj._composite_karma, (1, -1))

    def test__composite_karma_ignores_old_comments(self):
        """Assert that _composite_karma ignores karma from a user's previous responses."""
        self.obj.comment(self.db, u"I", -1, u'foo')
        self.obj.comment(self.db, u"can't", 1, u'foo')
        self.obj.comment(self.db, u"make", -1, u'foo')
        self.obj.comment(self.db, u"up", 1, u'foo')
        self.obj.comment(self.db, u"my", -1, u'foo')
        self.obj.comment(self.db, u"mind", 1, u'foo')
        self.obj.comment(self.db, u".", -37, u'foo')

        eq_(self.obj._composite_karma, (0, -37))

    def test__composite_karma_mixed_case(self):
        """Assert _composite_karma with mixed responses that hits a lot of the method."""
        self.obj.comment(self.db, u"ignored", -1, u'foo1')
        self.obj.comment(self.db, u"forgotten", -1, u'foo2')
        # This is a "karma reset event", so the above comments should not be counted in the karma.
        self.obj.comment(self.db, u"Removed build", 0, u'bodhi')
        self.obj.comment(self.db, u"Nice job", -1, u'foo')
        self.obj.comment(self.db, u"Whoops my last comment was wrong", 1, u'foo')
        self.obj.comment(self.db, u"LGTM", 1, u'foo2')
        self.obj.comment(self.db, u"Don't ignore me", -1, u'foo1')

        eq_(self.obj._composite_karma, (2, -1))

    def test__composite_karma_no_comments(self):
        """Assert _composite_karma with no comments is (0, 0)."""
        eq_(self.obj._composite_karma, (0, 0))

    def test__composite_karma_one_negative_two_positive(self):
        """Assert that _composite_karma returns (2, -1) with one negative and two positive comments.
        """
        self.obj.comment(self.db, u"foo", 1, u'foo')
        self.obj.comment(self.db, u"foo", -1, u'bar')
        self.obj.comment(self.db, u"foo", 1, u'biz')

        eq_(self.obj._composite_karma, (2, -1))

    @mock.patch('bodhi.server.notifications.publish')
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

    @mock.patch('bodhi.server.notifications.publish')
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
        from bodhi.server.util import bug_link
        link = bug_link(None, bug)
        eq_(link, (u"<a target='_blank' href='https://bugzilla.redhat.com/show_bug.cgi?id=1'>#1</a>"
                   u" foo\xe9bar"))

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

    @mock.patch('bodhi.server.notifications.publish')
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

    @mock.patch('bodhi.server.notifications.publish')
    def test_met_testing_requirements_at_7_days_after_bodhi_comment(self, publish):
        """
        Ensure a correct True return value from Update.met_testing_requirements() after an update
        has been in testing for 7 days and after bodhi has commented about it.
        """
        self.obj.status = UpdateStatus.testing
        # Pretend it's been in testing for a week
        self.obj.comment(
            self.db, u'This update has been pushed to testing.', author=u'bodhi')
        self.obj.date_testing = self.obj.comments[-1].timestamp - timedelta(days=7)
        eq_(self.obj.days_in_testing, 7)
        # The update should be eligible to receive the testing_approval_msg now.
        eq_(self.obj.meets_testing_requirements, True)
        # Add the testing_approval_message
        text = unicode(config.get('testing_approval_msg') % self.obj.days_in_testing)
        self.obj.comment(self.db, text, author=u'bodhi')

        # met_testing_requirement() should return True since Bodhi has commented on the Update to
        # say that it can now be pushed to stable.
        eq_(self.obj.met_testing_requirements, True)

    @mock.patch('bodhi.server.notifications.publish')
    def test_met_testing_requirements_at_7_days_before_bodhi_comment(self, publish):
        """
        Ensure a correct False return value from Update.met_testing_requirements() after an update
        has been in testing for 7 days but before bodhi has commented about it.
        """
        self.obj.status = UpdateStatus.testing
        # Pretend it's been in testing for a week
        self.obj.comment(
            self.db, u'This update has been pushed to testing.', author=u'bodhi')
        self.obj.date_testing = self.obj.comments[-1].timestamp - timedelta(days=7)
        eq_(self.obj.days_in_testing, 7)
        # The update should be eligible to receive the testing_approval_msg now.
        eq_(self.obj.meets_testing_requirements, True)

        # Since bodhi hasn't added the testing_approval_message yet, this should be False.
        eq_(self.obj.met_testing_requirements, False)

    def test_meets_testing_requirements_with_non_autokarma_update_below_stable_karma(self):
        """
        Assert that meets_testing_requirements() correctly returns True for non-autokarma updates
        that haven't reached the days in testing but have reached the stable_karma threshold.
        """
        self.obj.autokarma = False
        self.obj.status = UpdateStatus.testing
        self.obj.stable_karma = 1

        # meets_testing_requirement() should return False since the karma threshold has not been
        # reached (note that this Update does not have any karma).
        eq_(self.obj.meets_testing_requirements, False)

    def test_meets_testing_requirements_with_non_autokarma_update_reaching_stable_karma(self):
        """
        Assert that meets_testing_requirements() correctly returns True for non-autokarma updates
        that haven't reached the days in testing but have reached the stable_karma threshold.
        """
        self.obj.autokarma = False
        self.obj.status = UpdateStatus.testing
        self.obj.stable_karma = 1
        # Now let's add some karma to get it to the required threshold
        self.obj.comment(self.db, u'testing', author=u'hunter2', anonymous=False, karma=1)

        # meets_testing_requirement() should return True since the karma threshold has been reached
        eq_(self.obj.meets_testing_requirements, True)

    def test_meets_testing_requirements_with_non_autokarma_update_with_stable_karma_0(self):
        """
        Assert that meets_testing_requirements() correctly returns False for non-autokarma updates
        that haven't reached the days in testing but have stable_karma set to 0 (indicating that the
        update must stay in testing for the full amount of time).
        """
        self.obj.autokarma = False
        self.obj.status = UpdateStatus.testing
        self.obj.stable_karma = 0
        # Now let's add some karma to get it above stable_karma, which should not be counted as
        # meeting the requirements.
        self.obj.comment(self.db, u'testing', author=u'hunter2', anonymous=False, karma=1)

        # meets_testing_requirement() should return False since the stable_karma threshold is 0.
        eq_(self.obj.meets_testing_requirements, False)

    def test_meets_testing_requirements_with_non_autokarma_update_with_stable_karma_None(self):
        """
        Assert that meets_testing_requirements() correctly returns False for non-autokarma updates
        that haven't reached the days in testing but have stable_karma set to None (indicating that
        the update must stay in testing for the full amount of time).
        """
        self.obj.autokarma = False
        self.obj.status = UpdateStatus.testing
        self.obj.stable_karma = None
        # Now let's add some karma to get it above stable_karma, which should not be counted as
        # meeting the requirements.
        self.obj.comment(self.db, u'testing', author=u'hunter2', anonymous=False, karma=1)

        # meets_testing_requirement() should return False since the stable_karma threshold is None.
        eq_(self.obj.meets_testing_requirements, False)

    @mock.patch('bodhi.server.notifications.publish')
    def test_met_testing_requirements_with_karma_after_bodhi_comment(self, publish):
        """
        Ensure a correct True return value from Update.met_testing_requirements() after a
        non-autokarma update has reached the karma requirement and after bodhi has commented about
        it.
        """
        self.obj.autokarma = False
        self.obj.status = UpdateStatus.testing
        # Pretend it's been in testing for a day
        self.obj.comment(
            self.db, u'This update has been pushed to testing.', author=u'bodhi')
        self.obj.date_testing = self.obj.comments[-1].timestamp - timedelta(days=1)
        eq_(self.obj.days_in_testing, 1)
        # Now let's add some karma to get it to the required threshold
        self.obj.comment(self.db, u'testing', author=u'hunter1', anonymous=False, karma=1)
        self.obj.comment(self.db, u'testing', author=u'hunter2', anonymous=False, karma=1)
        self.obj.comment(self.db, u'testing', author=u'hunter3', anonymous=False, karma=1)
        # Add the testing_approval_message
        text = unicode(config.get('testing_approval_msg_based_on_karma'))
        self.obj.comment(self.db, text, author=u'bodhi')

        # met_testing_requirement() should return True since Bodhi has commented on the Update to
        # say that it can now be pushed to stable.
        eq_(self.obj.met_testing_requirements, True)

    @mock.patch('bodhi.server.notifications.publish')
    def test_met_testing_requirements_with_karma_before_bodhi_comment(self, publish):
        """
        Ensure a correct False return value from Update.met_testing_requirements() after a
        non-autokarma update has reached the karma requirement but before bodhi has commented about
        it.
        """
        self.obj.autokarma = False
        self.obj.status = UpdateStatus.testing
        # Pretend it's been in testing for a day
        self.obj.comment(
            self.db, u'This update has been pushed to testing.', author=u'bodhi')
        self.obj.date_testing = self.obj.comments[-1].timestamp - timedelta(days=1)
        eq_(self.obj.days_in_testing, 1)
        # Now let's add some karma to get it to the required threshold
        self.obj.comment(self.db, u'testing', author=u'hunter1', anonymous=False, karma=1)
        self.obj.comment(self.db, u'testing', author=u'hunter2', anonymous=False, karma=1)
        self.obj.comment(self.db, u'testing', author=u'hunter3', anonymous=False, karma=1)

        # met_testing_requirement() should return False since Bodhi has not yet commented on the
        # Update to say that it can now be pushed to stable.
        eq_(self.obj.met_testing_requirements, False)

    @mock.patch('bodhi.server.notifications.publish')
    def test_set_request_obsolete(self, publish):
        req = DummyRequest(user=DummyUser())
        req.errors = cornice.Errors()
        eq_(self.obj.status, UpdateStatus.pending)
        self.obj.set_request(self.db, UpdateRequest.obsolete, req.user.name)
        eq_(self.obj.status, UpdateStatus.obsolete)
        eq_(len(req.errors), 0)
        publish.assert_called_once_with(
            topic='update.request.obsolete', msg=mock.ANY)

    @mock.patch('bodhi.server.notifications.publish')
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

    @mock.patch('bodhi.server.notifications.publish')
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

    @mock.patch('bodhi.server.mail.get_template')
    def test_send_update_notice_message_template_fedora(self, get_template):
        """Ensure update message template reflects fedora when it should"""
        update = self.obj
        update.status = UpdateStatus.stable

        update.send_update_notice()

        get_template.assert_called_with(update, u'fedora_errata_template')

    @mock.patch('bodhi.server.mail.get_template')
    def test_send_update_notice_message_template_el7(self, get_template):
        """Ensure update message template reflects EL <= 7 when it should"""
        update = self.get_update(name=u'TurboGears-3.1-1.el7')
        release = model.Release(
            name=u'EL-7', long_name=u'Fedora EPEL 7', id_prefix=u'FEDORA-EPEL',
            dist_tag=u'dist-7E-epel', stable_tag=u'dist-7E-epel',
            testing_tag=u'dist-7E-epel-testing', candidate_tag=u'dist-7E-epel-testing-candidate',
            pending_testing_tag=u'dist-7E-epel-testing-pending',
            pending_stable_tag=u'dist-7E-epel-pending', override_tag=u'dist-7E-epel-override',
            branch=u'el7', version=u'7')
        update.release = release
        update.status = UpdateStatus.stable

        update.send_update_notice()

        get_template.assert_called_with(update, u'fedora_epel_legacy_errata_template')

    @mock.patch('bodhi.server.mail.get_template')
    def test_send_update_notice_message_template_el8(self, get_template):
        """Ensure update message template reflects EL >= 8 when it should"""
        update = self.get_update(name=u'TurboGears-4.1-1.el8')
        release = model.Release(
            name=u'EL-8', long_name=u'Fedora EPEL 8', id_prefix=u'FEDORA-EPEL',
            dist_tag=u'dist-8E-epel', stable_tag=u'dist-8E-epel',
            testing_tag=u'dist-8E-epel-testing', candidate_tag=u'dist-8E-epel-testing-candidate',
            pending_testing_tag=u'dist-8E-epel-testing-pending',
            pending_stable_tag=u'dist-8E-epel-pending', override_tag=u'dist-8E-epel-override',
            branch=u'el8', version=u'8')
        update.release = release
        update.status = UpdateStatus.stable

        update.send_update_notice()

        get_template.assert_called_with(update, u'fedora_epel_errata_template')


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
            submitter=model.User(name=u'lmacken'))
