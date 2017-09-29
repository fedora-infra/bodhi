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
from HTMLParser import HTMLParser
import json
import pickle
import time
import unittest

from pyramid.testing import DummyRequest
from sqlalchemy.exc import IntegrityError
import cornice
import mock

from bodhi.server import models as model, buildsys, mail, util, Session
from bodhi.server.config import config
from bodhi.server.exceptions import BodhiException
from bodhi.server.models import (
    BugKarma, ReleaseState, UpdateRequest, UpdateSeverity, UpdateStatus,
    UpdateSuggestion, UpdateType, TestGatingStatus)
from bodhi.tests.server.base import BaseTestCase


class DummyUser(object):
    name = 'guest'


class ModelTest(BaseTestCase):
    """Base unit test case for the models."""

    klass = None
    attrs = {}
    _populate_db = False

    def setUp(self):
        super(ModelTest, self).setUp()
        buildsys.setup_buildsystem({'buildsystem': 'dev'})
        if type(self) != ModelTest:
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

    def do_get_dependencies(self):
        """ Use this method to pull in other objects that need to be
        created for this object to be built properly.
        """

        return {}

    def test_create_obj(self):
        pass

    def test_query_obj(self):
        for key, value in self.attrs.iteritems():
            self.assertEqual(getattr(self.obj, key), value)

    def test_json(self):
        """ Ensure our models can return valid JSON """
        if type(self) != ModelTest:
            assert json.dumps(self.obj.__json__())

    def test_get(self):
        if type(self) != ModelTest:
            for col in self.obj.__get_by__:
                self.assertEqual(self.klass.get(getattr(self.obj, col), self.db), self.obj)


class TestBodhiBase(BaseTestCase):
    """Test the BodhiBase class."""

    def test__expand_with_m2m_relation(self):
        """Test the _expand() method with a many-to-many relation."""
        p = model.Package.query.all()[0]
        new_exclude_columns = list(model.Package.__exclude_columns__)
        new_exclude_columns.remove('committers')
        # p.committers is an InstrumentedList, which doesn't have an all() method. We have some
        # code to handle m2m relationships with all() methods, but it's not immediately obvious
        # which relationships have that for testing purposes. Thus, we can simulate this for
        # test coverage purposes by setting it to its __iter__() method.
        p.committers.all = p.committers.__iter__

        with mock.patch.object(model.Package, '__exclude_columns__', new_exclude_columns):
            committers = p._expand(p, p.committers, [], mock.MagicMock())

        self.assertEqual(len(committers), 1)
        self.assertEqual(committers[0]['name'], 'guest')

    def test__expand_with_relation_in_seen(self):
        """_expand() should return the relation.id attribute if its type is in seen."""
        b = model.Build.query.all()[0]

        self.assertEqual(b._expand(b, b.package, [type(b.package)], mock.MagicMock()), b.package.id)

    def test__to_json_anonymize_false(self):
        """Test _to_json with anonymize set to False."""
        c = model.Comment.query.all()[0]
        c.anonymous = True

        j = c._to_json(c, anonymize=False)

        self.assertEqual(
            j['user'],
            {'avatar': None, 'email': c.user.email, 'groups': [{'name': 'packager'}],
             'id': c.user.id, 'name': c.user.name, 'openid': None,
             'show_popups': c.user.show_popups})

    def test__to_json_anonymize_true(self):
        """Test _to_json with anonymize set to True."""
        c = model.Comment.query.all()[0]
        c.anonymous = True

        j = c._to_json(c, anonymize=True)

        self.assertEqual(j['user'], 'anonymous')

    def test__to_json_falsey_object(self):
        """Assert that _to_json() returns None when handed a Falsey object."""
        self.assertEqual(model.Build._to_json(False, seen=None), None)
        self.assertEqual(model.Build._to_json(None, seen=None), None)
        self.assertEqual(model.Build._to_json('', seen=None), None)
        self.assertEqual(model.Build._to_json([], seen=None), None)

    def test__to_json_no_seen(self):
        """Assert correct behavior from _to_json() when seen is None."""
        b = model.Build.query.all()[0]

        j = b._to_json(b, seen=None)

        self.assertEqual(
            j,
            {'release_id': 1, 'ci_url': b.ci_url, 'epoch': b.epoch, 'nvr': b.nvr,
             'signed': b.signed, 'type': unicode(b.type.value)})

    def test_grid_columns(self):
        """Assert correct return value from the grid_columns() method."""
        self.assertEqual(model.Build.grid_columns(), ['nvr', 'release_id', 'signed',
                                                      'ci_url', 'type', 'epoch'])

    def test_find_child_for_rpm(self):
        subclass = model.Package.find_polymorphic_child(model.ContentType.rpm)
        self.assertEqual(subclass, model.RpmPackage)
        subclass = model.Build.find_polymorphic_child(model.ContentType.rpm)
        self.assertEqual(subclass, model.RpmBuild)
        subclass = model.Package.find_polymorphic_child(model.ContentType.module)
        self.assertEqual(subclass, model.ModulePackage)
        subclass = model.Build.find_polymorphic_child(model.ContentType.module)
        self.assertEqual(subclass, model.ModuleBuild)

    def test_find_child_with_bad_identity(self):
        with self.assertRaises(NameError):
            model.Package.find_polymorphic_child(model.UpdateType.security)

    def test_find_child_with_bad_base_class(self):
        with self.assertRaises(KeyError):
            model.Update.find_polymorphic_child(model.ContentType.rpm)

    def test_find_child_with_badly_typed_argument(self):
        with self.assertRaises(TypeError):
            model.Update.find_polymorphic_child("whatever")


class TestQueryProperty(BaseTestCase):

    def test_session(self):
        """Assert the session the query property uses is from the scoped session."""
        query = model.Package.query
        self.assertTrue(self.db is query.session)


class TestComment(BaseTestCase):
    def test_text_not_nullable(self):
        """Assert that the text column does not allow NULL values.

        For history about why this is important, see
        https://github.com/fedora-infra/bodhi/issues/949.
        """
        self.assertEqual(model.Comment.__table__.columns['text'].nullable, False)

    def test_get_unigue_testcase_feedback(self):
        update = self.create_update(
            (u'bodhi-2.3.3-1.fc24', u'python-fedora-atomic-composer-2016.3-1.fc24'))
        package = update.builds[0].package
        test1 = model.TestCase(name=u"Test 1", package=package)
        test2 = model.TestCase(name=u"Test 2", package=package)
        test3 = model.TestCase(name=u"Test 2", package=package)
        testcase_feedback = [{'testcase': test1, 'karma': 1},
                             {'testcase': test2, 'karma': 1},
                             {'testcase': test3, 'karma': 1}]
        update.comment(session=self.db, text=u"test", karma=1, author=u"test",
                       testcase_feedback=testcase_feedback)
        comments = update.comments
        feedback = comments[0].unique_testcase_feedback

        feedback_titles = [f.testcase.name for f in feedback]
        feedback_titles_expected = [u"Test 1", u"Test 2"]
        feedback_karma_sum = sum([f.karma for f in feedback])

        self.assertEqual(len(feedback), 2)
        self.assertEqual(sorted(feedback_titles), sorted(feedback_titles_expected))
        self.assertEqual(feedback_karma_sum, 2)


class TestDeclEnum(unittest.TestCase):
    """Test the DeclEnum class."""

    def test_from_string_bad_value(self):
        """Test the from_string() method with a value that doesn't exist."""
        with self.assertRaises(ValueError) as exc:
            model.UpdateStatus.from_string('wrong')

        self.assertEqual(str(exc.exception), "Invalid value for 'UpdateStatus': 'wrong'")


class TestDeclEnumType(BaseTestCase):
    """Test the DeclEnumType class."""

    def test_create_does_not_raise_exception(self):
        """Assert that a call to the create() method does not raise an Exception."""
        t = model.DeclEnumType(model.UpdateStatus)

        t.create(self.engine)

    def test_drop_does_not_raise_exception(self):
        """Assert that a call to the drop() method does not raise an Exception."""
        t = model.DeclEnumType(model.UpdateStatus)

        t.drop(self.engine)

    def test_process_bind_param_None(self):
        """Test the process_bind_param() method with a value of None."""
        t = model.DeclEnumType(model.UpdateStatus)

        self.assertEqual(t.process_bind_param(None, self.engine.dialect), None)

    def test_process_bind_param_truthy_value(self):
        """Test the process_bind_param() method with a truthy value."""
        t = model.DeclEnumType(model.UpdateStatus)

        self.assertEqual(t.process_bind_param(model.UpdateStatus.stable, self.engine.dialect),
                         'stable')

    def test_process_result_value_None(self):
        """Test the process_result_value() method with a value of None."""
        t = model.DeclEnumType(model.UpdateStatus)

        self.assertEqual(t.process_result_value(None, self.engine.dialect), None)

    def test_process_result_value_truthy_value(self):
        """Test the process_result_value() method with a truthy value."""
        t = model.DeclEnumType(model.UpdateStatus)

        self.assertEqual(t.process_result_value('testing', self.engine.dialect),
                         model.UpdateStatus.testing)


class TestEnumMeta(unittest.TestCase):
    """Test the Enummeta class."""

    def test___iter__(self):
        """Assert correct return value from the __iter__() method."""
        m = model.EnumMeta('UpdateStatus', (model.DeclEnum,),
                           {'testing': ('testing', 'Testing'), 'stable': ('stable', 'Stable')})
        expected_values = ['testing', 'stable']

        for v in iter(m):
            self.assertEqual(str(v), '<{}>'.format(expected_values.pop(0)))
            self.assertEqual(type(v), model.EnumSymbol)

        self.assertEqual(expected_values, [])


class TestEnumSymbol(unittest.TestCase):
    """Test the EnumSymbol class."""

    def test___iter__(self):
        """Ensure correct operation of the __iter__() method."""
        s = model.EnumSymbol(model.UpdateStatus, 'name', 'value', 'description')
        expected_values = ['value', 'description']

        for v in iter(s):
            self.assertEqual(v, expected_values.pop(0))

        self.assertEqual(expected_values, [])

    def test___json__(self):
        """Ensure that the __json__() method returns the value."""
        s = model.EnumSymbol(model.UpdateStatus, 'name', 'value', 'description')

        self.assertEqual(s.__json__(), 'value')

    def test___reduce__(self):
        """Ensure correct operation of the __reduce__() method by pickling an instance."""
        s = model.EnumSymbol(model.UpdateStatus, 'testing', 'testing', 'testing')

        p = pickle.dumps(s)

        deserialized_s = pickle.loads(p)
        self.assertEqual(deserialized_s.cls_, model.UpdateStatus)
        self.assertEqual(deserialized_s.name, 'testing')
        self.assertEqual(deserialized_s.value, 'testing')
        self.assertEqual(deserialized_s.description, 'testing')

    def test___repr__(self):
        """Ensure correct operation of the __repr__() method."""
        s = model.EnumSymbol(model.UpdateStatus, 'name', 'value', 'description')

        self.assertEqual(repr(s), '<name>')

    def test___unicode__(self):
        """Ensure correct operation of the __unicode__() method."""
        s = model.EnumSymbol(model.UpdateStatus, 'name', 'value', 'description')

        self.assertEqual(unicode(s), 'value')
        self.assertEqual(type(unicode(s)), unicode)


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
        self.assertEqual(self.obj.version_int, 11)

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


class TestPackageUniqueConstraints(BaseTestCase):
    """Tests for the Package model's uniqueness constraints."""

    def test_two_package_different_types(self):
        """Assert two different package types with the same name is fine."""
        package1 = model.Package(name=u'python-requests')
        package2 = model.RpmPackage(name=u'python-requests')

        self.db.add(package1)
        self.db.add(package2)
        self.db.flush()

    def test_two_package_same_type(self):
        """Assert two packages of the same type with the same name is *not* fine."""
        package1 = model.RpmPackage(name=u'python-requests')
        package2 = model.RpmPackage(name=u'python-requests')

        self.db.add(package1)
        self.db.add(package2)
        self.assertRaises(IntegrityError, self.db.flush)


class TestModulePackage(ModelTest, unittest.TestCase):
    """Unit test case for the ``ModulePackage`` model."""
    klass = model.ModulePackage
    attrs = dict(name=u"TurboGears")

    def do_get_dependencies(self):
        return dict(
            committers=[model.User(name=u'lmacken')]
        )

    def setUp(self):
        super(TestModulePackage, self).setUp()
        self.package = model.ModulePackage(name=u'the-greatest-package')
        self.db.add(self.package)

    def test_adding_rpmbuild(self):
        """Assert that validation fails when adding a RpmBuild."""
        build1 = model.ModuleBuild(nvr=u'the-greatest-package-1.0.0-fc17.1')
        build2 = model.RpmBuild(nvr=u'the-greatest-package-1.1.0-fc17.1')
        self.package.builds.append(build1)

        with self.assertRaises(ValueError) as exc_context:
            self.package.builds.append(build2)

        self.assertEqual(
            unicode(exc_context.exception),
            ("A RPM Build cannot be associated with a Module Package. A Package's "
             "builds must be the same type as the package."))

    def test_adding_list_of_module_and_rpmbuild(self):
        """Assert that validation fails when adding a ModuleBuild and RpmBuild via a list."""
        build1 = model.ModuleBuild(nvr=u'the-greatest-package-1.0.0-fc17.1')
        build2 = model.RpmBuild(nvr=u'the-greatest-package-1.1.0-fc17.1')

        with self.assertRaises(ValueError) as exc_context:
            self.package.builds = [build1, build2]

        self.assertEqual(
            unicode(exc_context.exception),
            ("A RPM Build cannot be associated with a Module Package. A Package's "
             "builds must be the same type as the package."))

    def test_backref_no_builds(self):
        """Assert that a ModuleBuild can be appended via a backref."""
        build = model.ModuleBuild(nvr=u'the-greatest-package-1.0.0-fc17.1')
        build.package = self.package

        # This should not raise any Exception.
        self.db.flush()

    def test_backref_rpmbuild(self):
        """Assert that adding an RpmBuild via backref fails validation."""
        build1 = model.ModuleBuild(nvr=u'the-greatest-package-1.0.0-fc17.1')
        build2 = model.RpmBuild(nvr=u'the-greatest-package-1.1.0-fc17.1')
        build1.package = self.package

        with self.assertRaises(ValueError) as exc_context:
            build2.package = self.package

        self.assertEqual(
            unicode(exc_context.exception),
            ("A RPM Build cannot be associated with a Module Package. A Package's "
             "builds must be the same type as the package."))

    def test_backref_second_modulebuild(self):
        """Assert that two ModuleBuilds can be appended via backrefs."""
        build1 = model.ModuleBuild(nvr=u'the-greatest-package-1.0.0-fc17.1')
        build2 = model.ModuleBuild(nvr=u'the-greatest-package-1.1.0-fc17.1')
        build1.package = self.package
        build2.package = self.package

        # This should not raise any Exception.
        self.db.flush()

    def test_no_builds(self):
        """Assert that one ModuleBuild can be appended."""
        build = model.ModuleBuild(nvr=u'the-greatest-package-1.0.0-fc17.1')
        self.package.builds.append(build)

        # This should not raise any Exception.
        self.db.flush()

    def test_same_build_types(self):
        """Assert that two builds of the module type can be added and that validation passes."""
        build1 = model.ModuleBuild(nvr=u'the-greatest-package-1.0.0-fc17.1')
        build2 = model.ModuleBuild(nvr=u'the-greatest-package-1.1.0-fc17.1')
        self.package.builds += [build1, build2]

        # This should not raise any Exception.
        self.db.flush()


class TestRpmPackage(ModelTest, unittest.TestCase):
    """Unit test case for the ``Package`` model."""
    klass = model.RpmPackage
    attrs = dict(name=u"TurboGears")

    def setUp(self):
        super(TestRpmPackage, self).setUp()
        self.package = model.RpmPackage(name=u'the-greatest-package')
        self.db.add(self.package)

    def do_get_dependencies(self):
        return dict(
            committers=[model.User(name=u'lmacken')]
        )

    def test_wiki_test_cases(self):
        """Test querying the wiki for test cases"""
        # Mock out mediawiki so we don't do network calls in our tests
        response = {
            'query': {
                'categorymembers': [{
                    'title': u'Fake test case',
                }],
            }
        }

        # Now, our actual test.
        with mock.patch('bodhi.server.models.MediaWiki', MockWiki(response)):
            config['query_wiki_test_cases'] = True
            pkg = model.RpmPackage(name=u'gnome-shell')
            pkg.fetch_test_cases(self.db)
            assert pkg.test_cases

    def test_adding_modulebuild(self):
        """Assert that validation fails when adding a ModuleBuild."""
        build1 = model.RpmBuild(nvr=u'the-greatest-package-1.0.0-fc17.1')
        build2 = model.ModuleBuild(nvr=u'the-greatest-package-1.1.0-fc17.1')
        self.package.builds.append(build1)

        with self.assertRaises(ValueError) as exc_context:
            self.package.builds.append(build2)

        self.assertEqual(
            unicode(exc_context.exception),
            ("A Module Build cannot be associated with a RPM Package. A Package's "
             "builds must be the same type as the package."))

    def test_backref_no_builds(self):
        """Assert that a RpmBuild can be appended via a backref."""
        build = model.RpmBuild(nvr=u'the-greatest-package-1.0.0-fc17.1')
        build.package = self.package

        # This should not raise any Exception.
        self.db.flush()

    def test_backref_modulebuild(self):
        """Assert that adding a ModuleBuild via backref fails validation."""
        build1 = model.RpmBuild(nvr=u'the-greatest-package-1.0.0-fc17.1')
        build2 = model.ModuleBuild(nvr=u'the-greatest-package-1.1.0-fc17.1')
        build1.package = self.package

        with self.assertRaises(ValueError) as exc_context:
            build2.package = self.package

        self.assertEqual(
            unicode(exc_context.exception),
            ("A Module Build cannot be associated with a RPM Package. A Package's "
             "builds must be the same type as the package."))

    def test_backref_second_modulebuild(self):
        """Assert that two RpmBuilds can be appended via backrefs."""
        build1 = model.RpmBuild(nvr=u'the-greatest-package-1.0.0-fc17.1')
        build2 = model.RpmBuild(nvr=u'the-greatest-package-1.1.0-fc17.1')
        build1.package = self.package
        build2.package = self.package

        # This should not raise any Exception.
        self.db.flush()

    def test_committers(self):
        assert self.obj.committers[0].name == u'lmacken'

    def test_no_builds(self):
        """Assert that one RpmBuild can be appended."""
        build = model.RpmBuild(nvr=u'the-greatest-package-1.0.0-fc17.1')
        self.package.builds.append(build)

        # This should not raise any Exception.
        self.db.flush()

    def test_same_build_types(self):
        """Assert that two builds of the RPM type can be added and that validation passes."""
        build1 = model.RpmBuild(nvr=u'the-greatest-package-1.0.0-fc17.1')
        build2 = model.RpmBuild(nvr=u'the-greatest-package-1.1.0-fc17.1')
        self.package.builds += [build1, build2]

        # This should not raise any Exception.
        self.db.flush()

    @mock.patch('bodhi.server.util.requests.get')
    def test_get_pkg_committers_from_pagure(self, mock_get):
        """ Ensure that the package committers can be found using the Pagure
        API.
        """
        json_output = {
            "access_groups": {
                "admin": [],
                "commit": ['factory2'],
                "ticket": []
            },
            "access_users": {
                "admin": [],
                "commit": [],
                "owner": [
                    "mprahl"
                ],
                "ticket": ["jsmith"]
            },
            "close_status": [],
            "custom_keys": [],
            "date_created": "1494947106",
            "description": "Python",
            "fullname": "rpms/python",
            "id": 2,
            "milestones": {},
            "name": "python",
            "namespace": "rpms",
            "parent": None,
            "priorities": {},
            "tags": [],
            "user": {
                "fullname": "Matt Prahl",
                "name": "mprahl"
            }
        }
        mock_get.return_value.json.return_value = json_output
        mock_get.return_value.status_code = 200
        rv = self.package.get_pkg_committers_from_pagure()
        assert rv == (['mprahl'], ['factory2']), rv

    @mock.patch('bodhi.server.util.requests.get')
    def test_get_pkg_committers_container_from_pagure(self, mock_get):
        """ Ensure that the container committers can be found using the Pagure
        API.
        """
        json_output = {
            "access_groups": {
                "admin": ["factory2"],
                "commit": [],
                "ticket": []
            },
            "access_users": {
                "admin": [],
                "commit": ["tbrady"],
                "owner": ["mprahl"],
                "ticket": ["jsmith"]
            },
            "close_status": [],
            "custom_keys": [],
            "date_created": "1494947106",
            "description": "Python",
            "fullname": "container/python",
            "id": 2,
            "milestones": {},
            "name": "python",
            "namespace": "container",
            "parent": None,
            "priorities": {},
            "tags": [],
            "user": {
                "fullname": "Matt Prahl",
                "name": "mprahl"
            }
        }
        mock_get.return_value.json.return_value = json_output
        mock_get.return_value.status_code = 200
        # Even though Bodhi doesn't support containers yet, let's mock this
        # package to have the type set to `container` to make sure the code in
        # get_pkg_committers_from_pagure works with containers in the future.
        self.package.type = mock.Mock()
        self.package.type.name = 'container'
        rv = self.package.get_pkg_committers_from_pagure()
        assert rv == (['tbrady', 'mprahl'], ['factory2']), rv


class TestBuild(ModelTest):
    """Test class for the ``Build`` model."""
    klass = model.Build
    attrs = dict(nvr=u"TurboGears-1.0.8-3.fc11")


class TestRpmBuild(ModelTest):
    """Unit test case for the ``RpmBuild`` model."""
    klass = model.RpmBuild
    attrs = dict(nvr=u"TurboGears-1.0.8-3.fc11")

    def do_get_dependencies(self):
        return dict(release=model.Release(**TestRelease.attrs),
                    package=model.RpmPackage(**TestRpmPackage.attrs))

    def test_release_relation(self):
        self.assertEqual(self.obj.release.name, u"F11")
        self.assertEqual(len(self.obj.release.builds), 1)
        self.assertEqual(self.obj.release.builds[0], self.obj)

    def test_package_relation(self):
        self.assertEqual(self.obj.package.name, u"TurboGears")
        self.assertEqual(len(self.obj.package.builds), 1)
        self.assertEqual(self.obj.package.builds[0], self.obj)

    def test_epoch(self):
        self.obj.epoch = '1'
        self.assertEqual(self.obj.evr, ("1", "1.0.8", "3.fc11"))

    def test_url(self):
        self.assertEqual(self.obj.get_url(), u'/TurboGears-1.0.8-3.fc11')


class TestUpdateValidateBuilds(BaseTestCase):
    """Tests for the :class:`Update` validator for builds."""

    def setUp(self):
        super(TestUpdateValidateBuilds, self).setUp()
        self.package = model.RpmPackage(name='the-greatest-package')
        self.update = model.Update(
            title='The best update of all time.',
            user=model.User.query.filter_by(name=u'guest').one(),
            request=model.UpdateRequest.testing,
            notes=u'Useless details!',
            release=model.Release.query.filter_by(name=u'F17').one(),
            date_submitted=datetime(1984, 11, 2),
            requirements=u'rpmlint',
            stable_karma=3,
            unstable_karma=-3,
            type=UpdateType.bugfix
        )

    def test_no_builds(self):
        """Assert when the first build is appended, the validator passes."""
        build = model.Build(
            nvr='the-greatest-package-1.0.0-fc17.1',
            package_id=self.package.id,
            release_id=self.update.release.id,
        )
        self.update.builds.append(build)

    def test_same_build_types(self):
        """Assert when all builds are the same type, validation passes."""
        build1 = model.RpmBuild(
            nvr='the-greatest-package-1.0.0-fc17.1',
            package_id=self.package.id,
            release_id=self.update.release.id,
        )
        build2 = model.RpmBuild(
            nvr='the-greatest-package-1.1.0-fc17.1',
            package_id=self.package.id,
            release_id=self.update.release.id,
        )
        self.update.builds += [build1, build2]

    def test_different_build_types(self):
        """Assert when all builds are a different type, validation fails."""
        build1 = model.Build(
            nvr='the-greatest-package-1.0.0-fc17.1',
            package_id=self.package.id,
            release_id=self.update.release.id,
        )
        build2 = model.RpmBuild(
            nvr='the-greatest-package-1.1.0-fc17.1',
            package_id=self.package.id,
            release_id=self.update.release.id,
        )
        self.update.builds.append(build1)
        self.assertRaises(ValueError, self.update.builds.append, build2)

    def test_backref_no_builds(self):
        """Assert when the first build is appended via a backref, the validator passes."""
        build = model.Build(
            nvr='the-greatest-package-1.0.0-fc17.1',
            package_id=self.package.id,
            release_id=self.update.release.id,
        )
        build.update = self.update

    def test_backref_same_build_types(self):
        """Assert when all builds are the same type and set via backref validation passes."""
        build1 = model.RpmBuild(
            nvr='the-greatest-package-1.0.0-fc17.1',
            package_id=self.package.id,
            release_id=self.update.release.id,
        )
        build2 = model.RpmBuild(
            nvr='the-greatest-package-1.1.0-fc17.1',
            package_id=self.package.id,
            release_id=self.update.release.id,
        )
        build1.update = self.update
        build2.update = self.update

    def test_backref_different_build_types(self):
        """Assert when builds differ in type and are set via backref validation passes."""
        build1 = model.Build(
            nvr='the-greatest-package-1.0.0-fc17.1',
            package_id=self.package.id,
            release_id=self.update.release.id,
        )
        build2 = model.RpmBuild(
            nvr='the-greatest-package-1.1.0-fc17.1',
            package_id=self.package.id,
            release_id=self.update.release.id,
        )
        build1.update = self.update
        with self.assertRaises(ValueError) as cm:
            build2.update = self.update

        self.assertEqual(str(cm.exception), u'An update must contain builds of the same type.')


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
        test_gating_status=TestGatingStatus.passed)

    def do_get_dependencies(self):
        release = model.Release(**TestRelease.attrs)
        return dict(
            builds=[model.RpmBuild(
                nvr=u'TurboGears-1.0.8-3.fc11', package=model.RpmPackage(**TestRpmPackage.attrs),
                release=release)],
            bugs=[model.Bug(bug_id=1), model.Bug(bug_id=2)],
            cves=[model.CVE(cve_id=u'CVE-2009-0001')],
            release=release,
            user=model.User(name=u'lmacken'))

    def get_update(self, name=u'TurboGears-1.0.8-3.fc11'):
        """Return an Update instance for testing."""
        attrs = self.attrs.copy()
        attrs['title'] = name
        pkg = self.db.query(model.RpmPackage).filter_by(name=u'TurboGears').one()
        rel = self.db.query(model.Release).filter_by(name=u'F11').one()
        attrs.update(dict(
            builds=[model.RpmBuild(nvr=name, package=pkg, release=rel)],
            release=rel))
        return self.klass(**attrs)

    def test___json___with_no_builds(self):
        """Test the __json__() method when there are no Builds."""
        self.obj.builds = []

        self.assertEqual(self.obj.__json__()['content_type'], None)

    @mock.patch('bodhi.server.models.log.warn')
    def test_add_tag_null(self, warn):
        """Test the add_tag() method with a falsey tag, such as None."""
        result = self.obj.add_tag(tag=None)

        self.assertEqual(result, [])
        warn.assert_called_once_with('Not adding builds of TurboGears-1.0.8-3.fc11 to empty tag')

    def test_autokarma_not_nullable(self):
        """Assert that the autokarma column does not allow NULL values.

        For history about why this is important, see
        https://github.com/fedora-infra/bodhi/issues/1048
        """
        self.assertEqual(model.Update.__table__.columns['autokarma'].nullable, False)

    def test_builds(self):
        self.assertEqual(len(self.obj.builds), 1)
        self.assertEqual(self.obj.builds[0].nvr, u'TurboGears-1.0.8-3.fc11')
        self.assertEqual(self.obj.builds[0].release.name, u'F11')
        self.assertEqual(self.obj.builds[0].package.name, u'TurboGears')

    def test_content_type(self):
        self.assertEqual(self.obj.content_type, model.ContentType.rpm)

    def test_greenwave_subject(self):
        """Ensure that the greenwave_subject property returns the correct value."""
        self.obj.assign_alias()

        self.assertEqual(
            self.obj.greenwave_subject,
            [{'item': u'TurboGears-1.0.8-3.fc11', 'type': 'koji_build'},
             {'original_spec_nvr': u'TurboGears-1.0.8-3.fc11'},
             {'item': self.obj.alias, 'type': 'bodhi_update'}])

    def test_greenwave_subject_json(self):
        """Ensure that the greenwave_subject_json property returns the correct value."""
        self.obj.assign_alias()

        subject = self.obj.greenwave_subject_json

        self.assertTrue(isinstance(subject, basestring))
        self.assertEqual(
            json.loads(subject),
            [{'item': u'TurboGears-1.0.8-3.fc11', 'type': 'koji_build'},
             {'original_spec_nvr': u'TurboGears-1.0.8-3.fc11'},
             {'item': self.obj.alias, 'type': 'bodhi_update'}])

    def test_mandatory_days_in_testing_critpath(self):
        """
        The Update.mandatory_days_in_testing method should be the configured value
        for critpath if it is a critpath update.
        """
        update = self.obj
        update.critpath = True

        # Configured value.
        expected = int(config.get('critpath.stable_after_days_without_negative_karma'))

        self.assertEqual(update.mandatory_days_in_testing, expected)

    def test_mandatory_days_in_testing(self):
        """
        The Update.mandatory_days_in_testing method should be a positive integer if the
        mandatory_days_in_testing attribute of release is not truthy.
        """
        update = self.obj

        self.assertEqual(update.mandatory_days_in_testing, 7)

    @mock.patch.dict('bodhi.server.models.config', {'fedora.mandatory_days_in_testing': '0'})
    def test_mandatory_days_in_testing_false(self):
        """
        The Update.mandatory_days_in_testing method should be 0 if the
        mandatory_days_in_testing attribute of release is not truthy.
        """
        update = self.obj

        self.assertEqual(update.mandatory_days_in_testing, 0)

    def test_days_to_stable_critpath(self):
        """
        The Update.days_to_stable() method should return a positive integer depending
        on the configuration.
        """
        update = self.get_update()
        update.critpath = True
        update.date_testing = datetime.utcnow() + timedelta(days=-4)

        criptath_days_to_stable = int(
            config.get('critpath.stable_after_days_without_negative_karma'))

        self.assertEqual(update.days_to_stable, criptath_days_to_stable - 4)

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
        self.assertEqual(update.meets_testing_requirements, True)

        self.assertEqual(update.days_to_stable, 0)

    def test_days_to_stable_not_meets_testing_requirements_no_date_testing(self):
        """
        The Update.days_to_stable() method should return 0 if Update.meets_testing_requirements()
        returns False but the Update's date_testing attribute is not truthy.
        """
        update = self.get_update()
        # Assert that our preconditions from the docblock are correct.
        self.assertEqual(update.meets_testing_requirements, False)
        self.assertEqual(update.date_testing, None)

        self.assertEqual(update.days_to_stable, 0)

    def test_days_to_stable_not_meets_testing_requirements_with_date_testing(self):
        """
        The Update.days_to_stable() method should return a positive integer if
        Update.meets_testing_requirements() returns False and the Update's date_testing attribute is
        truthy.
        """
        update = self.get_update()
        update.date_testing = datetime.utcnow() + timedelta(days=-4)
        # Assert that our preconditions from the docblock are correct.
        self.assertEqual(update.meets_testing_requirements, False)

        self.assertEqual(update.days_to_stable, 3)

    @mock.patch.dict('bodhi.server.config.config', {'test_gating.required': True})
    def test_days_to_stable_zero(self):
        """
        The Update.days_to_stable() method should only return a positive integer or zero.
        In the past, days_to_stable() could return negative integers when the mandatory days in
        testing was less than the number of days in testing. If the mandatory days in testing is
        less than or equal to the number of days in testing, days_to_stable() should return zero.
        See issue #1708.
        """
        update = self.obj
        update.autokarma = False
        update.test_gating_status = TestGatingStatus.failed

        update.date_testing = datetime.utcnow() + timedelta(days=-8)
        self.assertEqual(update.meets_testing_requirements, False)

        self.assertEqual(update.mandatory_days_in_testing <= update.days_in_testing, True)
        self.assertEqual(update.days_to_stable, 0)

    @mock.patch.dict('bodhi.server.config.config', {'test_gating.required': True})
    def test_days_to_stable_positive(self):
        """
        The Update.days_to_stable() method should only return a positive integer or zero.
        In the past, days_to_stable() could return negative integers when the mandatory days in
        testing was less than the number of days in testing. If the mandatory days in testing is
        greater than the number of days in testing, return the positive number of days until
        stable. See issue #1708.
        """
        update = self.obj
        update.autokarma = False
        update.test_gating_status = TestGatingStatus.failed

        update.date_testing = datetime.utcnow() + timedelta(days=-3)
        self.assertEqual(update.meets_testing_requirements, False)

        self.assertEqual(update.mandatory_days_in_testing > update.days_in_testing, True)
        self.assertEqual(update.days_to_stable, 4)

    @mock.patch.dict('bodhi.server.config.config', {'test_gating.required': True})
    def test_test_gating_faild_no_testing_requirements(self):
        """
        The Update.meets_testing_requirements() should return False, if the test gating
        status of an update is failed.
        """
        update = self.obj
        update.autokarma = False
        update.stable_karma = 1
        update.test_gating_status = TestGatingStatus.failed
        update.comment(self.db, u'I found $100 after applying this update.', karma=1,
                       author=u'bowlofeggs')
        # Assert that our preconditions from the docblock are correct.
        self.assertEqual(update.meets_testing_requirements, False)

    @mock.patch.dict('bodhi.server.config.config', {'test_gating.required': True})
    def test_test_gating_queued_no_testing_requirements(self):
        """
        The Update.meets_testing_requirements() should return False, if the test gating
        status of an update is queued.
        """
        update = self.obj
        update.autokarma = False
        update.stable_karma = 1
        update.test_gating_status = TestGatingStatus.queued
        update.comment(self.db, u'I found $100 after applying this update.', karma=1,
                       author=u'bowlofeggs')
        # Assert that our preconditions from the docblock are correct.
        self.assertEqual(update.meets_testing_requirements, False)

    @mock.patch.dict('bodhi.server.config.config', {'test_gating.required': True})
    def test_test_gating_running_no_testing_requirements(self):
        """
        The Update.meets_testing_requirements() should return False, if the test gating
        status of an update is running.
        """
        update = self.obj
        update.autokarma = False
        update.stable_karma = 1
        update.test_gating_status = TestGatingStatus.running
        update.comment(self.db, u'I found $100 after applying this update.', karma=1,
                       author=u'bowlofeggs')
        # Assert that our preconditions from the docblock are correct.
        self.assertEqual(update.meets_testing_requirements, False)

    @mock.patch.dict('bodhi.server.config.config', {'test_gating.required': True})
    def test_test_gating_missing_testing_requirements(self):
        """
        The Update.meets_testing_requirements() should return True, if the test gating
        status of an update is missing.
        """
        update = self.obj
        update.autokarma = False
        update.stable_karma = 1
        update.test_gating_status = None
        update.comment(self.db, u'I found $100 after applying this update.', karma=1,
                       author=u'bowlofeggs')
        # Assert that our preconditions from the docblock are correct.
        self.assertEqual(update.meets_testing_requirements, True)

    @mock.patch.dict('bodhi.server.config.config', {'test_gating.required': True})
    def test_test_gating_waiting_testing_requirements(self):
        """
        The Update.meets_testing_requirements() should return False, if the test gating
        status of an update is waiting.
        """
        update = self.obj
        update.autokarma = False
        update.stable_karma = 1
        update.test_gating_status = TestGatingStatus.waiting
        update.comment(self.db, u'I found $100 after applying this update.', karma=1,
                       author=u'bowlofeggs')
        # Assert that our preconditions from the docblock are correct.
        self.assertEqual(update.meets_testing_requirements, False)

    @mock.patch.dict('bodhi.server.config.config', {'test_gating.required': False})
    def test_test_gating_off(self):
        """
        The Update.meets_testing_requirements() should return True if the
        testing gating is not required, regardless of its test gating status.
        """
        update = self.obj
        update.autokarma = False
        update.stable_karma = 1
        update.test_gating_status = TestGatingStatus.running
        update.comment(self.db, u'I found $100 after applying this update.', karma=1,
                       author=u'bowlofeggs')
        # Assert that our preconditions from the docblock are correct.
        self.assertEqual(update.meets_testing_requirements, True)

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
        self.assertEqual(comment.call_count, 0)
        # Make sure close() was called correctly.
        self.assertEqual([c[1][0] for c in close.mock_calls], [1, 2])
        self.assertEqual(all(
            ['to the Fedora 11 stable repository' in c[2]['comment'] for c in close.mock_calls]),
            True)
        self.assertEqual(all(
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
        self.assertEqual([c[1][0] for c in comment.mock_calls], [1, 2])
        self.assertEqual(all(
            ['pushed to the Fedora 11 stable repository' in c[1][1] for c in comment.mock_calls]),
            True)
        # No bugs should have been closed
        self.assertEqual(close.call_count, 0)

    @mock.patch('bodhi.server.util.requests.get')
    @mock.patch.dict(util.config, {
        'critpath.type': 'pdc',
        'pdc_url': 'http://domain.local'
    })
    def test_contains_critpath_component(self, mock_get):
        """ Verifies that the static function of contains_critpath_component
        determines that one of the builds has a critpath component.
        """
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            'count': 2,
            'next': None,
            'previous': None,
            'results': [
                {
                    'active': True,
                    'critical_path': True,
                    'global_component': 'gcc',
                    'id': 6,
                    'name': 'f11',
                    'slas': [],
                    'type': 'rpm'
                },
                {
                    'active': True,
                    'critical_path': True,
                    'global_component': 'TurboGears',
                    'id': 7,
                    'name': 'f11',
                    'slas': [],
                    'type': 'rpm'
                }
            ]
        }
        update = self.get_update()
        self.assertTrue(update.contains_critpath_component(
            update.builds, update.release.name))

    @mock.patch('bodhi.server.util.requests.get')
    @mock.patch.dict(util.config, {
        'critpath.type': 'pdc',
        'pdc_url': 'http://domain.local'
    })
    def test_contains_critpath_component_not_critpath(self, mock_get):
        """ Verifies that the static function of contains_critpath_component
        determines that none of the builds are critpath components.
        """
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            'count': 2,
            'next': None,
            'previous': None,
            'results': [
                {
                    'active': True,
                    'critical_path': True,
                    'global_component': 'gcc',
                    'id': 6,
                    'name': 'f25',
                    'slas': [],
                    'type': 'rpm'
                },
                {
                    'active': True,
                    'critical_path': True,
                    'global_component': 'python',
                    'id': 7,
                    'name': 'f25',
                    'slas': [],
                    'type': 'rpm'
                }
            ]
        }
        update = self.get_update()
        # Use a different release here for additional testing and to avoid
        # caching from the previous test
        update.release = model.Release(
            name=u'fc25', long_name=u'Fedora 25',
            id_prefix=u'FEDORA', dist_tag=u'dist-fc25',
            stable_tag=u'dist-fc25-updates',
            testing_tag=u'dist-fc25-updates-testing',
            candidate_tag=u'dist-fc25-updates-candidate',
            pending_signing_tag=u'dist-fc25-updates-testing-signing',
            pending_testing_tag=u'dist-fc25-updates-testing-pending',
            pending_stable_tag=u'dist-fc25-updates-pending',
            override_tag=u'dist-fc25-override',
            branch=u'fc25', version=u'25')
        self.assertFalse(update.contains_critpath_component(
            update.builds, update.release.name))

    def test_unpush_build(self):
        self.assertEqual(len(self.obj.builds), 1)
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
        self.assertEqual(koji.__moved__, [(u'dist-f11-updates-testing',
                         u'dist-f11-updates-candidate', u'TurboGears-1.0.8-3.fc11')])
        self.assertEqual(koji.__untag__, [(u'dist-f11-updates-testing-signing',
                         u'TurboGears-1.0.8-3.fc11'), (u'dist-f11-updates-testing-pending',
                                                       u'TurboGears-1.0.8-3.fc11')])

    def test_title(self):
        self.assertEqual(self.obj.title, u'TurboGears-1.0.8-3.fc11')

    def test_beautify_title(self):
        update = self.get_update()
        rpm_build = update.builds[0]
        self.assertEqual(update.beautify_title(), u'TurboGears')
        self.assertEqual(update.beautify_title(nvr=True), u'TurboGears-1.0.8-3.fc11')

        update.builds.append(rpm_build)
        self.assertEqual(update.beautify_title(), u'TurboGears and TurboGears')
        self.assertEqual(
            update.beautify_title(nvr=True),
            u'TurboGears-1.0.8-3.fc11 and TurboGears-1.0.8-3.fc11')

        update.builds.append(rpm_build)
        self.assertEqual(update.beautify_title(), u'TurboGears, TurboGears, and 1 more')
        self.assertEqual(update.beautify_title(nvr=True),
                         u'TurboGears-1.0.8-3.fc11, TurboGears-1.0.8-3.fc11, and 1 more')

        p = HTMLParser()
        self.assertEqual(
            p.unescape(update.beautify_title(amp=True)), u'TurboGears, TurboGears, & 1 more')
        self.assertEqual(p.unescape(update.beautify_title(amp=True, nvr=True)),
                         u'TurboGears-1.0.8-3.fc11, TurboGears-1.0.8-3.fc11, & 1 more')

    def test_pkg_str(self):
        """ Ensure str(pkg) is correct """
        self.assertEqual(
            str(self.obj.builds[0].package),
            ('================================================================================\n   '
             '  TurboGears\n======================================================================='
             '=========\n\n Pending Updates (1)\n    o TurboGears-1.0.8-3.fc11\n'))

    def test_bugstring(self):
        self.assertEqual(self.obj.get_bugstring(), u'1 2')

    def test_cvestring(self):
        self.assertEqual(self.obj.get_cvestring(), u'CVE-2009-0001')

    def test_assign_alias(self):
        update = self.obj
        with mock.patch(target='uuid.uuid4', return_value='wat'):
            update.assign_alias()
        year = time.localtime()[0]
        idx = 'a3bbe1a8f2'
        self.assertEqual(update.alias, u'%s-%s-%s' % (update.release.id_prefix, year, idx))

        update = self.get_update(name=u'TurboGears-0.4.4-8.fc11')
        with mock.patch(target='uuid.uuid4', return_value='wat2'):
            update.assign_alias()
        idx = '016462d41f'
        self.assertEqual(update.alias, u'%s-%s-%s' % (update.release.id_prefix, year, idx))

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
        self.assertEqual(update.alias, u'%s-%s-%s' % (update.release.id_prefix, year, idx))

        newest = self.get_update(name=u'nethack-2.5.8-1.fc10')
        with mock.patch(target='uuid.uuid4', return_value='wat4'):
            newest.assign_alias()
        idx = '0efffa96f7'
        self.assertEqual(update.alias, u'%s-%s-%s' % (update.release.id_prefix, year, idx))

    def test_epel_id(self):
        """ Make sure we can handle id_prefixes that contain dashes.
        eg: FEDORA-EPEL
        """
        # Create a normal Fedora update first
        update = self.obj
        with mock.patch(target='uuid.uuid4', return_value='wat'):
            update.assign_alias()
        idx = 'a3bbe1a8f2'
        self.assertEqual(update.alias, u'FEDORA-%s-%s' % (time.localtime()[0], idx))

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
        self.assertEqual(update.alias, u'FEDORA-EPEL-%s-%s' % (time.localtime()[0], idx))

        update = self.get_update(name=u'TurboGears-2.2-1.el5')
        update.release = release
        idx = '016462d41f'
        with mock.patch(target='uuid.uuid4', return_value='wat2'):
            update.assign_alias()
        self.assertEqual(update.alias, u'%s-%s-%s' % (
            release.id_prefix, time.localtime()[0], idx))

    def test_dupe(self):
        with self.assertRaises(IntegrityError):
            session = Session()
            session.add(self.get_update())
            session.commit()
            session.add(self.get_update())
            session.commit()

    def test_karma_no_comments(self):
        """Check that karma returns the correct value with one negative and two positive comments.
        """
        self.assertEqual(self.obj.karma, 0)

    def test_karma_one_negative_two_positive(self):
        """Check that karma returns the correct value with one negative and two positive comments.
        """
        self.obj.comment(self.db, u"foo", 1, u'foo')
        self.obj.comment(self.db, u"foo", -1, u'bar')
        self.obj.comment(self.db, u"foo", 1, u'biz')

        self.assertEqual(self.obj.karma, 1)

    def test_karma_two_negative_one_positive(self):
        """Check that karma returns the correct value with two negative and one positive comments.
        """
        self.obj.comment(self.db, u"foo", -1, u'foo')
        self.obj.comment(self.db, u"foo", -1, u'bar')
        self.obj.comment(self.db, u"foo", 1, u'biz')

        self.assertEqual(self.obj.karma, -1)

    def test__composite_karma_ignores_anonymous_karma(self):
        """Assert that _composite_karma ignores anonymous karma."""
        self.obj.comment(self.db, u"foo", -1, u'foo')
        self.obj.comment(self.db, u"foo", -1, u'bar')
        # This one shouldn't get counted
        self.obj.comment(self.db, u"foo", 1, u'biz', anonymous=True)

        self.assertEqual(self.obj._composite_karma, (0, -2))

    def test__composite_karma_ignores_comments_before_new_build(self):
        """Assert that _composite_karma ignores karma from before a new build karma reset event."""
        self.obj.comment(self.db, u"foo", -1, u'foo')
        self.obj.comment(self.db, u"foo", -1, u'bar')
        # This is a "karma reset event", so the above comments should not be counted in the karma.
        self.obj.comment(self.db, u"New build", 0, u'bodhi')
        self.obj.comment(self.db, u"foo", 1, u'biz')

        self.assertEqual(self.obj._composite_karma, (1, 0))

    def test__composite_karma_ignores_comments_before_removed_build(self):
        """Assert that _composite_karma ignores karma from before a removed build karma reset event.
        """
        self.obj.comment(self.db, u"foo", 1, u'foo')
        self.obj.comment(self.db, u"foo", 1, u'bar')
        # This is a "karma reset event", so the above comments should not be counted in the karma.
        self.obj.comment(self.db, u"Removed build", 0, u'bodhi')
        self.obj.comment(self.db, u"foo", -1, u'biz')

        self.assertEqual(self.obj._composite_karma, (0, -1))

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
        self.assertEqual(self.obj._composite_karma, (1, -1))

    def test__composite_karma_ignores_old_comments(self):
        """Assert that _composite_karma ignores karma from a user's previous responses."""
        self.obj.comment(self.db, u"I", -1, u'foo')
        self.obj.comment(self.db, u"can't", 1, u'foo')
        self.obj.comment(self.db, u"make", -1, u'foo')
        self.obj.comment(self.db, u"up", 1, u'foo')
        self.obj.comment(self.db, u"my", -1, u'foo')
        self.obj.comment(self.db, u"mind", 1, u'foo')
        self.obj.comment(self.db, u".", -37, u'foo')

        self.assertEqual(self.obj._composite_karma, (0, -37))

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

        self.assertEqual(self.obj._composite_karma, (2, -1))

    def test__composite_karma_no_comments(self):
        """Assert _composite_karma with no comments is (0, 0)."""
        self.assertEqual(self.obj._composite_karma, (0, 0))

    def test__composite_karma_one_negative_two_positive(self):
        """Assert that _composite_karma returns (2, -1) with one negative and two positive comments.
        """
        self.obj.comment(self.db, u"foo", 1, u'foo')
        self.obj.comment(self.db, u"foo", -1, u'bar')
        self.obj.comment(self.db, u"foo", 1, u'biz')

        self.assertEqual(self.obj._composite_karma, (2, -1))

    @mock.patch('bodhi.server.notifications.publish')
    def test_stable_karma(self, publish):
        update = self.obj
        update.request = None
        update.status = UpdateStatus.testing
        self.assertEqual(update.karma, 0)
        self.assertEqual(update.request, None)
        update.comment(self.db, u"foo", 1, u'foo')
        self.assertEqual(update.karma, 1)
        self.assertEqual(update.request, None)
        update.comment(self.db, u"foo", 1, u'bar')
        self.assertEqual(update.karma, 2)
        self.assertEqual(update.request, None)
        update.comment(self.db, u"foo", 1, u'biz')
        self.assertEqual(update.karma, 3)
        self.assertEqual(update.request, UpdateRequest.batched)
        publish.assert_called_with(topic='update.comment', msg=mock.ANY)

    @mock.patch('bodhi.server.notifications.publish')
    def test_unstable_karma(self, publish):
        update = self.obj
        update.status = UpdateStatus.testing
        self.assertEqual(update.karma, 0)
        self.assertEqual(update.status, UpdateStatus.testing)
        update.comment(self.db, u"foo", -1, u'foo')
        self.assertEqual(update.status, UpdateStatus.testing)
        self.assertEqual(update.karma, -1)
        update.comment(self.db, u"bar", -1, u'bar')
        self.assertEqual(update.status, UpdateStatus.testing)
        self.assertEqual(update.karma, -2)
        update.comment(self.db, u"biz", -1, u'biz')
        self.assertEqual(update.karma, -3)
        self.assertEqual(update.status, UpdateStatus.obsolete)
        publish.assert_called_with(topic='update.comment', msg=mock.ANY)

    def test_update_bugs(self):
        update = self.obj
        self.assertEqual(len(update.bugs), 2)
        session = self.db

        # try just adding bugs
        bugs = ['1234']
        update.update_bugs(bugs, session)
        self.assertEqual(len(update.bugs), 1)
        self.assertEqual(update.bugs[0].bug_id, 1234)

        # try just removing
        bugs = []
        update.update_bugs(bugs, session)
        self.assertEqual(len(update.bugs), 0)
        self.assertEqual(self.db.query(model.Bug).filter_by(bug_id=1234).first(), None)

        # Test new duplicate bugs
        bugs = ['1234', '1234']
        update.update_bugs(bugs, session)
        assert len(update.bugs) == 1

        # Try adding a new bug, and removing the rest
        bugs = ['4321']
        update.update_bugs(bugs, session)
        assert len(update.bugs) == 1
        assert update.bugs[0].bug_id == 4321
        self.assertEqual(self.db.query(model.Bug).filter_by(bug_id=1234).first(), None)

        # Try removing a bug when it already has BugKarma
        karma = BugKarma(bug_id=4321, karma=1)
        self.db.add(karma)
        self.db.flush()
        bugs = ['5678']
        update.update_bugs(bugs, session)
        assert len(update.bugs) == 1
        assert update.bugs[0].bug_id == 5678
        self.assertEqual(self.db.query(model.Bug).filter_by(bug_id=4321).count(), 1)

    def test_unicode_bug_title(self):
        bug = self.obj.bugs[0]
        bug.title = u'foo\xe9bar'
        from bodhi.server.util import bug_link
        link = bug_link(None, bug)
        self.assertEqual(
            link, (u"<a target='_blank' href='https://bugzilla.redhat.com/show_bug.cgi?id=1'>#1</a>"
                   u" foo\xe9bar"))

    def test_set_request_untested_stable(self):
        """
        Ensure that we can't submit an update for stable if it hasn't met the
        minimum testing requirements.
        """
        req = DummyRequest(user=DummyUser())
        req.errors = cornice.Errors()
        req.koji = buildsys.get_session()
        self.assertEqual(self.obj.status, UpdateStatus.pending)
        try:
            self.obj.set_request(self.db, UpdateRequest.stable, req.user.name)
            assert False
        except BodhiException as e:
            pass
        self.assertEqual(self.obj.request, UpdateRequest.testing)
        self.assertEqual(self.obj.status, UpdateStatus.pending)
        self.assertEqual(str(e), config.get('not_yet_tested_msg'))

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
        self.assertEqual(self.obj.days_in_testing, 7)
        self.assertEqual(self.obj.meets_testing_requirements, True)

        self.obj.set_request(self.db, UpdateRequest.stable, req)
        self.assertEqual(self.obj.request, UpdateRequest.stable)
        self.assertEqual(len(req.errors), 0)
        publish.assert_called_once_with(
            topic='update.request.stable', msg=mock.ANY)

    @mock.patch.dict('bodhi.server.config.config', {'test_gating.required': True})
    def test_set_request_stable_for_critpath_update_when_test_gating_enabled(self):
        """
        Ensure that we can't submit a critpath update for stable if it hasn't passed the
        test gating and return the error message as expected.
        """
        req = DummyRequest()
        req.errors = cornice.Errors()
        req.koji = buildsys.get_session()
        req.user = model.User(name='bob')

        self.obj.status = UpdateStatus.testing
        self.obj.request = None
        self.obj.critpath = True
        self.obj.test_gating_satus = TestGatingStatus.failed
        try:
            self.obj.set_request(self.db, UpdateRequest.stable, req.user.name)
            assert False
        except BodhiException as e:
            pass
        expected_msg = (
            'This critical path update has not yet been approved for pushing to the '
            'stable repository.  It must first reach a karma of %s, consisting of %s '
            'positive karma from proventesters, along with %d additional karma from '
            'the community. Or, it must spend %s days in testing without any negative '
            'feedback')
        expected_msg = expected_msg % (
            config.get('critpath.min_karma'),
            config.get('critpath.num_admin_approvals'),
            (config.get('critpath.min_karma') -
                config.get('critpath.num_admin_approvals')),
            config.get('critpath.stable_after_days_without_negative_karma'))
        expected_msg += ' Additionally, it must pass automated tests.'
        self.assertEqual(str(e), expected_msg)

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
        self.assertEqual(self.obj.days_in_testing, 7)
        # The update should be eligible to receive the testing_approval_msg now.
        self.assertEqual(self.obj.meets_testing_requirements, True)
        # Add the testing_approval_message
        text = unicode(config.get('testing_approval_msg') % self.obj.days_in_testing)
        self.obj.comment(self.db, text, author=u'bodhi')

        # met_testing_requirement() should return True since Bodhi has commented on the Update to
        # say that it can now be pushed to stable.
        self.assertEqual(self.obj.met_testing_requirements, True)

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
        self.assertEqual(self.obj.days_in_testing, 7)
        # The update should be eligible to receive the testing_approval_msg now.
        self.assertEqual(self.obj.meets_testing_requirements, True)

        # Since bodhi hasn't added the testing_approval_message yet, this should be False.
        self.assertEqual(self.obj.met_testing_requirements, False)

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
        self.assertEqual(self.obj.meets_testing_requirements, False)

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
        self.assertEqual(self.obj.meets_testing_requirements, True)

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
        self.assertEqual(self.obj.meets_testing_requirements, False)

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
        self.assertEqual(self.obj.meets_testing_requirements, False)

    def test_meets_testing_requirements_critpath_negative_karma(self):
        """
        Assert that meets_testing_requirements() correctly returns False for critpath updates
        with negative karma.
        """
        update = self.obj
        update.critpath = True
        update.comment(self.db, u'testing', author=u'enemy', anonymous=False, karma=-1)
        self.assertEqual(update.meets_testing_requirements, False)

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
        self.assertEqual(self.obj.days_in_testing, 1)
        # Now let's add some karma to get it to the required threshold
        self.obj.comment(self.db, u'testing', author=u'hunter1', anonymous=False, karma=1)
        self.obj.comment(self.db, u'testing', author=u'hunter2', anonymous=False, karma=1)
        self.obj.comment(self.db, u'testing', author=u'hunter3', anonymous=False, karma=1)
        # Add the testing_approval_message
        text = unicode(config.get('testing_approval_msg_based_on_karma'))
        self.obj.comment(self.db, text, author=u'bodhi')

        # met_testing_requirement() should return True since Bodhi has commented on the Update to
        # say that it can now be pushed to stable.
        self.assertEqual(self.obj.met_testing_requirements, True)

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
        self.assertEqual(self.obj.days_in_testing, 1)
        # Now let's add some karma to get it to the required threshold
        self.obj.comment(self.db, u'testing', author=u'hunter1', anonymous=False, karma=1)
        self.obj.comment(self.db, u'testing', author=u'hunter2', anonymous=False, karma=1)
        self.obj.comment(self.db, u'testing', author=u'hunter3', anonymous=False, karma=1)

        # met_testing_requirement() should return False since Bodhi has not yet commented on the
        # Update to say that it can now be pushed to stable.
        self.assertEqual(self.obj.met_testing_requirements, False)

    @mock.patch('bodhi.server.notifications.publish')
    def test_set_request_obsolete(self, publish):
        req = DummyRequest(user=DummyUser())
        req.errors = cornice.Errors()
        self.assertEqual(self.obj.status, UpdateStatus.pending)
        self.obj.set_request(self.db, UpdateRequest.obsolete, req.user.name)
        self.assertEqual(self.obj.status, UpdateStatus.obsolete)
        self.assertEqual(len(req.errors), 0)
        publish.assert_called_once_with(
            topic='update.request.obsolete', msg=mock.ANY)

    @mock.patch('bodhi.server.notifications.publish')
    def test_request_complete(self, publish):
        self.obj.request = None
        self.assertEqual(self.obj.date_pushed, None)
        self.obj.request = UpdateRequest.testing
        self.obj.request_complete()
        assert self.obj.date_pushed
        self.assertEqual(self.obj.status, UpdateStatus.testing)

    def test_status_comment(self):
        self.obj.status = UpdateStatus.testing
        self.obj.status_comment(self.db)
        self.assertEqual(len(self.obj.comments), 1)
        self.assertEqual(self.obj.comments[0].user.name, u'bodhi')
        self.assertEqual(self.obj.comments[0].text, u'This update has been pushed to testing.')
        self.obj.status = UpdateStatus.stable
        self.obj.status_comment(self.db)
        self.assertEqual(len(self.obj.comments), 2)
        self.assertEqual(self.obj.comments[1].user.name, u'bodhi')
        self.assertEqual(self.obj.comments[1].text, u'This update has been pushed to stable.')
        assert str(self.obj.comments[1]).endswith('This update has been pushed to stable.')

    @mock.patch('bodhi.server.notifications.publish')
    def test_anonymous_comment(self, publish):
        self.obj.comment(self.db, u'testing', author='me', anonymous=True, karma=1)
        c = self.obj.comments[-1]
        assert str(c).endswith('testing')
        self.assertEqual(c.anonymous, True)
        self.assertEqual(c.text, 'testing')
        publish.assert_called_once_with(
            topic='update.comment', msg=mock.ANY)
        args, kwargs = publish.call_args
        self.assertEqual(kwargs['msg']['comment']['author'], 'anonymous')

    def test_get_url(self):
        self.assertEqual(self.obj.get_url(), u'updates/TurboGears-1.0.8-3.fc11')
        idx = 'a3bbe1a8f2'
        with mock.patch(target='uuid.uuid4', return_value='wat'):
            self.obj.assign_alias()
        expected = u'updates/FEDORA-%s-%s' % (time.localtime()[0], idx)
        self.assertEqual(self.obj.get_url(), expected)

    def test_bug(self):
        bug = self.obj.bugs[0]
        self.assertEqual(bug.url, 'https://bugzilla.redhat.com/show_bug.cgi?id=1')
        bug.testing(self.obj)
        bug.add_comment(self.obj)
        bug.add_comment(self.obj, comment='testing')
        bug.close_bug(self.obj)
        self.obj.status = UpdateStatus.testing
        bug.add_comment(self.obj)

    def test_cve(self):
        cve = self.obj.cves[0]
        self.assertEqual(cve.url, 'http://www.cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2009-0001')

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

    def test_check_requirements_empty(self):
        '''Empty requirements are OK'''
        update = self.obj
        settings = {'resultsdb_api_url': ''}

        for req in ['', None]:
            update.requirements = req

            result, reason = update.check_requirements(None, settings)

            self.assertTrue(result)
            self.assertEqual(reason, "No checks required.")

    @mock.patch('bodhi.server.models.Update.last_modified',
                new_callable=mock.PropertyMock)
    def test_check_requirements_no_last_modified(self, mock_last_modified):
        '''Missing last_modified should fail the check'''
        update = self.obj
        mock_last_modified.return_value = None
        update.requirements = 'rpmlint abicheck'
        settings = {'resultsdb_api_url': ''}

        result, reason = update.check_requirements(None, settings)

        self.assertFalse(result)
        self.assertIn("Failed to determine last_modified", reason)

    @mock.patch('bodhi.server.util.taskotron_results')
    def test_check_requirements_query_error(self, mock_taskotron_results):
        '''Error during retrieving results should fail'''
        update = self.obj
        update.requirements = 'rpmlint abicheck'
        settings = {'resultsdb_api_url': ''}
        mock_taskotron_results.side_effect = Exception('Query failed')

        result, reason = update.check_requirements(None, settings)

        self.assertFalse(result)
        self.assertIn("Failed retrieving requirements results", reason)

    @mock.patch('bodhi.server.util.taskotron_results')
    def test_check_requirements_no_results(self, mock_taskotron_results):
        '''No results for a testcase means fail'''
        update = self.obj
        update.requirements = 'rpmlint abicheck'
        settings = {'resultsdb_api_url': ''}
        results = [{'testcase': {'name': 'rpmlint'},
                    'data': {},
                    'outcome': 'PASSED'}]
        mock_taskotron_results.return_value = iter(results)

        result, reason = update.check_requirements(None, settings)

        self.assertFalse(result)
        self.assertEqual("No result found for required testcase abicheck",
                         reason)

    @mock.patch('bodhi.server.util.taskotron_results')
    def test_check_requirements_failed_results(self, mock_taskotron_results):
        '''Failed results for a testcase means fail'''
        update = self.obj
        update.requirements = 'rpmlint abicheck'
        settings = {'resultsdb_api_url': ''}
        results = [{'testcase': {'name': 'rpmlint'},
                    'data': {},
                    'outcome': 'FAILED'}]
        mock_taskotron_results.return_value = iter(results)

        result, reason = update.check_requirements(None, settings)

        self.assertFalse(result)
        self.assertEqual("Required task rpmlint returned FAILED",
                         reason)

    @mock.patch('bodhi.server.util.taskotron_results')
    def test_check_requirements_pass(self, mock_taskotron_results):
        '''All testcases pass means pass'''
        update = self.obj
        update.requirements = 'rpmlint abicheck'
        settings = {'resultsdb_api_url': ''}
        results = [{'testcase': {'name': 'rpmlint'},
                    'data': {},
                    'outcome': 'PASSED'},
                   {'testcase': {'name': 'abicheck'},
                    'data': {},
                    'outcome': 'PASSED'}]
        mock_taskotron_results.return_value = iter(results)

        result, reason = update.check_requirements(None, settings)

        self.assertTrue(result)
        self.assertEqual("All checks pass.", reason)

    @mock.patch('bodhi.server.util.taskotron_results')
    @mock.patch('bodhi.server.buildsys.DevBuildsys.multiCall')
    def test_check_requirements_koji_error(self, mock_multiCall,
                                           mock_taskotron_results):
        '''Koji error means fail'''
        update = self.obj
        update.requirements = 'rpmlint abicheck'
        settings = {'resultsdb_api_url': ''}
        results = []
        mock_taskotron_results.return_value = iter(results)
        mock_multiCall.return_value = [{'error code': 'error description'}]

        result, reason = update.check_requirements(None, settings)

        self.assertFalse(result)
        self.assertIn("Failed retrieving requirements results:", reason)
        self.assertIn("Error retrieving data from Koji for", reason)

    def test_test_cases_with_no_dupes(self):
        update = self.get_update(name=u"FullTestCasesWithNoDupes")
        package = update.builds[0].package
        test1 = model.TestCase(name=u"Test 1", package=package)
        test2 = model.TestCase(name=u"Test 2", package=package)
        model.TestCase(name=u"Test 2", package=package)

        tests = update.full_test_cases
        test_names = update.test_cases

        expected = [test1, test2]
        expected_names = [u"Test 1", u"Test 2"]

        self.assertEqual(len(tests), len(expected))
        self.assertEqual(sorted(tests), sorted(expected))

        self.assertEqual(len(test_names), len(expected_names))
        self.assertEqual(sorted(test_names), sorted(expected_names))


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
            build=model.RpmBuild(
                nvr=u'TurboGears-1.0.8-3.fc11', package=model.RpmPackage(**TestRpmPackage.attrs),
                release=model.Release(**TestRelease.attrs)),
            submitter=model.User(name=u'lmacken'))
