# Copyright © 2011-2019 Red Hat, Inc. and others.
#
# This file is part of Bodhi.
#
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
from unittest import mock
from urllib.error import URLError
import hashlib
import html
import json
import pickle
import time
import uuid

from fedora_messaging.api import Message
from fedora_messaging.testing import mock_sends
from pyramid.testing import DummyRequest
from sqlalchemy.exc import IntegrityError
import cornice
import pytest
import requests.exceptions

from bodhi.messages.schemas import errata as errata_schemas
from bodhi.messages.schemas import update as update_schemas
from bodhi.server import buildsys, mail
from bodhi.server import models as model
from bodhi.server import Session, util
from bodhi.server.config import config
from bodhi.server.exceptions import (
    BodhiException,
    ExternalCallException,
    LockedUpdateException,
)
from bodhi.server.models import (
    BugKarma,
    PackageManager,
    ReleaseState,
    TestGatingStatus,
    UpdateRequest,
    UpdateSeverity,
    UpdateStatus,
    UpdateSuggestion,
    UpdateType,
)

from .base import BasePyTestCase, DummyUser


class ModelTest(BasePyTestCase):
    """Base unit test case for the models."""

    klass = None
    attrs = {}
    _populate_db = False

    def setup_method(self):
        super(ModelTest, self).setup_method(self)
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
            except Exception:
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
        for key, value in self.attrs.items():
            assert getattr(self.obj, key) == value

    def test_json(self):
        """ Ensure our models can return valid JSON """
        if type(self) != ModelTest:
            assert isinstance(json.dumps(self.obj.__json__()), str)

    def test_get(self):
        if type(self) != ModelTest:
            for col in self.obj.__get_by__:
                assert self.klass.get(getattr(self.obj, col)) == self.obj


class TestBodhiBase(BasePyTestCase):
    """Test the BodhiBase class."""

    def test__expand_with_m2m_relation(self):
        """Test the _expand() method with a many-to-many relation."""
        u = model.Update.query.all()[0]
        # u.bugs is an InstrumentedList, which doesn't have an all() method. We have some
        # code to handle m2m relationships with all() methods, but it's not immediately obvious
        # which relationships have that for testing purposes. Thus, we can simulate this for
        # test coverage purposes by setting it to its __iter__() method.
        u.bugs.all = u.bugs.__iter__

        bugs = u._expand(u, u.bugs, [], mock.MagicMock())

        assert len(bugs) == 1
        assert bugs[0]['bug_id'] == 12345

    def test__expand_with_relation_in_seen(self):
        """_expand() should return the relation.id attribute if its type is in seen."""
        b = model.Build.query.all()[0]

        assert b._expand(b, b.package, [type(b.package)], mock.MagicMock()) == b.package.id

    def test__json__exclude(self):
        """Test __json__()'s exclude flag."""
        c = model.Comment.query.all()[0]
        j_with_text = c.__json__()
        assert 'text' in j_with_text

        j = c.__json__(exclude=['text'])

        assert 'text' not in j
        # If we remove the 'text' attribute from j_with_text, j should be equal to what remains.
        del j_with_text['text']
        assert j == j_with_text

    def test___json___include(self):
        """Test __json__()'s include flag."""
        c = model.Comment.query.all()[0]
        j_with_text = c.__json__()
        assert 'unique_testcase_feedback' not in j_with_text

        j = c.__json__(include=['unique_testcase_feedback'])

        assert 'unique_testcase_feedback' in j
        assert j['unique_testcase_feedback'] == []
        # If we add unique_testcase_feedback to j_with_text, it should be identical.
        j_with_text['unique_testcase_feedback'] = j['unique_testcase_feedback']
        assert j == j_with_text

    def test__to_json_exclude(self):
        """Test _to_json()'s exclude flag."""
        c = model.Comment.query.all()[0]
        j_with_text = c._to_json(c)
        assert 'text' in j_with_text

        j = model.Comment._to_json(c, exclude=['text'])

        assert 'text' not in j
        # If we remove the 'text' attribute from j_with_text, j should be equal to what remains.
        del j_with_text['text']
        assert j == j_with_text

    def test__to_json_include(self):
        """Test _to_json()'s include flag."""
        c = model.Comment.query.all()[0]
        j_with_text = c._to_json(c)
        assert 'unique_testcase_feedback' not in j_with_text

        j = model.Comment._to_json(c, include=['unique_testcase_feedback'])

        assert 'unique_testcase_feedback' in j
        assert j['unique_testcase_feedback'] == []
        # If we add unique_testcase_feedback to j_with_text, it should be identical.
        j_with_text['unique_testcase_feedback'] = j['unique_testcase_feedback']
        assert j == j_with_text

    def test__to_json_falsey_object(self):
        """Assert that _to_json() returns None when handed a Falsey object."""
        assert model.Build._to_json(False, seen=None) is None
        assert model.Build._to_json(None, seen=None) is None
        assert model.Build._to_json('', seen=None) is None
        assert model.Build._to_json([], seen=None) is None

    def test__to_json_no_seen(self):
        """Assert correct behavior from _to_json() when seen is None."""
        b = model.Build.query.all()[0]

        j = b._to_json(b, seen=None)

        assert j == (
            {'release_id': 1, 'epoch': b.epoch, 'nvr': b.nvr,
             'signed': b.signed, 'type': str(b.type.value)})

    def test_grid_columns(self):
        """Assert correct return value from the grid_columns() method."""
        assert sorted(model.Build.grid_columns()) == sorted(['nvr', 'signed', 'release_id',
                                                             'type', 'epoch'])

    def test_find_child_for_rpm(self):
        subclass = model.Package.find_polymorphic_child(model.ContentType.rpm)
        assert subclass == model.RpmPackage
        subclass = model.Build.find_polymorphic_child(model.ContentType.rpm)
        assert subclass == model.RpmBuild
        subclass = model.Package.find_polymorphic_child(model.ContentType.module)
        assert subclass == model.ModulePackage
        subclass = model.Build.find_polymorphic_child(model.ContentType.module)
        assert subclass == model.ModuleBuild

    def test_find_child_with_bad_identity(self):
        with pytest.raises(NameError):
            model.Package.find_polymorphic_child(model.UpdateType.security)

    def test_find_child_with_bad_base_class(self):
        with pytest.raises(KeyError):
            model.Update.find_polymorphic_child(model.ContentType.rpm)

    def test_find_child_with_badly_typed_argument(self):
        with pytest.raises(TypeError):
            model.Update.find_polymorphic_child("whatever")


class TestBugAddComment(BasePyTestCase):
    """Test Bug.add_comment()."""

    @mock.patch('bodhi.server.models.bugs.bugtracker.comment')
    @mock.patch('bodhi.server.models.log.debug')
    def test_parent_security_bug(self, debug, comment):
        """The method should not comment on a parent security bug."""
        update = model.Update.query.first()
        update.type = model.UpdateType.security
        bug = model.Bug.query.first()
        bug.parent = True

        bug.add_comment(update)

        debug.assert_called_once_with('Not commenting on parent security bug %s', bug.bug_id)
        assert comment.call_count == 0


class TestBugDefaultMessage(BasePyTestCase):
    """Test Bug.default_message()."""

    def test_default_msg_error(self):
        """Test we raise a ValueError if the update is not in stable or testing."""
        bug = model.Bug()
        update = model.Update.query.first()
        update.status = UpdateStatus.pending

        with pytest.raises(ValueError) as exc:
            bug.default_message(update)
        assert str(exc.value) == (
            f'Trying to post a default comment to a bug, but '
            f'{update.alias} is not in Stable or Testing status.')

    @mock.patch.dict(config, {'stable_bug_msg': 'cool fedora stuff {update_alias}',
                              'testing_bug_msg': 'not here'})
    def test_stable_bug_msg(self):
        """Test default message when update is in stable."""
        bug = model.Bug()
        update = model.Update.query.first()
        update.release.id_prefix = 'FEDORA'
        update.status = UpdateStatus.stable

        message = bug.default_message(update)

        assert 'cool fedora stuff {}'.format(update.alias) == message
        assert 'not here' not in message

    @mock.patch.dict(config, {'stable_bug_msg': 'not here',
                              'testing_bug_msg': 'cool fedora stuff {update_alias}'})
    def test_testing_bug_msg(self):
        """Test default message when update is in testing."""
        bug = model.Bug()
        update = model.Update.query.first()
        update.release.id_prefix = 'FEDORA'
        update.status = UpdateStatus.testing

        message = bug.default_message(update)

        assert 'cool fedora stuff {}'.format(update.alias) == message
        assert 'not here' not in message

    def test_epel_with_testing_bug_epel_msg(self):
        """Test with testing_bug_epel_msg defined."""
        config['testing_bug_epel_msg'] = 'cool epel stuff {update_url}'
        bug = model.Bug()
        update = model.Update.query.first()
        update.release.id_prefix = 'FEDORA-EPEL'
        update.status = UpdateStatus.testing

        message = bug.default_message(update)

        assert 'cool epel stuff {}'.format(config['base_address'] + update.get_url()) == message

    @mock.patch('bodhi.server.models.log.warning')
    def test_epel_without_testing_bug_epel_msg(self, warning):
        """Test with testing_bug_epel_msg undefined."""
        config.update({
            'testing_bug_msg': 'cool fedora stuff {update_url}',
            'base_address': 'b',
            'critpath.min_karma': 1,
            'fedora_epel.mandatory_days_in_testing': 0
        })
        del config["testing_bug_epel_msg"]
        bug = model.Bug()
        update = model.Update.query.first()
        update.release.id_prefix = 'FEDORA-EPEL'
        update.status = UpdateStatus.testing

        message = bug.default_message(update)

        warning.assert_called_once_with("No 'testing_bug_epel_msg' found in the config.")
        assert 'cool fedora stuff {}'.format(config['base_address'] + update.get_url()) == message


class TestBugModified(BasePyTestCase):
    """Test Bug.modified()."""

    @mock.patch('bodhi.server.models.bugs.bugtracker.modified')
    @mock.patch('bodhi.server.models.log.debug')
    def test_parent_security_bug(self, debug, modified):
        """The method should not act on a parent security bug."""
        update = model.Update.query.first()
        update.type = model.UpdateType.security
        bug = model.Bug.query.first()
        bug.parent = True

        bug.modified(update, 'this should not be used')

        debug.assert_called_once_with('Not modifying parent security bug %s', bug.bug_id)
        assert modified.call_count == 0


class TestBugTesting(BasePyTestCase):
    """Test Bug.testing()."""

    @mock.patch('bodhi.server.models.bugs.bugtracker.on_qa')
    @mock.patch('bodhi.server.models.log.debug')
    def test_parent_security_bug(self, debug, on_qa):
        """The method should not act on a parent security bug."""
        update = model.Update.query.first()
        update.type = model.UpdateType.security
        bug = model.Bug.query.first()
        bug.parent = True

        bug.testing(update)

        debug.assert_called_once_with('Not modifying parent security bug %s', bug.bug_id)
        assert on_qa.call_count == 0


class TestQueryProperty(BasePyTestCase):

    def test_session(self):
        """Assert the session the query property uses is from the scoped session."""
        query = model.Package.query
        assert self.db is query.session


class TestComment(BasePyTestCase):
    def test_text_not_nullable(self):
        """Assert that the text column does not allow NULL values.

        For history about why this is important, see
        https://github.com/fedora-infra/bodhi/issues/949.
        """
        assert model.Comment.__table__.columns['text'].nullable == False


class TestDeclEnum:
    """Test the DeclEnum class."""

    def test_from_string_bad_value(self):
        """Test the from_string() method with a value that doesn't exist."""
        with pytest.raises(ValueError) as exc:
            model.UpdateStatus.from_string('wrong')
        assert str(exc.value) == "Invalid value for 'UpdateStatus': 'wrong'"


class TestDeclEnumType(BasePyTestCase):
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

        assert t.process_bind_param(None, self.engine.dialect) is None

    def test_process_bind_param_truthy_value(self):
        """Test the process_bind_param() method with a truthy value."""
        t = model.DeclEnumType(model.UpdateStatus)

        assert t.process_bind_param(model.UpdateStatus.stable, self.engine.dialect) == 'stable'

    def test_process_result_value_None(self):
        """Test the process_result_value() method with a value of None."""
        t = model.DeclEnumType(model.UpdateStatus)

        assert t.process_result_value(None, self.engine.dialect) is None

    def test_process_result_value_truthy_value(self):
        """Test the process_result_value() method with a truthy value."""
        t = model.DeclEnumType(model.UpdateStatus)

        assert t.process_result_value('testing', self.engine.dialect) == model.UpdateStatus.testing


class TestEnumMeta:
    """Test the Enummeta class."""

    def test___iter__(self):
        """Assert correct return value from the __iter__() method."""
        m = model.EnumMeta('UpdateStatus', (model.DeclEnum,),
                           {'testing': ('testing', 'Testing'), 'stable': ('stable', 'Stable')})
        expected_values = ['testing', 'stable']

        for v in iter(m):
            assert repr(v) == '<{}>'.format(expected_values.pop(0))
            assert type(v) == model.EnumSymbol

        assert expected_values == []


class TestEnumSymbol:
    """Test the EnumSymbol class."""

    def test___iter__(self):
        """Ensure correct operation of the __iter__() method."""
        s = model.EnumSymbol(model.UpdateStatus, 'name', 'value', 'description')
        expected_values = ['value', 'description']

        for v in iter(s):
            assert v == expected_values.pop(0)

        assert expected_values == []

    def test___json__(self):
        """Ensure that the __json__() method returns the value."""
        s = model.EnumSymbol(model.UpdateStatus, 'name', 'value', 'description')

        assert s.__json__() == 'value'

    def test___lt__(self):
        """Ensure that EnumSymbols support sorting."""
        open_source = model.EnumSymbol(model.UpdateStatus, 'open source', 'open_source',
                                       'Open Source')
        closed_source = model.EnumSymbol(model.UpdateStatus, 'closed source',
                                         'closed_source', 'Closed Source')

        assert closed_source < open_source
        assert open_source > closed_source
        assert open_source != closed_source

    def test___reduce__(self):
        """Ensure correct operation of the __reduce__() method by pickling an instance."""
        s = model.EnumSymbol(model.UpdateStatus, 'testing', 'testing', 'testing')

        p = pickle.dumps(s)

        deserialized_s = pickle.loads(p)
        assert deserialized_s.cls_ == model.UpdateStatus
        assert deserialized_s.name == 'testing'
        assert deserialized_s.value == 'testing'
        assert deserialized_s.description == 'testing'

    def test___repr__(self):
        """Ensure correct operation of the __repr__() method."""
        s = model.EnumSymbol(model.UpdateStatus, 'name', 'value', 'description')

        assert repr(s) == '<name>'

    def test___str__(self):
        """Ensure correct operation of the __str__() method."""
        s = model.EnumSymbol(model.UpdateStatus, 'name', 'value', 'description')

        assert str(s) == 'value'
        assert type(str(s)) == str


class TestCompose(BasePyTestCase):
    """Test the :class:`Compose` model."""
    def _generate_compose(self, request, security):
        """
        Create and return a Compose.

        Args:
            request (UpdateRequest): The request you would like the compose for.
            security (bool): Whether you want the compose to be a security Compose.
        Returns:
            Compose: The created compose.
        """
        uid = uuid.uuid4()
        release = model.Release(
            name='F27-{}'.format(uid), long_name='Fedora 27 {}'.format(uid),
            id_prefix='FEDORA', version='27',
            dist_tag='f27', stable_tag='f27-updates',
            testing_tag='f27-updates-testing',
            candidate_tag='f27-updates-candidate',
            pending_signing_tag='f27-updates-testing-signing',
            pending_testing_tag='f27-updates-testing-pending',
            pending_stable_tag='f27-updates-pending',
            override_tag='f27-override',
            state=ReleaseState.current,
            branch='f27-{}'.format(uid))
        self.db.add(release)
        update = self.create_update(['bodhi-{}-1.fc27'.format(uuid.uuid4())])
        update.release = release
        update.request = request
        update.locked = True
        if security:
            update.type = model.UpdateType.security
        compose = model.Compose(request=request, release=update.release)
        self.db.add(compose)
        self.db.flush()
        return compose

    def test_content_type_no_updates(self):
        """The content_type should be None if there are no updates."""
        compose = self._generate_compose(model.UpdateRequest.stable, False)
        compose.updates[0].locked = False
        self.db.flush()
        self.db.refresh(compose)

        assert compose.content_type is None

    def test_content_type_with_updates(self):
        """The content_type should match the first update."""
        compose = self._generate_compose(model.UpdateRequest.stable, False)

        assert compose.content_type == model.ContentType.rpm

    def test_from_dict(self):
        """Assert that from_dict() returns a Compose."""
        compose = self._generate_compose(model.UpdateRequest.stable, False)

        reloaded_compose = model.Compose.from_dict(self.db, compose.__json__())

        assert reloaded_compose.request == compose.request
        assert reloaded_compose.release == compose.release

    def test_from_updates(self):
        """Assert that from_updates() correctly generates Composes."""
        update_1 = self.create_update(['bodhi-{}-1.fc27'.format(uuid.uuid4())])
        # This update should be ignored.
        update_2 = self.create_update(['bodhi-{}-1.fc27'.format(uuid.uuid4())])
        update_2.request = None
        release = model.Release(
            name='F27', long_name='Fedora 27',
            id_prefix='FEDORA', version='27',
            dist_tag='f27', stable_tag='f27-updates',
            testing_tag='f27-updates-testing',
            candidate_tag='f27-updates-candidate',
            pending_signing_tag='f27-updates-testing-signing',
            pending_testing_tag='f27-updates-testing-pending',
            pending_stable_tag='f27-updates-pending',
            override_tag='f27-override',
            state=ReleaseState.current,
            branch='f27')
        self.db.add(release)
        update_3 = self.create_update(['bodhi-{}-1.fc27'.format(uuid.uuid4())])
        update_3.release = release
        update_3.type = model.UpdateType.security
        update_4 = self.create_update(['bodhi-{}-1.fc27'.format(uuid.uuid4())])
        update_4.status = model.UpdateStatus.testing
        update_4.request = model.UpdateRequest.stable

        composes = model.Compose.from_updates([update_1, update_2, update_3, update_4])

        assert isinstance(composes, list)
        for c in composes:
            self.db.add(c)
            self.db.flush()
            self.db.refresh(c)
        composes = sorted(composes)
        assert len(composes) == 3

        def assert_compose_has_update(compose, update):
            assert compose.updates == [update]
            assert compose.release == update.release
            assert compose.request == update.request

        assert_compose_has_update(composes[0], update_3)
        assert_compose_has_update(composes[1], update_4)
        assert_compose_has_update(composes[2], update_1)

    def test_from_updates_no_builds(self):
        """Assert that update without builds is not added to compose."""
        update = self.create_update(['bodhi-{}-1.fc27'.format(uuid.uuid4())])
        update.builds = []

        composes = model.Compose.from_updates([update])

        assert isinstance(composes, list)
        assert len(composes) == 0

    def test_security_false(self):
        """Assert that security is False if none of the Updates are security updates."""
        compose = self._generate_compose(model.UpdateRequest.stable, False)

        assert not compose.security

    def test_security_true(self):
        """Assert that security is True if one of the Updates is a security update."""
        compose = self._generate_compose(model.UpdateRequest.stable, True)

        assert compose.security

    def test_update_state_date(self):
        """Ensure that the state_date attribute gets automatically set when state changes."""
        compose = self._generate_compose(model.UpdateRequest.stable, True)
        before = datetime.utcnow()
        compose.state = model.ComposeState.notifying

        assert compose.state_date > before
        assert datetime.utcnow() > compose.state_date

    def test_update_summary(self):
        """Test the update_summary() property."""
        compose = self._generate_compose(model.UpdateRequest.stable, True)
        update = compose.updates[0]

        assert compose.update_summary == (
            [{'alias': update.alias, 'title': update.get_title(nvr=True, beautify=True)}])

    def test___json___composer_flag(self):
        """The composer flag should reduce the number of serialized fields."""
        compose = self._generate_compose(model.UpdateRequest.stable, True)
        normal_json = compose.__json__()

        j = compose.__json__(composer=True)

        assert set(j.keys()), {'security', 'release_id', 'request' == 'content_type'}
        # If we remove the extra keys from normal_json, the remaining dictionary should be the same
        # as j.
        for k in set(normal_json.keys()) - set(j.keys()):
            del(normal_json[k])
        assert j == normal_json

    def test___lt___false_fallthrough(self):
        """__lt__() should return False if the other conditions tested don't catch anything."""
        compose_1 = self._generate_compose(model.UpdateRequest.stable, True)
        compose_2 = self._generate_compose(model.UpdateRequest.stable, True)

        assert not compose_1 < compose_2
        assert not compose_2 < compose_1
        assert not compose_1 > compose_2
        assert not compose_2 > compose_1

    def test___lt___security_prioritized(self):
        """__lt__() should return True if other is security and self is not."""
        compose_1 = self._generate_compose(model.UpdateRequest.testing, True)
        compose_2 = self._generate_compose(model.UpdateRequest.testing, False)

        assert compose_1 < compose_2
        assert not compose_2 < compose_1
        assert not compose_1 > compose_2
        assert compose_2 > compose_1
        assert sorted([compose_1, compose_2]) == [compose_1, compose_2]

    def test___lt___security_prioritized_over_stable(self):
        """
        __lt__() should return True if other is security and self is not, even if self is
        stable.
        """
        compose_1 = self._generate_compose(model.UpdateRequest.testing, True)
        compose_2 = self._generate_compose(model.UpdateRequest.stable, False)

        assert compose_1 < compose_2
        assert not compose_2 < compose_1
        assert not compose_1 > compose_2
        assert compose_2 > compose_1
        assert sorted([compose_1, compose_2]) == [compose_1, compose_2]

    def test___lt___stable_prioritized(self):
        """__lt__() should return True if self is stable and other is not."""
        compose_1 = self._generate_compose(model.UpdateRequest.testing, False)
        compose_2 = self._generate_compose(model.UpdateRequest.stable, False)

        assert not compose_1 < compose_2
        assert compose_2 < compose_1
        assert compose_1 > compose_2
        assert not compose_2 > compose_1
        assert sorted([compose_1, compose_2]) == [compose_2, compose_1]

    def test___str__(self):
        """Ensure __str__() returns the right string."""
        compose = self._generate_compose(model.UpdateRequest.stable, False)

        assert str(compose) == '<Compose: {} stable>'.format(compose.release.name)


class TestRelease(ModelTest):
    """Unit test case for the ``Release`` model."""
    klass = model.Release
    attrs = dict(
        name="F11",
        long_name="Fedora 11",
        id_prefix="FEDORA",
        version='11',
        branch='f11',
        dist_tag="dist-f11",
        stable_tag="dist-f11-updates",
        testing_tag="dist-f11-updates-testing",
        candidate_tag="dist-f11-updates-candidate",
        pending_signing_tag="dist-f11-updates-testing-signing",
        pending_testing_tag="dist-f11-updates-testing-pending",
        pending_stable_tag="dist-f11-updates-pending",
        override_tag="dist-f11-override",
        state=model.ReleaseState.current,
        composed_by_bodhi=True,
        package_manager=PackageManager.yum,
        testing_repository='updates-testing')

    def test_collection_name(self):
        """Test the collection_name property of the Release."""
        assert self.obj.collection_name == 'Fedora'

    def test_mandatory_days_in_testing_status_falsey(self):
        """Test mandatory_days_in_testing() with a value that is falsey."""
        config["fedora.mandatory_days_in_testing"] = 42
        assert self.obj.mandatory_days_in_testing == 42

    def test_mandatory_days_in_testing_status_truthy(self):
        """Test mandatory_days_in_testing() with a value that is truthy."""
        config.update({
            'f11.current.mandatory_days_in_testing': 42,
            'f11.status': 'current'
        })
        assert self.obj.mandatory_days_in_testing == 42

    def test_mandatory_days_in_testing_status_0_days(self):
        """Test mandatory_days_in_testing() with a value that is 0."""
        config.update({
            'f11.current.mandatory_days_in_testing': 0,
            'f11.status': 'current'
        })
        assert self.obj.mandatory_days_in_testing == 0

    def test_critpath_mandatory_days_in_testing_no_status(self):
        """
        Test critpath_mandatory_days_in_testing() returns global default if
        release has no status.
        """
        config.update({
            'critpath.stable_after_days_without_negative_karma': 11,
            'f11.current.critpath.stable_after_days_without_negative_karma': 42
        })
        assert self.obj.critpath_mandatory_days_in_testing == 11

    def test_critpath_mandatory_days_in_testing_status_default(self):
        """
        Test critpath_mandatory_days_in_testing() returns global default if
        release has status, but no override set.
        """
        config.update({
            'critpath.stable_after_days_without_negative_karma': 11,
            'f11.status': 'current'
        })
        assert self.obj.critpath_mandatory_days_in_testing == 11

    def test_critpath_mandatory_days_in_testing_status_override(self):
        """
        Test critpath_mandatory_days_in_testing() returns override value if
        release has status and override set.
        """
        config.update({
            'critpath.stable_after_days_without_negative_karma': 11,
            'f11.status': 'current',
            'f11.current.critpath.stable_after_days_without_negative_karma': 42
        })
        assert self.obj.critpath_mandatory_days_in_testing == 42

    def test_setting_prefix(self):
        """Assert correct return value from the setting_prefix property."""
        assert self.obj.setting_prefix == 'f11'

        # Try putting a - into the name of the release, which should get removed
        self.obj.name = 'f-11'

        assert self.obj.setting_prefix == 'f11'

    def test_setting_status_found(self):
        """Assert correct return value from the setting_status property when config is found."""
        config.update({
            'f11.status': "It's doing just fine, thanks for asking"
        })
        assert self.obj.setting_status == "It's doing just fine, thanks for asking"

    def test_setting_status_not_found(self):
        """Assert correct return value from the setting_status property when config not found."""
        assert self.obj.setting_status is None

    def test_version_int(self):
        assert self.obj.version_int == 11

    def test_all_releases(self):
        releases = model.Release.all_releases()

        state = ReleaseState.from_string(list(releases.keys())[0])
        assert 'long_name' in releases[state.value][0], releases
        # Make sure it's the same cached object
        assert releases is model.Release.all_releases()

    def test_clear_all_releases_cache(self):
        model.Release.all_releases()
        assert model.Release._all_releases is not None
        model.Release.clear_all_releases_cache()
        assert model.Release._all_releases is None

    def test_get_pending_signing_side_tag_found(self):
        """
        Assert that correct side tag is returned.
        """
        config.update({
            'f11.koji-signing-pending-side-tag': '-signing-pending-test'
        })
        assert self.obj.get_pending_signing_side_tag("side-tag") == "side-tag-signing-pending-test"

    def test_get_pending_signing_side_tag_not_found(self):
        """
        Assert that default side tag is returned.
        """
        assert self.obj.get_pending_signing_side_tag("side-tag") == "side-tag-signing-pending"

    def test_get_pending_testing_side_tag_found(self):
        """
        Assert that correct side tag is returned.
        """
        config.update({
            'f11.koji-testing-side-tag': '-testing-test'
        })
        assert self.obj.get_pending_testing_side_tag("side-tag") == "side-tag-testing-test"

    def test_get_pending_testing_side_tag_not_found(self):
        """
        Assert that default side tag is returned.
        """
        assert self.obj.get_pending_testing_side_tag("side-tag") == "side-tag-testing-pending"


class TestReleaseCritpathMinKarma(BasePyTestCase):
    """Tests for the Release.critpath_min_karma property."""

    @mock.patch.dict(
        config, {'critpath.min_karma': 2, 'f17.beta.critpath.min_karma': 42, 'f17.status': "beta"})
    def test_setting_status_min(self):
        """If a min is defined for the release, it should be returned."""
        release = model.Release.query.first()

        assert release.critpath_min_karma == 42

    @mock.patch.dict(
        config, {'critpath.min_karma': 25, 'f17.status': "beta"})
    def test_setting_status_no_min(self):
        """If no min is defined for the release, the general min karma config should be returned."""
        release = model.Release.query.first()

        assert release.critpath_min_karma == 25

    @mock.patch.dict(
        config, {'critpath.min_karma': 72})
    def test_setting_status_no_setting_status(self):
        """If no status is defined for the release, the general min karma should be returned."""
        release = model.Release.query.first()

        assert release.critpath_min_karma == 72


class TestReleaseModular(ModelTest):
    """Unit test case for the ``Release`` model for modular releases."""
    klass = model.Release
    attrs = dict(
        name="F11M",
        long_name="Fedora 11 Modular",
        id_prefix="FEDORA-MODULAR",
        version='11',
        branch='f11m',
        dist_tag="dist-f11",
        stable_tag="dist-f11-updates",
        testing_tag="dist-f11-updates-testing",
        candidate_tag="dist-f11-updates-candidate",
        pending_signing_tag="dist-f11-updates-testing-signing",
        pending_testing_tag="dist-f11-updates-testing-pending",
        pending_stable_tag="dist-f11-updates-pending",
        override_tag="dist-f11-override",
        state=model.ReleaseState.current,
        composed_by_bodhi=True,
        package_manager=PackageManager.dnf,
        testing_repository='updates-testing')

    def test_version_int(self):
        assert self.obj.version_int == 11

    def test_all_releases(self):
        releases = model.Release.all_releases()

        state = ReleaseState.from_string(list(releases.keys())[0])
        assert 'long_name' in releases[state.value][0], releases
        # Make sure it's the same cached object
        assert releases is model.Release.all_releases()

    def test_clear_all_releases_cache(self):
        model.Release.all_releases()
        assert model.Release._all_releases is not None
        model.Release.clear_all_releases_cache()
        assert model.Release._all_releases is None


class TestReleaseContainer(ModelTest):
    """Unit test case for the ``Release`` model for container releases."""
    klass = model.Release
    attrs = dict(
        name="F11C",
        long_name="Fedora 11 Container",
        id_prefix="FEDORA-CONTAINER",
        version='11',
        branch='f11c',
        dist_tag="dist-f11",
        stable_tag="dist-f11-updates",
        testing_tag="dist-f11-updates-testing",
        candidate_tag="dist-f11-updates-candidate",
        pending_signing_tag="dist-f11-updates-testing-signing",
        pending_testing_tag="dist-f11-updates-testing-pending",
        pending_stable_tag="dist-f11-updates-pending",
        override_tag="dist-f11-override",
        state=model.ReleaseState.current,
        composed_by_bodhi=True,
        package_manager=PackageManager.unspecified,
        testing_repository=None)

    def test_version_int(self):
        assert self.obj.version_int == 11

    def test_all_releases(self):
        releases = model.Release.all_releases()

        state = ReleaseState.from_string(list(releases.keys())[0])
        assert 'long_name' in releases[state.value][0], releases
        # Make sure it's the same cached object
        assert releases is model.Release.all_releases()

    def test_clear_all_releases_cache(self):
        model.Release.all_releases()
        assert model.Release._all_releases is not None
        model.Release.clear_all_releases_cache()
        assert model.Release._all_releases is None


class TestReleaseFlatpak(ModelTest):
    """Unit test case for the ``Release`` model for flatpak releases."""
    klass = model.Release
    attrs = dict(
        name="F29F",
        long_name="Fedora 29 Flatpaks",
        id_prefix="FEDORA-FLATPAK",
        version='29',
        branch='f29',
        dist_tag="f29-flatpak",
        stable_tag="f29-flatpak-updates",
        testing_tag="f29-flatpak-updates-testing",
        candidate_tag="f29-flatpak-updates-candidate",
        pending_signing_tag="",
        pending_testing_tag="f29-flatpak-updates-testing-pending",
        pending_stable_tag="f29-flatpak-updates-pending",
        override_tag="f29-flatpak-override",
        state=model.ReleaseState.current,
        composed_by_bodhi=True,
        package_manager=PackageManager.unspecified,
        testing_repository=None)

    def test_version_int(self):
        assert self.obj.version_int == 29

    def test_all_releases(self):
        releases = model.Release.all_releases()

        state = ReleaseState.from_string(list(releases.keys())[0])
        assert 'long_name' in releases[state.value][0], releases
        # Make sure it's the same cached object
        assert releases is model.Release.all_releases()

    def test_clear_all_releases_cache(self):
        model.Release.all_releases()
        assert model.Release._all_releases is not None
        model.Release.clear_all_releases_cache()
        assert model.Release._all_releases is None


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


class TestPackageModel(BasePyTestCase):
    """Tests for the Package model."""

    def test_two_package_different_types(self):
        """Assert two different package types with the same name is fine."""
        package1 = model.Package(name='python-requests')
        package2 = model.RpmPackage(name='python-requests')

        self.db.add(package1)
        self.db.add(package2)
        self.db.flush()

    def test_two_package_same_type(self):
        """Assert two packages of the same type with the same name is *not* fine."""
        package1 = model.RpmPackage(name='python-requests')
        package2 = model.RpmPackage(name='python-requests')

        self.db.add(package1)
        self.db.add(package2)
        pytest.raises(IntegrityError, self.db.flush)

    @pytest.mark.parametrize('exists', (False, True))
    def test_package_existence(self, exists):
        """Assert package existence check works based on specific type."""
        if exists:
            package1 = model.RpmPackage(name='python-requests')
        else:
            package1 = model.ModulePackage(name='python-requests')
        self.db.add(package1)
        self.db.flush()

        koji = buildsys.get_session()
        kbuildinfo = koji.getBuild('python-requests-1.0-1.fc36')
        rbuildinfo = {
            'info': kbuildinfo,
            'nvr': kbuildinfo['nvr'].rsplit('-', 2),
        }
        assert model.Package.check_existence(rbuildinfo) is exists


class TestModulePackage(ModelTest):
    """Unit test case for the ``ModulePackage`` model."""
    klass = model.ModulePackage
    attrs = dict(name="TurboGears")

    def setup_method(self):
        super(TestModulePackage, self).setup_method()
        self.package = model.ModulePackage(name='the-greatest-package:master')
        self.db.add(self.package)

    def test_adding_rpmbuild(self):
        """Assert that validation fails when adding a RpmBuild."""
        build1 = model.ModuleBuild(nvr='the-greatest-package-1.0.0-fc17.1')
        build2 = model.RpmBuild(nvr='the-greatest-package-1.1.0-fc17.1')
        self.package.builds.append(build1)

        with pytest.raises(ValueError) as exc_context:
            self.package.builds.append(build2)
        assert str(exc_context.value) == (
            ("A RPM Build cannot be associated with a Module Package. A Package's "
             "builds must be the same type as the package."))

    def test_adding_list_of_module_and_rpmbuild(self):
        """Assert that validation fails when adding a ModuleBuild and RpmBuild via a list."""
        build1 = model.ModuleBuild(nvr='the-greatest-package-1.0.0-fc17.1')
        build2 = model.RpmBuild(nvr='the-greatest-package-1.1.0-fc17.1')

        with pytest.raises(ValueError) as exc_context:
            self.package.builds = [build1, build2]
        assert str(exc_context.value) == (
            ("A RPM Build cannot be associated with a Module Package. A Package's "
             "builds must be the same type as the package."))

    def test_backref_no_builds(self):
        """Assert that a ModuleBuild can be appended via a backref."""
        build = model.ModuleBuild(nvr='the-greatest-package-1.0.0-fc17.1')
        build.package = self.package

        # This should not raise any Exception.
        self.db.flush()

    def test_backref_rpmbuild(self):
        """Assert that adding an RpmBuild via backref fails validation."""
        build1 = model.ModuleBuild(nvr='the-greatest-package-1.0.0-fc17.1')
        build2 = model.RpmBuild(nvr='the-greatest-package-1.1.0-fc17.1')
        build1.package = self.package

        with pytest.raises(ValueError) as exc_context:
            build2.package = self.package
        assert str(exc_context.value) == (
            ("A RPM Build cannot be associated with a Module Package. A Package's "
             "builds must be the same type as the package."))

    def test_backref_second_modulebuild(self):
        """Assert that two ModuleBuilds can be appended via backrefs."""
        build1 = model.ModuleBuild(nvr='the-greatest-package-1.0.0-fc17.1')
        build2 = model.ModuleBuild(nvr='the-greatest-package-1.1.0-fc17.1')
        build1.package = self.package
        build2.package = self.package

        # This should not raise any Exception.
        self.db.flush()

    def test_no_builds(self):
        """Assert that one ModuleBuild can be appended."""
        build = model.ModuleBuild(nvr='the-greatest-package-1.0.0-fc17.1')
        self.package.builds.append(build)

        # This should not raise any Exception.
        self.db.flush()

    def test_same_build_types(self):
        """Assert that two builds of the module type can be added and that validation passes."""
        build1 = model.ModuleBuild(nvr='the-greatest-package-1.0.0-fc17.1')
        build2 = model.ModuleBuild(nvr='the-greatest-package-1.1.0-fc17.1')
        self.package.builds += [build1, build2]

        # This should not raise any Exception.
        self.db.flush()

    @mock.patch('bodhi.server.util.http_session')
    def test_get_pkg_committers_from_pagure_with_group(self, session):
        """
        Ensure that the package committers can be found using the Pagure
        API with a package that does have group ACLs.
        """
        json_output = {
            "access_groups": {
                "admin": [],
                "commit": ["rpm-software-management-sig"],
                "ticket": []},
            "access_users": {
                "admin": ["ignatenkobrain"],
                "commit": ["jmracek"],
                "owner": ["dmach"],
                "ticket": []},
            "close_status": [],
            "custom_keys": [],
            "date_created": "1501867095",
            "date_modified": "1507272820",
            "description": "The dnf rpms",
            "fullname": "modules/dnf",
            "group_details": {
                "rpm-software-management-sig": [
                    "releng",
                    "ignatenkobrain",
                    "jsilhan",
                    "mluscon",
                    "jmracek",
                    "mhatina",
                    "dmach"]},
            "id": 2599,
            "milestones": {},
            "name": "dnf",
            "namespace": "modules",
            "parent": None,
            "priorities": {},
            "tags": [],
            "user": {
                "fullname": "Daniel Mach",
                "name": "dmach"}}
        session.get.return_value.json.return_value = json_output
        session.get.return_value.status_code = 200

        rv = self.package.get_pkg_committers_from_pagure()

        committers, groups = rv

        assert sorted(committers) == (
            ['dmach', 'ignatenkobrain', 'jmracek', 'jsilhan',
             'mhatina', 'mluscon', 'releng'])
        assert groups == ['rpm-software-management-sig']
        session.get.assert_called_once_with(
            'https://src.fedoraproject.org/pagure/api/0/modules/the-greatest-package?'
            'expand_group=1',
            timeout=60)

    @pytest.mark.parametrize('access', (False, True))
    @mock.patch('bodhi.server.util.http_session')
    def test_hascommitaccess_module(self, session, access):
        """
        Test call to Pagure to check if a user has access to this package/branch.
        """
        json_output = {
            "args": {
                "username": "mattia",
                "branch": "master",
                "project": {}
            },
            "hascommit": access
        }
        session.get.return_value.json.return_value = json_output
        session.get.return_value.status_code = 200

        rv = self.package.hascommitaccess('mattia', 'f33')

        assert rv is access
        session.get.assert_called_once_with(
            'https://src.fedoraproject.org/pagure/api/0/modules/the-greatest-package/'
            'hascommit?user=mattia&branch=master',
            timeout=60)


class TestContainerPackage(ModelTest):
    """Test the Container class."""

    klass = model.ContainerPackage
    attrs = dict(name="docker-distribution")

    @mock.patch('bodhi.server.util.http_session')
    def test_get_pkg_committers_from_pagure(self, http_session):
        """Ensure correct return value from get_pkg_committers_from_pagure()."""
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
            "group_details": {},
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
        http_session.get.return_value.json.return_value = json_output
        http_session.get.return_value.status_code = 200

        rv = self.obj.get_pkg_committers_from_pagure()

        assert rv == (['mprahl'], ['factory2'])
        http_session.get.assert_called_once_with(
            ('https://src.fedoraproject.org/pagure/api/0/container/docker-distribution'
             '?expand_group=1'),
            timeout=60)

    @pytest.mark.parametrize('access', (False, True))
    @mock.patch('bodhi.server.util.http_session')
    def test_hascommitaccess_container(self, session, access):
        """
        Test call to Pagure to check if a user has access to this package/branch.
        """
        json_output = {
            "args": {
                "username": "mattia",
                "branch": "f33",
                "project": {}
            },
            "hascommit": access
        }
        session.get.return_value.json.return_value = json_output
        session.get.return_value.status_code = 200

        rv = self.obj.hascommitaccess('mattia', 'f33')

        assert rv is access
        session.get.assert_called_once_with(
            'https://src.fedoraproject.org/pagure/api/0/container/docker-distribution/'
            'hascommit?user=mattia&branch=f33',
            timeout=60)


class TestFlatpakPackage(ModelTest):
    klass = model.FlatpakPackage
    attrs = dict(name="flatpak-runtime")

    def patch_http_session(self, http_session, namespace):
        """Patch in the correct pagure API result for the particular flatpaks namespace."""
        json_output = {
            "access_groups": {
                "admin": [],
                "commit": [],
                "ticket": []
            },
            "access_users": {
                "admin": [],
                "commit": [],
                "owner": [
                    "otaylor"
                ],
                "ticket": []
            },
            "close_status": [],
            "custom_keys": [],
            "date_created": "1494947106",
            "description": "Flatpak Runtime",
            "fullname": namespace + "/flatpak-runtime",
            "group_details": {},
            "id": 2,
            "milestones": {},
            "name": "python",
            "namespace": "rpms",
            "parent": None,
            "priorities": {},
            "tags": [],
            "user": {
                "fullname": "Owen Taylor",
                "name": "otaylor"
            }
        }
        http_session.get.return_value.json.return_value = json_output
        http_session.get.return_value.status_code = 200

    @mock.patch('bodhi.server.util.http_session')
    def test_get_pkg_committers_from_pagure_modules(self, http_session):
        """Ensure correct return value from get_pkg_committers_from_pagure()."""
        self.patch_http_session(http_session, namespace='flatpaks')

        rv = self.obj.get_pkg_committers_from_pagure()

        assert rv == (['otaylor'], [])
        http_session.get.assert_called_once_with(
            ('https://src.fedoraproject.org/pagure/api/0/flatpaks/flatpak-runtime'
             '?expand_group=1'),
            timeout=60)

    @pytest.mark.parametrize('access', (False, True))
    @mock.patch('bodhi.server.util.http_session')
    def test_hascommitaccess_flatpak(self, http_session, access):
        """
        Test call to Pagure to check if a user has access to this package/branch.
        """
        json_output = {
            "args": {
                "username": "mattia",
                "branch": "stable",
                "project": {}
            },
            "hascommit": access
        }
        http_session.get.return_value.json.return_value = json_output
        http_session.get.return_value.status_code = 200

        rv = self.obj.hascommitaccess('mattia', 'f33')

        assert rv is access
        http_session.get.assert_called_once_with(
            'https://src.fedoraproject.org/pagure/api/0/flatpaks/flatpak-runtime/'
            'hascommit?user=mattia&branch=stable',
            timeout=60)


class TestRpmPackage(ModelTest):
    """Unit test case for the ``RpmPackage`` model."""
    klass = model.RpmPackage
    attrs = dict(name="TurboGears")

    def setup_method(self):
        super(TestRpmPackage, self).setup_method()
        self.package = model.RpmPackage(name='the-greatest-package')
        self.db.add(self.package)

    def test_adding_modulebuild(self):
        """Assert that validation fails when adding a ModuleBuild."""
        build1 = model.RpmBuild(nvr='the-greatest-package-1.0.0-fc17.1')
        build2 = model.ModuleBuild(nvr='the-greatest-package-1.1.0-fc17.1')
        self.package.builds.append(build1)

        with pytest.raises(ValueError) as exc_context:
            self.package.builds.append(build2)
        assert str(exc_context.value) == (
            ("A Module Build cannot be associated with a RPM Package. A Package's "
             "builds must be the same type as the package."))

    def test_backref_no_builds(self):
        """Assert that a RpmBuild can be appended via a backref."""
        build = model.RpmBuild(nvr='the-greatest-package-1.0.0-fc17.1')
        build.package = self.package

        # This should not raise any Exception.
        self.db.flush()

    def test_backref_modulebuild(self):
        """Assert that adding a ModuleBuild via backref fails validation."""
        build1 = model.RpmBuild(nvr='the-greatest-package-1.0.0-fc17.1')
        build2 = model.ModuleBuild(nvr='the-greatest-package-1.1.0-fc17.1')
        build1.package = self.package

        with pytest.raises(ValueError) as exc_context:
            build2.package = self.package
        assert str(exc_context.value) == (
            ("A Module Build cannot be associated with a RPM Package. A Package's "
             "builds must be the same type as the package."))

    def test_backref_second_modulebuild(self):
        """Assert that two RpmBuilds can be appended via backrefs."""
        build1 = model.RpmBuild(nvr='the-greatest-package-1.0.0-fc17.1')
        build2 = model.RpmBuild(nvr='the-greatest-package-1.1.0-fc17.1')
        build1.package = self.package
        build2.package = self.package

        # This should not raise any Exception.
        self.db.flush()

    def test_no_builds(self):
        """Assert that one RpmBuild can be appended."""
        build = model.RpmBuild(nvr='the-greatest-package-1.0.0-fc17.1')
        self.package.builds.append(build)

        # This should not raise any Exception.
        self.db.flush()

    def test_same_build_types(self):
        """Assert that two builds of the RPM type can be added and that validation passes."""
        build1 = model.RpmBuild(nvr='the-greatest-package-1.0.0-fc17.1')
        build2 = model.RpmBuild(nvr='the-greatest-package-1.1.0-fc17.1')
        self.package.builds += [build1, build2]

        # This should not raise any Exception.
        self.db.flush()

    @mock.patch('bodhi.server.util.http_session')
    def test_get_pkg_committers_from_pagure_with_group(self, session):
        """
        Ensure that the package committers can be found using the Pagure
        API with a package that does have group ACLs.
        """
        json_output = {
            "access_groups": {
                "admin": [],
                "commit": ["rpm-software-management-sig"],
                "ticket": []},
            "access_users": {
                "admin": ["ignatenkobrain"],
                "commit": ["jmracek"],
                "owner": ["dmach"],
                "ticket": []},
            "close_status": [],
            "custom_keys": [],
            "date_created": "1501867095",
            "date_modified": "1507272820",
            "description": "The dnf rpms",
            "fullname": "rpms/dnf",
            "group_details": {
                "rpm-software-management-sig": [
                    "releng",
                    "ignatenkobrain",
                    "jsilhan",
                    "mluscon",
                    "jmracek",
                    "mhatina",
                    "dmach"]},
            "id": 2599,
            "milestones": {},
            "name": "dnf",
            "namespace": "rpms",
            "parent": None,
            "priorities": {},
            "tags": [],
            "user": {
                "fullname": "Daniel Mach",
                "name": "dmach"}}
        session.get.return_value.json.return_value = json_output
        session.get.return_value.status_code = 200

        rv = self.package.get_pkg_committers_from_pagure()

        committers, groups = rv

        assert sorted(committers) == (
            ['dmach', 'ignatenkobrain', 'jmracek', 'jsilhan',
             'mhatina', 'mluscon', 'releng'])
        assert groups == ['rpm-software-management-sig']
        session.get.assert_called_once_with(
            'https://src.fedoraproject.org/pagure/api/0/rpms/the-greatest-package?expand_group=1',
            timeout=60)

    @mock.patch('bodhi.server.util.http_session')
    def test_get_pkg_committers_from_pagure_without_group(self, session):
        """
        Ensure that the package committers can be found using the Pagure
        API with a package that doesn't have group ACLs.
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
            "group_details": {},
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
        session.get.return_value.json.return_value = json_output
        session.get.return_value.status_code = 200

        rv = self.package.get_pkg_committers_from_pagure()

        assert rv == (['mprahl'], ['factory2'])

    @mock.patch('bodhi.server.util.http_session')
    def test_get_pkg_committers_from_pagure_without_group_expansion(self, session):
        """
        Ensure that the package committers can be found using the Pagure
        API with a Pagure version that doesn't support the expand_group GET parameter.
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
        session.get.return_value.json.return_value = json_output
        session.get.return_value.status_code = 200

        rv = self.package.get_pkg_committers_from_pagure()

        assert rv == (['mprahl'], ['factory2'])

    @pytest.mark.parametrize('access', (False, True))
    @mock.patch('bodhi.server.util.http_session')
    def test_hascommitaccess_container_rpm(self, session, access):
        """
        Test call to Pagure to check if a user has access to this package/branch.
        """
        json_output = {
            "args": {
                "username": "mattia",
                "branch": "f33",
                "project": {}
            },
            "hascommit": access
        }
        session.get.return_value.json.return_value = json_output
        session.get.return_value.status_code = 200

        rv = self.package.hascommitaccess('mattia', 'f33')

        assert rv is access
        session.get.assert_called_once_with(
            'https://src.fedoraproject.org/pagure/api/0/rpms/the-greatest-package/'
            'hascommit?user=mattia&branch=f33',
            timeout=60)


class TestBuild(ModelTest):
    """Test class for the ``Build`` model."""
    klass = model.Build
    attrs = dict(nvr="TurboGears-1.0.8-3.fc11")

    def do_get_dependencies(self):
        """
        A Build needs a package to be associated with.

        Returns:
            dict: A dictionary specifying a package to associate with this Build.
        """
        return {'package': model.Package(name='TurboGears')}

    @mock.patch.dict(config, {'query_wiki_test_cases': True})
    def test_wiki_test_cases(self):
        """Test querying the wiki for test cases"""
        # Mock out mediawiki so we don't do network calls in our tests
        response = {
            'query': {
                'categorymembers': [{
                    'title': 'Fake test case',
                }],
            }
        }

        # Now, our actual test.
        with mock.patch('bodhi.server.models.MediaWiki', MockWiki(response)):
            pkg = model.RpmPackage(name='gnome-shell')
            self.db.add(pkg)
            build = model.RpmBuild(nvr='gnome-shell-1.1.1-1.fc32', package=pkg)
            self.db.add(build)
            build.update_test_cases(self.db)
            assert build.testcases[0].name == 'Fake test case'
            assert len(build.testcases) == 1

    @mock.patch.dict(config, {'query_wiki_test_cases': True})
    @mock.patch('bodhi.server.models.MediaWiki')
    def test_wiki_test_cases_recursive(self, MediaWiki):
        """Test querying the wiki for test cases when recursion is necessary."""
        responses = [
            {'query': {
                'categorymembers': [
                    {'title': 'Fake'},
                    {'title': 'Category:Bodhi'},
                    {'title': 'Uploading cat pictures'}]}},
            {'query': {
                'categorymembers': [
                    {'title': 'Does Bodhi eat +1s'}]}}]
        MediaWiki.return_value.call.side_effect = responses
        pkg = model.RpmPackage(name='gnome-shell')
        self.db.add(pkg)
        build = model.RpmBuild(nvr='gnome-shell-1.1.1-1.fc32', package=pkg)
        self.db.add(build)

        build.update_test_cases(self.db)

        assert model.TestCase.query.count() == 3
        assert len(build.testcases) == 3
        assert {tc.name for tc in model.TestCase.query.all()} == (
            {'Does Bodhi eat +1s', 'Fake', 'Uploading cat pictures'})

    @mock.patch.dict(config, {'query_wiki_test_cases': True})
    @mock.patch('bodhi.server.models.MediaWiki')
    def test_wiki_test_cases_removed(self, MediaWiki):
        """Test querying the wiki for test cases and remove test which aren't actual."""
        responses = [
            {'query': {
                'categorymembers': [
                    {'title': 'Fake test case'},
                    {'title': 'Does Bodhi eat +1s'}]}}]

        pkg = model.RpmPackage(name='gnome-shell')
        self.db.add(pkg)
        build = model.RpmBuild(nvr='gnome-shell-1.1.1-1.fc32', package=pkg)
        self.db.add(build)

        # Add both tests to build
        MediaWiki.return_value.call.side_effect = responses
        build.update_test_cases(self.db)
        assert model.TestCase.query.count() == 2
        assert len(build.testcases) == 2
        assert {tc.name for tc in build.testcases} == (
            {'Does Bodhi eat +1s', 'Fake test case'})

        # Now remove one test
        responses = [
            {'query': {
                'categorymembers': [
                    {'title': 'Fake test case'}]}}]
        MediaWiki.return_value.call.side_effect = responses
        build.update_test_cases(self.db)
        assert model.TestCase.query.count() == 2
        assert len(build.testcases) == 1
        assert build.testcases[0].name == 'Fake test case'

    @mock.patch.dict(config, {'query_wiki_test_cases': True})
    @mock.patch('bodhi.server.models.MediaWiki')
    def test_wiki_test_cases_exception(self, MediaWiki):
        """Test querying the wiki for test cases when connection to Wiki failed"""
        MediaWiki.return_value.call.side_effect = URLError("oh no!")

        with pytest.raises(ExternalCallException) as exc_context:
            pkg = model.RpmPackage(name='gnome-shell')
            self.db.add(pkg)
            build = model.RpmBuild(nvr='gnome-shell-1.1.1-1.fc32', package=pkg)
            self.db.add(build)
            build.update_test_cases(self.db)
        assert len(build.testcases) == 0
        assert str(exc_context.value) == 'Failed retrieving testcases from Wiki'


class TestRpmBuild(ModelTest):
    """Unit test case for the ``RpmBuild`` model."""
    klass = model.RpmBuild
    attrs = dict(nvr="TurboGears-1.0.8-3.fc11")

    def do_get_dependencies(self):
        return dict(release=model.Release(**TestRelease.attrs),
                    package=model.RpmPackage(**TestRpmPackage.attrs))

    @mock.patch('bodhi.server.models.log.exception')
    def test_get_changelog_bad_data(self, exception):
        """Ensure the get_changelog() logs an error when it is unable to form the log."""
        # The changelogname field doesn't have enough entries, which will cause an Exception.
        rpm_header = {
            'changelogtext': ['- Added a free money feature.', '- Make users ☺'],
            'release': '1.fc20',
            'version': '2.1.0',
            'changelogtime': [1375531200, 1370952000],
            'description': 'blah blah blah',
            'changelogname': ['Fedora Releng <rel-eng@lists.fedoraproject.org> - 2.1.0-1'],
            'url': 'http://libseccomp.sourceforge.net',
            'name': 'libseccomp',
            'summary': 'Enhanced seccomp library'}

        with mock.patch(
                'bodhi.server.models.get_rpm_header', return_value=rpm_header) as get_rpm_header:
            changelog = self.obj.get_changelog()

        # The free money note should still have made it.
        assert changelog == (
            ('* Sat Aug  3 2013 Fedora Releng <rel-eng@lists.fedoraproject.org> - 2.1.0-1\n- Added '
             'a free money feature.\n'))
        # The changelogname field should have caused an Exception to be raised.
        exception.assert_called_once_with(
            'Unable to add changelog entry for header %s', rpm_header)
        get_rpm_header.assert_called_once_with(self.obj.nvr)

    def test_get_changelog_no_description(self):
        """Ensure the get_changelog() returns empty string when there is no description."""
        rpm_header = {
            'changelogtext': [],
            'release': '1.fc20',
            'version': '2.1.0',
            'changelogtime': [1375531200, 1370952000],
            'description': 'blah blah blah',
            'changelogname': ['Fedora Releng <rel-eng@lists.fedoraproject.org> - 2.1.0-1'],
            'url': 'http://libseccomp.sourceforge.net',
            'name': 'libseccomp',
            'summary': 'Enhanced seccomp library'}

        with mock.patch(
                'bodhi.server.models.get_rpm_header', return_value=rpm_header) as get_rpm_header:
            changelog = self.obj.get_changelog()

        assert changelog == ''
        get_rpm_header.assert_called_once_with(self.obj.nvr)

    @mock.patch('bodhi.server.models.log.exception')
    def test_get_changelog_when_is_list(self, exception):
        """Test get_changelog() when the changelogtime is given as a list."""
        rpm_header = {
            'changelogtext': ['- Added a free money feature.', '- Make users ☺'],
            'release': '1.fc20',
            'version': '2.1.0',
            'changelogtime': [1375531200, 1370952000],
            'description': 'blah blah blah',
            'changelogname': ['Fedora Releng <rel-eng@lists.fedoraproject.org> - 2.1.0-1',
                              'Randy <bowlofeggs@fpo> - 2.0.1-2'],
            'url': 'http://libseccomp.sourceforge.net',
            'name': 'libseccomp',
            'summary': 'Enhanced seccomp library'}

        with mock.patch(
                'bodhi.server.models.get_rpm_header', return_value=rpm_header) as get_rpm_header:
            changelog = self.obj.get_changelog()

        # The full changelog should be rendered.
        assert changelog == (
            ('* Sat Aug  3 2013 Fedora Releng <rel-eng@lists.fedoraproject.org> - 2.1.0-1\n- Added '
             'a free money feature.\n* Tue Jun 11 2013 Randy <bowlofeggs@fpo> - 2.0.1-2\n- Make '
             'users ☺\n'))
        # No exception should have been logged.
        assert exception.call_count == 0
        get_rpm_header.assert_called_once_with(self.obj.nvr)

    @mock.patch('bodhi.server.models.log.exception')
    def test_get_changelog_when_not_list(self, exception):
        """Test get_changelog() when the changelogtime is not given as a list."""
        rpm_header = {
            'changelogtext': ['- Added a free money feature.'],
            'release': '1.fc20',
            'version': '2.1.0',
            'changelogtime': 1375531200,
            'description': 'blah blah blah',
            'changelogname': ['Fedora Releng <rel-eng@lists.fedoraproject.org> - 2.1.0-1'],
            'url': 'http://libseccomp.sourceforge.net',
            'name': 'libseccomp',
            'summary': 'Enhanced seccomp library'}

        with mock.patch(
                'bodhi.server.models.get_rpm_header', return_value=rpm_header) as get_rpm_header:
            changelog = self.obj.get_changelog()

        # The full changelog should be rendered.
        assert changelog == (
            ('* Sat Aug  3 2013 Fedora Releng <rel-eng@lists.fedoraproject.org> - 2.1.0-1\n- Added '
             'a free money feature.\n'))
        # No exception should have been logged.
        assert exception.call_count == 0
        get_rpm_header.assert_called_once_with(self.obj.nvr)

    @mock.patch('bodhi.server.models.log.exception')
    def test_get_changelog_with_timelimit(self, exception):
        """Test get_changelog() with time limit."""
        rpm_header = {
            'changelogtext': ['- Added a free money feature.', '- Make users ☺'],
            'release': '1.fc20',
            'version': '2.1.0',
            'changelogtime': [1375531200, 1370952000],
            'description': 'blah blah blah',
            'changelogname': ['Fedora Releng <rel-eng@lists.fedoraproject.org> - 2.1.0-1',
                              'Randy <bowlofeggs@fpo> - 2.0.1-2'],
            'url': 'http://libseccomp.sourceforge.net',
            'name': 'libseccomp',
            'summary': 'Enhanced seccomp library'}

        with mock.patch(
                'bodhi.server.models.get_rpm_header', return_value=rpm_header) as get_rpm_header:
            changelog = self.obj.get_changelog(timelimit=1371000000)

        # Only one entry should be rendered.
        assert changelog == (
            ('* Sat Aug  3 2013 Fedora Releng <rel-eng@lists.fedoraproject.org> - 2.1.0-1\n- Added '
             'a free money feature.\n'))
        # No exception should have been logged.
        assert exception.call_count == 0
        get_rpm_header.assert_called_once_with(self.obj.nvr)

    @mock.patch('bodhi.server.models.log.exception')
    @mock.patch('bodhi.server.models.RpmBuild.get_latest', return_value='libseccomp-2.0.1-2.fc20')
    def test_get_changelog_with_lastupdate(self, get_latest, exception):
        """Test get_changelog() with lastupdate set to True."""
        rpm_headers = [{
            'changelogtext': ['- Added a free money feature.', '- Make users ☺'],
            'release': '1.fc20',
            'version': '2.1.0',
            'changelogtime': [1375531200, 1370952000],
            'description': 'blah blah blah',
            'changelogname': ['Fedora Releng <rel-eng@lists.fedoraproject.org> - 2.1.0-1',
                              'Randy <bowlofeggs@fpo> - 2.0.1-2'],
            'url': 'http://libseccomp.sourceforge.net',
            'name': 'libseccomp',
            'summary': 'Enhanced seccomp library'},
            {
            'changelogtext': ['- Make users ☺'],
            'release': '2.fc20',
            'version': '2.0.1',
            'changelogtime': [1370952000],
            'description': 'blah blah blah',
            'changelogname': ['Randy <bowlofeggs@fpo> - 2.0.1-2'],
            'url': 'http://libseccomp.sourceforge.net',
            'name': 'libseccomp',
            'summary': 'Enhanced seccomp library'}]

        with mock.patch('bodhi.server.models.get_rpm_header') as get_rpm_header:
            get_rpm_header.side_effect = rpm_headers
            changelog = self.obj.get_changelog(lastupdate=True)

        # Only the newer entry should be rendered.
        assert changelog == (
            ('* Sat Aug  3 2013 Fedora Releng <rel-eng@lists.fedoraproject.org> - 2.1.0-1\n- Added '
             'a free money feature.\n'))
        # No exception should have been logged.
        assert exception.call_count == 0

    @mock.patch('bodhi.server.models.log.exception')
    @mock.patch('bodhi.server.models.RpmBuild.get_latest', return_value=None)
    def test_get_changelog_newpackage(self, get_latest, exception):
        """Test get_changelog() with a new package."""
        rpm_header = {
            'changelogtext': ['- Added a free money feature.', '- Make users ☺'],
            'release': '1.fc20',
            'version': '2.1.0',
            'changelogtime': [1375531200, 1370952000],
            'description': 'blah blah blah',
            'changelogname': ['Fedora Releng <rel-eng@lists.fedoraproject.org> - 2.1.0-1',
                              'Randy <bowlofeggs@fpo> - 2.0.1-2'],
            'url': 'http://libseccomp.sourceforge.net',
            'name': 'libseccomp',
            'summary': 'Enhanced seccomp library'}

        with mock.patch('bodhi.server.models.get_rpm_header', return_value=rpm_header):
            changelog = self.obj.get_changelog(lastupdate=True)

        # The full changelog should be rendered, since no previous update exists.
        assert changelog == (
            ('* Sat Aug  3 2013 Fedora Releng <rel-eng@lists.fedoraproject.org> - 2.1.0-1\n- Added '
             'a free money feature.\n* Tue Jun 11 2013 Randy <bowlofeggs@fpo> - 2.0.1-2\n- Make '
             'users ☺\n'))
        # No exception should have been logged.
        assert exception.call_count == 0

    def test_release_relation(self):
        assert self.obj.release.name == "F11"
        assert len(self.obj.release.builds) == 1
        assert self.obj.release.builds[0] == self.obj

    def test_package_relation(self):
        assert self.obj.package.name == "TurboGears"
        assert len(self.obj.package.builds) == 1
        assert self.obj.package.builds[0] == self.obj

    def test_epoch(self):
        self.obj.epoch = '1'
        assert self.obj.evr, ("1", "1.0.8" == "3.fc11")


class TestUpdateInit(BasePyTestCase):
    """Tests for the update.__init__() method."""

    def test_release_missing(self):
        """If the release is not passed when creating an Update, a ValueError should be raised."""
        with pytest.raises(ValueError) as exc:
            model.Update()
        assert str(exc.value) == 'You must specify a Release when creating an Update.'


@mock.patch('bodhi.server.models.work_on_bugs_task', mock.Mock())
@mock.patch('bodhi.server.models.fetch_test_cases_task', mock.Mock())
class TestUpdateNew(BasePyTestCase):
    """Tests for the Update.new() method."""

    @mock.patch('bodhi.server.models.log.warning')
    def test_add_bugs_bodhi_not_configured(self, warning):
        """Adding a bug should log a warning if Bodhi isn't configured to handle bugs."""
        config["bodhi_email"] = None
        release = self.create_release('36')
        package = model.RpmPackage.query.filter_by(name='bodhi').one()
        build = model.RpmBuild(nvr='bodhi-6.0.0-1.fc36', release=release,
                               package=package, signed=False)
        self.db.add(build)
        data = {'release': release, 'builds': [build], 'from_tag': 'f36-build-side-1234',
                'bugs': [], 'requirements': '', 'edited': '', 'autotime': True,
                'stable_days': 3, 'stable_karma': 3, 'unstable_karma': -1,
                'notes': 'simple update', 'type': 'unspecified'}
        request = mock.MagicMock()
        request.db = self.db
        request.user.name = 'tester'
        self.db.flush()

        model.Update.new(request, data)

        warning.assert_called_with('Not configured to handle bugs')


@mock.patch('bodhi.server.models.work_on_bugs_task', mock.Mock())
@mock.patch('bodhi.server.models.fetch_test_cases_task', mock.Mock())
class TestUpdateEdit(BasePyTestCase):
    """Tests for the Update.edit() method."""

    def test_add_build_to_locked_update(self):
        """Adding a build to a locked update should raise LockedUpdateException."""
        data = {
            'edited': model.Update.query.first().alias, 'builds': ["can't", 'do', 'this']}
        request = mock.MagicMock()
        request.db = self.db
        update = model.Update.query.first()
        update.locked = True
        self.db.flush()

        with pytest.raises(model.LockedUpdateException):
            model.Update.edit(request, data)

    def test_remove_builds_from_locked_update(self):
        """Adding a build to a locked update should raise LockedUpdateException."""
        data = {
            'edited': model.Update.query.first().alias, 'builds': []}
        request = mock.MagicMock()
        request.db = self.db
        update = model.Update.query.first()
        update.locked = True
        self.db.flush()

        with pytest.raises(model.LockedUpdateException):
            model.Update.edit(request, data)

    @mock.patch('bodhi.server.models.log.warning')
    def test_add_bugs_bodhi_not_configured(self, warning):
        """Adding a bug should log a warning if Bodhi isn't configured to handle bugs."""
        config["bodhi_email"] = None
        update = model.Update.query.first()
        data = {
            'edited': update.alias, 'builds': [update.builds[0].nvr], 'bugs': [12345, ], }
        request = mock.MagicMock()
        request.db = self.db
        request.user.name = 'tester'
        with mock_sends(Message):
            model.Update.edit(request, data)

        warning.assert_called_with('Not configured to handle bugs')

    def test_empty_display_name(self):
        """An only whitespaces string should not be set as display name."""
        update = model.Update.query.first()
        data = {
            'edited': update.alias, 'builds': [update.builds[0].nvr],
            'bugs': [], 'display_name': '  '}
        request = mock.MagicMock()
        request.db = self.db
        request.user.name = 'tester'
        with mock_sends(Message):
            model.Update.edit(request, data)

        update = model.Update.query.first()
        assert update.display_name == ''

    def test_gating_required_false(self):
        """Assert that test_gating_status is not updated if test_gating is not enabled."""
        config["test_gating.required"] = False
        update = model.Update.query.first()
        update.test_gating_status = None
        data = {
            'edited': update.alias, 'builds': [update.builds[0].nvr],
            'bugs': [], 'display_name': '  '}
        request = mock.MagicMock()
        request.db = self.db
        request.user.name = 'tester'
        with mock_sends(update_schemas.UpdateEditV1):
            with mock.patch('bodhi.server.models.util.greenwave_api_post') as mock_greenwave:
                greenwave_response = {
                    'policies_satisfied': False,
                    'summary': 'what have you done‽',
                    'applicable_policies': ['taskotron_release_critical_tasks'],
                    'unsatisfied_requirements': [
                        {'testcase': 'dist.rpmdeplint',
                         'item': {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                         'type': 'test-result-failed', 'scenario': None},
                        {'testcase': 'dist.rpmdeplint',
                         'item': {'item': update.alias, 'type': 'bodhi_update'},
                         'type': 'test-result-failed', 'scenario': None}]}
                mock_greenwave.return_value = greenwave_response
                model.Update.edit(request, data)

        update = model.Update.query.first()
        assert update.test_gating_status is None

    def test_gating_required_true(self):
        """Assert that test_gating_status is updated if test_gating is enabled."""
        config["test_gating.required"] = True
        update = model.Update.query.first()
        update.test_gating_status = None
        data = {
            'edited': update.alias, 'builds': [update.builds[0].nvr],
            'bugs': [], 'display_name': '  '}
        request = mock.MagicMock()
        request.db = self.db
        request.user.name = 'tester'
        with mock_sends(update_schemas.UpdateEditV1):
            with mock.patch('bodhi.server.models.util.greenwave_api_post') as mock_greenwave:
                greenwave_response = {
                    'policies_satisfied': False,
                    'summary': 'what have you done‽',
                    'applicable_policies': ['taskotron_release_critical_tasks'],
                    'unsatisfied_requirements': [
                        {'testcase': 'dist.rpmdeplint',
                         'item': {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                         'type': 'test-result-failed', 'scenario': None},
                        {'testcase': 'dist.rpmdeplint',
                         'item': {'item': update.alias, 'type': 'bodhi_update'},
                         'type': 'test-result-failed', 'scenario': None}]}
                mock_greenwave.return_value = greenwave_response
                model.Update.edit(request, data)

        update = model.Update.query.first()
        assert update.test_gating_status == model.TestGatingStatus.failed

    def test_rawhide_update_edit_move_to_testing(self):
        """
        Assert that a pending rawhide update that was edited gets moved to testing
        if all the builds in the update are signed.
        """
        config["test_gating.required"] = True
        update = model.Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        update.status = model.UpdateStatus.pending
        update.release.composed_by_bodhi = False
        update.builds[0].signed = True
        data = {
            'edited': update.alias, 'builds': [update.builds[0].nvr],
            'bugs': [], 'display_name': '  '}
        request = mock.MagicMock()
        request.db = self.db
        request.user.name = 'tester'

        with mock_sends(update_schemas.UpdateEditV1, update_schemas.UpdateReadyForTestingV2):
            with mock.patch('bodhi.server.models.util.greenwave_api_post') as mock_greenwave:
                greenwave_response = {
                    'policies_satisfied': False,
                    'summary': 'what have you done‽',
                    'applicable_policies': ['taskotron_release_critical_tasks'],
                    'unsatisfied_requirements': [
                        {'testcase': 'dist.rpmdeplint',
                         'item': {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                         'type': 'test-result-failed', 'scenario': None},
                        {'testcase': 'dist.rpmdeplint',
                         'item': {'item': update.alias, 'type': 'bodhi_update'},
                         'type': 'test-result-failed', 'scenario': None}]}
                mock_greenwave.return_value = greenwave_response
                model.Update.edit(request, data)

        assert update.status == model.UpdateStatus.testing
        assert update.test_gating_status == model.TestGatingStatus.failed

    def test_rawhide_update_edit_stays_pending(self):
        """
        Assert that a pending rawhide update that was edited does not get moved to testing
        if not all the builds in the update are signed.
        """
        config["test_gating.required"] = True
        update = model.Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        update.status = model.UpdateStatus.pending
        update.release.composed_by_bodhi = False
        update.builds[0].signed = False
        data = {
            'edited': update.alias, 'builds': [update.builds[0].nvr],
            'bugs': [], 'display_name': '  '}
        request = mock.MagicMock()
        request.db = self.db
        request.user.name = 'tester'

        with mock_sends(update_schemas.UpdateEditV1):
            with mock.patch('bodhi.server.models.util.greenwave_api_post') as mock_greenwave:
                greenwave_response = {
                    'policies_satisfied': False,
                    'summary': 'what have you done‽',
                    'applicable_policies': ['taskotron_release_critical_tasks'],
                    'unsatisfied_requirements': [
                        {'testcase': 'dist.rpmdeplint',
                         'item': {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                         'type': 'test-result-failed', 'scenario': None},
                        {'testcase': 'dist.rpmdeplint',
                         'item': {'item': update.alias, 'type': 'bodhi_update'},
                         'type': 'test-result-failed', 'scenario': None}]}
                mock_greenwave.return_value = greenwave_response
                model.Update.edit(request, data)

        assert update.status == model.UpdateStatus.pending
        assert update.test_gating_status == model.TestGatingStatus.failed

    def test_not_rawhide_update_signed_stays_pending(self):
        """
        Assert that a non rawhide pending update that was edited does not get moved to testing
        if all the builds in the update are signed.
        """
        config["test_gating.required"] = True
        update = model.Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        update.status = model.UpdateStatus.pending
        update.release.composed_by_bodhi = True
        update.builds[0].signed = True
        data = {
            'edited': update.alias, 'builds': [update.builds[0].nvr],
            'bugs': [], 'display_name': '  '}
        request = mock.MagicMock()
        request.db = self.db
        request.user.name = 'tester'

        with mock_sends(update_schemas.UpdateEditV1):
            with mock.patch('bodhi.server.models.util.greenwave_api_post') as mock_greenwave:
                greenwave_response = {
                    'policies_satisfied': False,
                    'summary': 'what have you done‽',
                    'applicable_policies': ['taskotron_release_critical_tasks'],
                    'unsatisfied_requirements': [
                        {'testcase': 'dist.rpmdeplint',
                         'item': {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                         'type': 'test-result-failed', 'scenario': None},
                        {'testcase': 'dist.rpmdeplint',
                         'item': {'item': update.alias, 'type': 'bodhi_update'},
                         'type': 'test-result-failed', 'scenario': None}]}
                mock_greenwave.return_value = greenwave_response
                model.Update.edit(request, data)

        assert update.status == model.UpdateStatus.pending
        assert update.test_gating_status == model.TestGatingStatus.failed


@mock.patch("bodhi.server.models.tag_update_builds_task", mock.Mock())
@mock.patch('bodhi.server.models.work_on_bugs_task', mock.Mock())
@mock.patch('bodhi.server.models.fetch_test_cases_task', mock.Mock())
class TestUpdateVersionHash(BasePyTestCase):
    """Tests for the Update.version_hash property."""

    def test_version_hash(self):
        update = model.Update.query.first()

        # check with what we expect the hash to be
        initial_expected_hash = "19504edccbed061be0b47741238859a94d973138"
        assert update.version_hash == initial_expected_hash

        # calculate the hash, and check it again
        initial_expected_builds = "bodhi-2.0-1.fc17"
        assert len(update.builds) == 1
        builds = " ".join(sorted([x.nvr for x in update.builds]))
        assert builds == initial_expected_builds
        initial_calculated_hash = hashlib.sha1(str(builds).encode('utf-8')).hexdigest()
        assert update.version_hash == initial_calculated_hash

        # add another build
        package = model.RpmPackage(name='python-rpdb')
        self.db.add(package)
        build = model.RpmBuild(nvr='python-rpdb-1.3-1.fc17', package=package)
        self.db.add(build)
        update = model.Update.query.first()
        data = {
            'edited': update.alias, 'builds': [update.builds[0].nvr, build.nvr], 'bugs': []}
        request = mock.MagicMock()
        request.buildinfo = {
            build.nvr: {
                'nvr': build._get_n_v_r(), 'info': buildsys.get_session().getBuild(build.nvr)}}
        request.db = self.db
        request.user.name = 'tester'
        self.db.flush()
        with mock_sends(Message):
            model.Update.edit(request, data)

        # now, with two builds, check the hash has changed
        updated_expected_hash = "d89b54971b965505179438481d761f8b5ee64e8c"
        assert initial_expected_hash != updated_expected_hash

        # check the updated is what we expect the hash to be
        assert update.version_hash == updated_expected_hash

        # calculate the updated hash, and check it again
        updated_expected_builds = "bodhi-2.0-1.fc17 python-rpdb-1.3-1.fc17"
        assert len(update.builds) == 2
        builds = " ".join(sorted([x.nvr for x in update.builds]))
        assert builds == updated_expected_builds
        updated_calculated_hash = hashlib.sha1(str(builds).encode('utf-8')).hexdigest()
        assert update.version_hash == updated_calculated_hash


class TestUpdateGetBugKarma(BasePyTestCase):
    """Test the get_bug_karma() method."""

    def test_feedback_wrong_bug(self):
        """Feedback for other bugs should be ignored."""
        update = model.Update.query.first()
        # Let's add a bug karma to the existing comment on the bug.
        bk = model.BugKarma(karma=1, comment=update.comments[0], bug=update.bugs[0])
        self.db.add(bk)
        # Now let's associate a new bug with the update.
        bug = model.Bug(bug_id=12345, title='some title')
        update.bugs.append(bug)

        bad, good = update.get_bug_karma(bug)

        assert bad == 0
        assert good == 0

    def test_mixed_feedback(self):
        """Make sure mixed feedback is counted correctly."""
        update = model.Update.query.first()
        for i, karma in enumerate([-1, 1, 1]):
            user = model.User(name='user_{}'.format(i))
            comment = model.Comment(text='Test comment', karma=karma, user=user)
            self.db.add(comment)
            update.comments.append(comment)
            bug_karma = model.BugKarma(karma=karma, comment=comment, bug=update.bugs[0])
            self.db.add(bug_karma)

        bad, good = update.get_bug_karma(update.bugs[0])

        assert bad == -1
        assert good == 2

        # This is a "karma reset event", so the above comments should not be counted in the karma.
        user = model.User(name='bodhi')
        comment = model.Comment(text="New build", karma=0, user=user)
        self.db.add(comment)
        update.comments.append(comment)

        bad, good = update.get_bug_karma(update.bugs[0])

        assert bad == 0
        assert good == 0


class TestUpdateInstallCommand(BasePyTestCase):
    """Test the update_install_command() function."""

    def test_upgrade_in_testing(self):
        """Update is an enhancement, a security or a bugfix and is in testing."""
        update = model.Update.query.first()
        update.status = UpdateStatus.testing
        update.type = UpdateType.bugfix
        update.release.package_manager = PackageManager.dnf
        update.release.testing_repository = 'updates-testing'

        assert update.install_command == (
            f'sudo dnf upgrade --enablerepo=updates-testing --refresh --advisory={update.alias}')

    def test_upgrade_in_stable(self):
        """Update is an enhancement, a security or a bugfix and is in stable."""
        update = model.Update.query.first()
        update.status = UpdateStatus.stable
        update.type = UpdateType.bugfix
        update.release.package_manager = PackageManager.dnf
        update.release.testing_repository = 'updates-testing'

        assert update.install_command == f'sudo dnf upgrade --refresh --advisory={update.alias}'

    def test_newpackage_in_testing(self):
        """Update is a newpackage and is in testing."""
        update = model.Update.query.first()
        update.status = UpdateStatus.testing
        update.type = UpdateType.newpackage
        update.release.package_manager = PackageManager.dnf
        update.release.testing_repository = 'updates-testing'

        assert update.install_command == (
            r'sudo dnf install --enablerepo=updates-testing --refresh '
            r'--advisory={} \*'.format(update.alias))

    def test_newpackage_in_stable(self):
        """Update is a newpackage and is in stable."""
        update = model.Update.query.first()
        update.status = UpdateStatus.stable
        update.type = UpdateType.newpackage
        update.release.package_manager = PackageManager.dnf
        update.release.testing_repository = 'updates-testing'

        assert update.install_command == r'sudo dnf install --refresh ' \
                                         r'--advisory={} \*'.format(update.alias)

    def test_cannot_install(self):
        """Update is out of stable or testing repositories."""
        update = model.Update.query.first()
        update.status = UpdateStatus.obsolete

        assert update.install_command == ''

    def test_cannot_install_rawhide_testing(self):
        """Update is in testing state and is for Rawhide.

        This should be a temporary state, however, since it's not available
        in any repository, just don't show a wrong update command.
        """
        update = model.Update.query.first()
        update.status = UpdateStatus.testing
        update.type = UpdateType.bugfix
        update.release.package_manager = PackageManager.dnf
        update.release.testing_repository = 'updates-testing'
        update.release.composed_by_bodhi = False

        assert update.install_command == ''

    def test_update_command_not_possible_missing_packagemanager(self):
        """The Release of the Update misses the package manager definition."""
        update = model.Update.query.first()
        update.status = UpdateStatus.stable
        update.type = UpdateType.newpackage
        update.release.package_manager = PackageManager.unspecified
        update.release.testing_repository = 'updates-testing'

        assert update.install_command == ''

    def test_update_command_not_possible_missing_repo(self):
        """The Release of the Update misses the testing repository definition."""
        update = model.Update.query.first()
        update.status = UpdateStatus.stable
        update.type = UpdateType.newpackage
        update.release.package_manager = PackageManager.dnf
        update.release.testing_repository = None

        assert update.install_command == ''


class TestUpdateGetTestcaseKarma(BasePyTestCase):
    """Test the get_testcase_karma() method."""

    def test_feedback_wrong_testcase(self):
        """Feedback for other testcases should be ignored."""
        update = model.Update.query.first()
        # Let's add a testcase karma to the existing comment on the testcase.
        tck = model.TestCaseKarma(karma=1, comment=update.comments[0],
                                  testcase=update.builds[0].testcases[0])
        self.db.add(tck)
        # Now let's associate a new testcase with the update.
        testcase = model.TestCase(name='a testcase')
        update.builds[0].testcases.append(testcase)

        bad, good = update.get_testcase_karma(testcase)

        assert bad == 0
        assert good == 0

    def test_mixed_feedback(self):
        """Make sure mixed feedback is counted correctly."""
        update = model.Update.query.first()
        for i, karma in enumerate([-1, 1, 1]):
            user = model.User(name='user_{}'.format(i))
            comment = model.Comment(text='Test comment', karma=karma, user=user)
            self.db.add(comment)
            update.comments.append(comment)
            testcase_karma = model.TestCaseKarma(karma=karma, comment=comment,
                                                 testcase=update.builds[0].testcases[0])
            self.db.add(testcase_karma)

        bad, good = update.get_testcase_karma(update.builds[0].testcases[0])

        assert bad == -1
        assert good == 2

        # This is a "karma reset event", so the above comments should not be counted in the karma.
        user = model.User(name='bodhi')
        comment = model.Comment(text="New build", karma=0, user=user)
        self.db.add(comment)
        update.comments.append(comment)

        bad, good = update.get_testcase_karma(update.builds[0].testcases[0])

        assert bad == 0
        assert good == 0


class TestUpdateSigned(BasePyTestCase):
    """Test the Update.signed() property."""

    def test_release_without_pending_signing_tag(self):
        """If the update's release doesn't have a pending_signing_tag, it should return True."""
        update = model.Update.query.first()
        update.builds[0].signed = False
        update.release.pending_signing_tag = ''

        assert update.signed

    def test_from_tag_update(self):
        """If the update's release doesn't have a pending_signing_tag, it should return True."""
        update = model.Update.query.first()
        update.builds[0].signed = False
        update.from_tag = 'f30-side-tag'
        update.release.pending_signing_tag = ''

        assert not update.signed


class TestUpdateUpdateTestGatingStatus(BasePyTestCase):
    """Test the Update.update_test_gating_status() method."""

    @mock.patch('bodhi.server.models.log.error')
    @mock.patch('bodhi.server.util.http_session.post')
    @mock.patch('bodhi.server.util.time.sleep')
    def test_500_response_from_greenwave(self, sleep, post, error):
        """A 500 response from Greenwave should result in marking the test results as ignored."""
        post.return_value = mock.MagicMock()
        post.return_value.status_code = 500
        update = model.Update.query.first()
        # Let's set this to anything other than ignored, so we can assert that
        # update_test_gating_status() toggles it back.
        update.test_gating_status = model.TestGatingStatus.passed

        update.update_test_gating_status()

        assert update.test_gating_status == model.TestGatingStatus.waiting
        assert sleep.mock_calls == [mock.call(1), mock.call(1), mock.call(1)]
        expected_post = mock.call(
            'https://greenwave-web-greenwave.app.os.fedoraproject.org/api/v1.0/decision',
            data={"product_version": "fedora-17", "decision_context": "bodhi_update_push_testing",
                  "subject": [{"item": f"{update.builds[0].nvr}", "type": "koji_build"},
                              {"item": f"{update.alias}", "type": "bodhi_update"}],
                  "verbose": False},
            headers={'Content-Type': 'application/json'}, timeout=60)
        assert post.call_count == 4
        for i in range(4):
            # Make sure the positional arguments are correct.
            assert post.mock_calls[i][1] == expected_post[1]
            assert post.mock_calls[i][2].keys() == expected_post[2].keys()
            # The request has serialized our data as JSON. We should probably not just serialize our
            # expected JSON, because we don't have a guarantee that it will serialize to the same
            # string. So instead, let's deserialize the JSON that the mock captured and compare it
            # to our dictionary above.
            assert json.loads(post.mock_calls[i][2]['data']) == expected_post[2]['data']
            # Make sure the other stuff is all the same
            for key in expected_post[2].keys():
                if key != 'data':
                    assert post.mock_calls[i][2][key] == expected_post[2][key]
        assert error.mock_calls == (
            [mock.call((
                'Bodhi failed to send POST request to Greenwave at the following URL '
                '"https://greenwave-web-greenwave.app.os.fedoraproject.org/api/v1.0/decision". The '
                'status code was "500".')) for i in range(2)])

    @mock.patch('bodhi.server.models.log.error')
    @mock.patch('bodhi.server.util.http_session.post')
    @mock.patch('bodhi.server.util.time.sleep')
    def test_timeout_from_greenwave(self, sleep, post, error):
        """Similar to the 500 test above, a timeout should also result in marking tests ignored."""
        post.side_effect = requests.exceptions.ConnectTimeout('The connection timed out.')
        update = model.Update.query.first()
        # Let's set this to anything other than ignored, so we can assert that
        # update_test_gating_status() toggles it back.
        update.test_gating_status = model.TestGatingStatus.passed

        update.update_test_gating_status()

        assert update.test_gating_status == model.TestGatingStatus.waiting
        # The call_url() handler doesn't catch a Timeout so there are no sleeps/retries.
        assert sleep.mock_calls == []
        expected_post = mock.call(
            'https://greenwave-web-greenwave.app.os.fedoraproject.org/api/v1.0/decision',
            data={"product_version": "fedora-17", "decision_context": "bodhi_update_push_testing",
                  "subject": [{"item": f"{update.builds[0].nvr}", "type": "koji_build"},
                              {"item": f"{update.alias}", "type": "bodhi_update"}],
                  "verbose": False},
            headers={'Content-Type': 'application/json'}, timeout=60)
        assert post.call_count == 1
        # Make sure the positional arguments are correct.
        assert post.mock_calls[0][1] == expected_post[1]
        assert post.mock_calls[0][2].keys() == expected_post[2].keys()
        # The request has serialized our data as JSON. We should probably not just serialize our
        # expected JSON, because we don't have a guarantee that it will serialize to the same
        # string. So instead, let's deserialize the JSON that the mock captured and compare it
        # to our dictionary above.
        assert json.loads(post.mock_calls[0][2]['data']) == expected_post[2]['data']
        # Make sure the other stuff is all the same
        for key in expected_post[2].keys():
            if key != 'data':
                assert post.mock_calls[0][2][key] == expected_post[2][key]
        assert error.mock_calls == [mock.call('The connection timed out.')]


class TestUpdateValidateBuilds(BasePyTestCase):
    """Tests for the :class:`Update` validator for builds."""

    def setup_method(self):
        super(TestUpdateValidateBuilds, self).setup_method(self)
        self.package = model.RpmPackage(name='the-greatest-package')
        self.update = model.Update(
            user=model.User.query.filter_by(name='guest').one(),
            request=model.UpdateRequest.testing,
            notes='Useless details!',
            release=model.Release.query.filter_by(name='F17').one(),
            date_submitted=datetime(1984, 11, 2),
            requirements='rpmlint',
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
        pytest.raises(ValueError, self.update.builds.append, build2)

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
        with pytest.raises(ValueError) as cm:
            build2.update = self.update
        assert str(cm.value) == 'An update must contain builds of the same type.'


@mock.patch('bodhi.server.models.work_on_bugs_task', mock.Mock())
@mock.patch('bodhi.server.models.fetch_test_cases_task', mock.Mock())
class TestUpdateMeetsTestingRequirements(BasePyTestCase):
    """Test the Update.meets_testing_requirements() method."""

    def test_autokarma_update_reaching_stable_karma(self):
        """
        Assert that meets_testing_requirements() correctly returns True for autokarma updates
        that haven't reached the days in testing but have reached the stable_karma threshold.
        """
        update = model.Update.query.first()
        update.autokarma = True
        update.status = UpdateStatus.testing
        update.stable_karma = 1
        # Now let's add some karma to get it to the required threshold
        with mock_sends(Message, Message):
            update.comment(self.db, 'testing', author='hunter2', karma=1)

        # meets_testing_requirement() should return True since the karma threshold has been reached
        assert update.meets_testing_requirements

    def test_critpath_14_days_negative_karma(self):
        """critpath packages in testing for 14 days shouldn't go stable with negative karma."""
        update = model.Update.query.first()
        update.critpath = True
        update.status = model.UpdateStatus.testing
        update.request = None
        update.date_testing = datetime.utcnow() - timedelta(days=15)
        update.stable_karma = 1
        update.comment(self.db, 'testing', author='enemy', karma=-1)
        # This gets the update to positive karma, but not to the required 2 karma needed for
        # critpath.
        update.comment(self.db, 'testing', author='bro', karma=1)

        assert not update.meets_testing_requirements

    def test_critpath_14_days_no_negative_karma(self):
        """critpath packages in testing for 14 days can go stable without negative karma."""
        update = model.Update.query.first()
        update.critpath = True
        update.status = model.UpdateStatus.testing
        update.request = None
        update.date_testing = datetime.utcnow() - timedelta(days=15)
        update.stable_karma = 1

        assert update.meets_testing_requirements

    def test_critpath_karma_2_met(self):
        """critpath packages should be allowed to go stable when meeting required karma."""
        update = model.Update.query.first()
        update.critpath = True
        update.stable_karma = 1
        with mock_sends(Message, Message, Message, Message, Message):
            update.comment(self.db, 'testing', author='enemy', karma=-1)
            update.comment(self.db, 'testing', author='bro', karma=1)
            # Despite meeting the stable_karma, the function should still not
            # mark this as meeting testing requirements because critpath packages
            # have a higher requirement for minimum karma. So let's get it a second one.
            update.comment(self.db, 'testing', author='ham', karma=1)

        assert update.meets_testing_requirements

    def test_critpath_karma_2_required(self):
        """critpath packages should require a minimum karma."""
        update = model.Update.query.first()
        update.critpath = True
        update.stable_karma = 1

        # Despite meeting the stable_karma, the function should still not mark this as meeting
        # testing requirements because critpath packages have a higher requirement for minimum
        # karma.
        assert not update.meets_testing_requirements

    def test_critpath_negative_karma(self):
        """
        Assert that meets_testing_requirements() correctly returns False for critpath updates
        with negative karma.
        """
        update = model.Update.query.first()
        update.critpath = True
        update.comment(self.db, 'testing', author='enemy', karma=-1)
        assert not update.meets_testing_requirements

    def test_karma_2_met(self):
        """Regular packages should be allowed to go stable when meeting required karma."""
        update = model.Update.query.first()
        update.stable_karma = 3
        update.comment(self.db, 'testing', author='enemy', karma=-1)
        update.comment(self.db, 'testing', author='bro', karma=1)
        # Despite meeting the stable_karma, the function should still not mark this as meeting
        # testing requirements because critpath packages have a higher requirement for minimum
        # karma. So let's get it a second one.
        update.comment(self.db, 'testing', author='ham', karma=1)

        assert update.meets_testing_requirements

    def test_non_autokarma_update_below_stable_karma(self):
        """It should return False for non-autokarma updates below stable karma and time."""
        update = model.Update.query.first()
        update.autokarma = False
        update.comments = []
        update.status = UpdateStatus.testing
        update.stable_karma = 1

        # meets_testing_requirement() should return False since the karma threshold has not been
        # reached (note that this Update does not have any karma).
        assert not update.meets_testing_requirements

    def test_non_autokarma_update_reaching_stable_karma(self):
        """
        Assert that meets_testing_requirements() correctly returns True for non-autokarma updates
        that haven't reached the days in testing but have reached the stable_karma threshold.
        """
        update = model.Update.query.first()
        update.autokarma = False
        update.status = UpdateStatus.testing
        update.stable_karma = 1

        # meets_testing_requirement() should return True since the karma threshold has been reached
        assert update.meets_testing_requirements

    def test_test_gating_faild_no_testing_requirements(self):
        """
        The Update.meets_testing_requirements() should return False, if the test gating
        status of an update is failed.
        """
        config["test_gating.required"] = True
        update = model.Update.query.first()
        update.autokarma = False
        update.stable_karma = 1
        update.test_gating_status = TestGatingStatus.failed
        update.comment(self.db, 'I found $100 after applying this update.', karma=1,
                       author='bowlofeggs')
        # Assert that our preconditions from the docblock are correct.
        assert not update.meets_testing_requirements

    def test_test_gating_queued_no_testing_requirements(self):
        """
        The Update.meets_testing_requirements() should return False, if the test gating
        status of an update is queued.
        """
        config["test_gating.required"] = True
        update = model.Update.query.first()
        update.autokarma = False
        update.stable_karma = 1
        update.test_gating_status = TestGatingStatus.queued
        update.comment(self.db, 'I found $100 after applying this update.', karma=1,
                       author='bowlofeggs')
        # Assert that our preconditions from the docblock are correct.
        assert not update.meets_testing_requirements

    def test_test_gating_running_no_testing_requirements(self):
        """
        The Update.meets_testing_requirements() should return False, if the test gating
        status of an update is running.
        """
        config["test_gating.required"] = True
        update = model.Update.query.first()
        update.autokarma = False
        update.stable_karma = 1
        update.test_gating_status = TestGatingStatus.running
        update.comment(self.db, 'I found $100 after applying this update.', karma=1,
                       author='bowlofeggs')
        # Assert that our preconditions from the docblock are correct.
        assert not update.meets_testing_requirements

    def test_test_gating_missing_testing_requirements(self):
        """
        The Update.meets_testing_requirements() should return True, if the test gating
        status of an update is missing.
        """
        config["test_gating.required"] = True
        update = model.Update.query.first()
        update.autokarma = False
        update.stable_karma = 1
        update.test_gating_status = None
        update.comment(self.db, 'I found $100 after applying this update.', karma=1,
                       author='bowlofeggs')
        # Assert that our preconditions from the docblock are correct.
        assert update.meets_testing_requirements

    def test_test_gating_waiting_testing_requirements(self):
        """
        The Update.meets_testing_requirements() should return False, if the test gating
        status of an update is waiting.
        """
        config["test_gating.required"] = True
        update = model.Update.query.first()
        update.autokarma = False
        update.stable_karma = 1
        update.test_gating_status = TestGatingStatus.waiting
        update.comment(self.db, 'I found $100 after applying this update.', karma=1,
                       author='bowlofeggs')
        # Assert that our preconditions from the docblock are correct.
        assert not update.meets_testing_requirements

    def test_test_gating_off(self):
        """
        The Update.meets_testing_requirements() should return True if the
        testing gating is not required, regardless of its test gating status.
        """
        config["test_gating.required"] = False
        update = model.Update.query.first()
        update.autokarma = False
        update.stable_karma = 1
        update.test_gating_status = TestGatingStatus.running
        update.comment(self.db, 'I found $100 after applying this update.', karma=1,
                       author='bowlofeggs')
        # Assert that our preconditions from the docblock are correct.
        assert update.meets_testing_requirements

    def test_time_in_testing_met(self):
        """It should return True for non-critpath updates that meet time in testing."""
        update = model.Update.query.first()
        update.status = model.UpdateStatus.testing
        update.request = None
        update.date_testing = datetime.utcnow() - timedelta(days=8)
        update.stable_karma = 10

        assert update.meets_testing_requirements

    def test_time_in_testing_unmet(self):
        """It should return False for non-critpath updates that don't yet meet time in testing."""
        update = model.Update.query.first()
        update.status = model.UpdateStatus.testing
        update.request = None
        update.date_testing = datetime.utcnow() - timedelta(days=6)
        update.stable_karma = 10

        assert not update.meets_testing_requirements


@mock.patch('bodhi.server.models.work_on_bugs_task', mock.Mock())
@mock.patch('bodhi.server.models.fetch_test_cases_task', mock.Mock())
class TestUpdate(ModelTest):
    """Unit test case for the ``Update`` model."""
    klass = model.Update
    attrs = dict(
        type=UpdateType.security,
        status=UpdateStatus.pending,
        request=UpdateRequest.testing,
        severity=UpdateSeverity.medium,
        suggest=UpdateSuggestion.reboot,
        stable_karma=3,
        unstable_karma=-3,
        close_bugs=True,
        notes='foobar')

    @staticmethod
    def do_get_dependencies():
        release = model.Release(**TestRelease.attrs)
        return dict(
            builds=[model.RpmBuild(
                nvr='TurboGears-1.0.8-3.fc11', package=model.RpmPackage(**TestRpmPackage.attrs),
                release=release)],
            bugs=[model.Bug(bug_id=1), model.Bug(bug_id=2)],
            release=release,
            user=model.User(name='lmacken'))

    def get_update(self, name='TurboGears-1.0.8-3.fc11', override_args=None):
        """Return an Update instance for testing."""
        attrs = self.attrs.copy()
        pkg = self.db.query(model.RpmPackage).filter_by(name='TurboGears').one()
        rel = self.db.query(model.Release).filter_by(name='F11').one()
        attrs.update(dict(
            builds=[model.RpmBuild(nvr=name, package=pkg, release=rel)],
            release=rel))
        attrs.update(override_args or {})
        return self.klass(**attrs)

    def test___json___with_no_builds(self):
        """Test the __json__() method when there are no Builds."""
        self.obj.builds = []

        assert self.obj.__json__()['content_type'] is None

    @mock.patch('bodhi.server.models.log.warning')
    def test_add_tag_null(self, warning):
        """Test the add_tag() method with a falsey tag, such as None."""
        result = self.obj.add_tag(tag=None)

        assert result == []
        warning.assert_called_once_with('Not adding builds of %s to empty tag',
                                        'TurboGears-1.0.8-3.fc11')

    def test_autokarma_not_nullable(self):
        """Assert that the autokarma column does not allow NULL values.

        For history about why this is important, see
        https://github.com/fedora-infra/bodhi/issues/1048
        """
        assert not model.Update.__table__.columns['autokarma'].nullable

    def test_builds(self):
        assert len(self.obj.builds) == 1
        assert self.obj.builds[0].nvr == 'TurboGears-1.0.8-3.fc11'
        assert self.obj.builds[0].release.name == 'F11'
        assert self.obj.builds[0].package.name == 'TurboGears'

    def test_compose_relationship(self):
        """Assert the compose relationship works correctly when the update is locked."""
        compose = model.Compose(release=self.obj.release, request=self.obj.request)
        self.obj.locked = True
        self.db.add(compose)
        self.db.flush()

        compose = model.Compose.query.one()
        assert compose.updates == [self.obj]
        assert self.obj.compose == compose

    def test_compose_relationship_delete(self):
        """The Compose should not mess with the Update's state when deleted."""
        compose = model.Compose(release=self.obj.release, request=self.obj.request)
        self.obj.locked = True
        self.db.add(compose)
        self.db.flush()

        self.db.delete(compose)
        self.db.flush()

        assert self.obj.compose is None
        assert self.obj.request == model.UpdateRequest.testing
        assert self.obj.release == model.Release.query.one()

    def test_compose_relationship_none(self):
        """Assert that the compose relationship is None when the update is not locked."""
        compose = model.Compose(release=self.obj.release, request=self.obj.request)
        self.db.add(compose)
        self.db.flush()

        assert self.obj.compose is None
        assert not self.obj.locked
        assert model.Compose.query.one().updates == []

    def test_content_type(self):
        assert self.obj.content_type == model.ContentType.rpm

    def test_date_locked_no_compose(self):
        """Test that date_locked is None if there is no Compose."""
        self.obj.locked = True

        assert self.obj.date_locked is None

    def test_date_locked_not_locked(self):
        """Test that date_locked is None if the Update isn't locked."""
        compose = model.Compose(release=self.obj.release, request=self.obj.request)
        self.db.add(compose)
        self.db.flush()

        assert self.obj.date_locked is None

    def test_date_locked_not_locked_and_no_compose(self):
        """Test that date_locked is None if the Update isn't locked and there is no Compose."""
        assert self.obj.date_locked is None

    def test_date_locked_with_compose(self):
        """Test that date_locked is the Compose's creation date."""
        compose = model.Compose(release=self.obj.release, request=self.obj.request)
        self.obj.locked = True
        self.db.add(compose)
        self.db.flush()

        assert self.obj.date_locked == compose.date_created

    def test_greenwave_subject(self):
        """Ensure that the greenwave_subject property returns the correct value."""
        assert self.obj.greenwave_subject == (
            [{'item': 'TurboGears-1.0.8-3.fc11', 'type': 'koji_build'},
             {'item': self.obj.alias, 'type': 'bodhi_update'}])

    def test_greenwave_request_batches_single(self):
        """Ensure that the greenwave_request_batches property returns the correct value."""
        with mock.patch.dict('bodhi.server.models.config', {'greenwave_batch_size': 2}):
            assert self.obj.greenwave_subject_batch_size == 2
            assert self.obj.greenwave_request_batches(verbose=False) == (
                [
                    {
                        'product_version': 'fedora-11',
                        'decision_context': 'bodhi_update_push_testing',
                        'verbose': False,
                        'subject': [
                            {'item': 'TurboGears-1.0.8-3.fc11', 'type': 'koji_build'},
                            {'item': self.obj.alias, 'type': 'bodhi_update'},
                        ]
                    }
                ]
            )

    def test_greenwave_request_batches_multiple(self):
        """Ensure that the greenwave_request_batches property returns the correct value."""
        with mock.patch.dict('bodhi.server.models.config', {'greenwave_batch_size': 1}):
            assert self.obj.greenwave_subject_batch_size == 1
            assert self.obj.greenwave_request_batches(verbose=True) == (
                [
                    {
                        'product_version': 'fedora-11',
                        'decision_context': 'bodhi_update_push_testing',
                        'verbose': True,
                        'subject': [
                            {'item': 'TurboGears-1.0.8-3.fc11', 'type': 'koji_build'},
                        ]
                    },
                    {
                        'product_version': 'fedora-11',
                        'decision_context': 'bodhi_update_push_testing',
                        'verbose': True,
                        'subject': [
                            {'item': self.obj.alias, 'type': 'bodhi_update'},
                        ]
                    },
                ]
            )

    def test_greenwave_request_batches_multiple_critpath(self):
        """
        Ensure that the greenwave_request_batches property returns the correct value
        for critpath update with multiple batches.
        """
        with mock.patch.dict('bodhi.server.models.config', {'greenwave_batch_size': 1}):
            self.obj.critpath = True
            assert self.obj.greenwave_subject_batch_size == 1
            assert self.obj.greenwave_request_batches(verbose=True) == (
                [
                    {
                        'product_version': 'fedora-11',
                        'decision_context': 'bodhi_update_push_testing_critpath',
                        'verbose': True,
                        'subject': [
                            {'item': 'TurboGears-1.0.8-3.fc11', 'type': 'koji_build'},
                        ]
                    },
                    {
                        'product_version': 'fedora-11',
                        'decision_context': 'bodhi_update_push_testing',
                        'verbose': True,
                        'subject': [
                            {'item': 'TurboGears-1.0.8-3.fc11', 'type': 'koji_build'},
                        ]
                    },
                    {
                        'product_version': 'fedora-11',
                        'decision_context': 'bodhi_update_push_testing_critpath',
                        'verbose': True,
                        'subject': [
                            {'item': self.obj.alias, 'type': 'bodhi_update'},
                        ]
                    },
                    {
                        'product_version': 'fedora-11',
                        'decision_context': 'bodhi_update_push_testing',
                        'verbose': True,
                        'subject': [
                            {'item': self.obj.alias, 'type': 'bodhi_update'},
                        ]
                    },

                ]
            )

    def test_greenwave_request_batches_json(self):
        """Ensure that the greenwave_request_batches_json property returns the correct value."""
        requests = self.obj.greenwave_request_batches_json

        assert isinstance(requests, str)
        assert json.loads(requests) == (
            [
                {
                    'product_version': 'fedora-11',
                    'decision_context': 'bodhi_update_push_testing',
                    'verbose': True,
                    'subject': [
                        {'item': 'TurboGears-1.0.8-3.fc11', 'type': 'koji_build'},
                        {'item': self.obj.alias, 'type': 'bodhi_update'},
                    ]
                }
            ]
        )

    def test_mandatory_days_in_testing_critpath(self):
        """
        The Update.mandatory_days_in_testing method should be the configured value
        for critpath if it is a critpath update.
        """
        update = self.obj
        update.critpath = True

        # Configured value.
        expected = int(config.get('critpath.stable_after_days_without_negative_karma'))

        assert update.mandatory_days_in_testing == expected

    def test_mandatory_days_in_testing(self):
        """
        The Update.mandatory_days_in_testing method should be a positive integer if the
        mandatory_days_in_testing attribute of release is not truthy.
        """
        assert self.obj.mandatory_days_in_testing == 7

    def test_mandatory_days_in_testing_false(self):
        """
        The Update.mandatory_days_in_testing method should be 0 if the
        mandatory_days_in_testing attribute of release is not truthy.
        """
        config["fedora.mandatory_days_in_testing"] = 0
        assert self.obj.mandatory_days_in_testing == 0

    def test_mandatory_days_in_testing_release_not_configured(self):
        """mandatory_days_in_testing() should return 0 if there is no config for the release."""
        del config["fedora.mandatory_days_in_testing"]
        assert self.obj.mandatory_days_in_testing == 0

    def test_days_to_stable_critpath(self):
        """
        The Update.days_to_stable() method should return a positive integer depending
        on the configuration.
        """
        update = self.get_update()
        update.critpath = True
        update.date_testing = datetime.utcnow() + timedelta(days=-4)

        critpath_days_to_stable = int(
            config.get('critpath.stable_after_days_without_negative_karma'))

        assert update.days_to_stable == critpath_days_to_stable - 4

    def test_days_to_stable_meets_testing_requirements(self):
        """
        The Update.days_to_stable() method should return 0 if Update.meets_testing_requirements()
        returns True.
        """
        update = self.obj
        update.autokarma = False
        update.stable_karma = 1
        update.comment(self.db, 'I found $100 after applying this update.', karma=1,
                       author='bowlofeggs')
        # Assert that our preconditions from the docblock are correct.
        assert update.meets_testing_requirements

        assert update.days_to_stable == 0

    def test_days_to_stable_not_meets_testing_requirements_no_date_testing(self):
        """
        The Update.days_to_stable() method should return 0 if Update.meets_testing_requirements()
        returns False but the Update's date_testing attribute is not truthy.
        """
        update = self.get_update()
        # Assert that our preconditions from the docblock are correct.
        assert not update.meets_testing_requirements
        assert update.date_testing is None

        assert update.days_to_stable == 0

    def test_days_to_stable_not_meets_testing_requirements_with_date_testing(self):
        """
        The Update.days_to_stable() method should return a positive integer if
        Update.meets_testing_requirements() returns False and the Update's date_testing attribute is
        truthy.
        """
        update = self.get_update()
        update.date_testing = datetime.utcnow() + timedelta(days=-4)
        # Assert that our preconditions from the docblock are correct.
        assert not update.meets_testing_requirements

        assert update.days_to_stable == 3

    def test_days_to_stable_zero(self):
        """
        The Update.days_to_stable() method should only return a positive integer or zero.
        In the past, days_to_stable() could return negative integers when the mandatory days in
        testing was less than the number of days in testing. If the mandatory days in testing is
        less than or equal to the number of days in testing, days_to_stable() should return zero.
        See issue #1708.
        """
        config["test_gating.required"] = True
        update = self.obj
        update.autokarma = False
        update.test_gating_status = TestGatingStatus.failed

        update.date_testing = datetime.utcnow() + timedelta(days=-8)
        assert not update.meets_testing_requirements

        assert update.mandatory_days_in_testing <= update.days_in_testing
        assert update.days_to_stable == 0

    def test_days_to_stable_positive(self):
        """
        The Update.days_to_stable() method should only return a positive integer or zero.
        In the past, days_to_stable() could return negative integers when the mandatory days in
        testing was less than the number of days in testing. If the mandatory days in testing is
        greater than the number of days in testing, return the positive number of days until
        stable. See issue #1708.
        """
        config["test_gating.required"] = True
        update = self.obj
        update.autokarma = False
        update.test_gating_status = TestGatingStatus.failed

        update.date_testing = datetime.utcnow() + timedelta(days=-3)
        assert not update.meets_testing_requirements

        assert update.mandatory_days_in_testing > update.days_in_testing
        assert update.days_to_stable == 4

    def test_requested_tag_request_none(self):
        """requested_tag() should raise RuntimeError if the Update's request is None."""
        self.obj.request = None

        with pytest.raises(RuntimeError) as exc:
            self.obj.requested_tag
        assert str(exc.value) == f'Unable to determine requested tag for {self.obj.alias}.'

    def test_requested_tag_request_obsolete(self):
        """requested_tag() should return the candidate_tag if the request is obsolete."""
        self.obj.request = UpdateRequest.obsolete

        assert self.obj.requested_tag == self.obj.release.candidate_tag

    def test_side_tag_locked_false(self):
        """Test the side_tag_locked property when it is false."""
        self.obj.status = model.UpdateStatus.side_tag_active
        self.obj.request = None

        assert not self.obj.side_tag_locked

    def test_side_tag_locked_true(self):
        """Test the side_tag_locked property when it is true."""
        self.obj.status = model.UpdateStatus.side_tag_active
        self.obj.request = model.UpdateRequest.stable

        assert self.obj.side_tag_locked

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
        assert comment.call_count == 0
        # Make sure close() was called correctly.
        assert [c[1][0] for c in close.mock_calls] == [1, 2]
        assert all(
            ['to the Fedora 11 stable repository' in c[2]['comment']
                for c in close.mock_calls]) == True
        assert all(
            [c[2]['versions']['TurboGears'] == 'TurboGears-1.0.8-3.fc11'
                for c in close.mock_calls]) == True

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
        assert [c[1][0] for c in comment.mock_calls] == [1, 2]
        assert all(
            ['pushed to the Fedora 11 stable repository' in c[1][1]
                for c in comment.mock_calls]) == True
        # No bugs should have been closed
        assert close.call_count == 0

    @mock.patch('bodhi.server.util.http_session')
    @mock.patch.dict(util.config, {
        'critpath.type': 'pdc',
        'pdc_url': 'http://domain.local'
    })
    def test_contains_critpath_component(self, session):
        """ Verifies that the static function of contains_critpath_component
        determines that one of the builds has a critpath component.
        """
        session.get.return_value.status_code = 200
        session.get.return_value.json.return_value = {
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
        assert update.contains_critpath_component(update.builds, update.release.name)

    @mock.patch('bodhi.server.util.http_session')
    @mock.patch.dict(util.config, {
        'critpath.type': 'pdc',
        'pdc_url': 'http://domain.local'
    })
    def test_contains_critpath_component_not_critpath(self, session):
        """ Verifies that the static function of contains_critpath_component
        determines that none of the builds are critpath components.
        """
        session.get.return_value.status_code = 200
        session.get.return_value.json.return_value = {
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
            name='fc25', long_name='Fedora 25',
            id_prefix='FEDORA', dist_tag='dist-fc25',
            stable_tag='dist-fc25-updates',
            testing_tag='dist-fc25-updates-testing',
            candidate_tag='dist-fc25-updates-candidate',
            pending_signing_tag='dist-fc25-updates-testing-signing',
            pending_testing_tag='dist-fc25-updates-testing-pending',
            pending_stable_tag='dist-fc25-updates-pending',
            override_tag='dist-fc25-override',
            branch='fc25', version='25')
        assert not update.contains_critpath_component(update.builds, update.release.name)

    def test_unpush_build(self):
        assert len(self.obj.builds) == 1
        b = self.obj.builds[0]
        release = self.obj.release
        koji = buildsys.get_session()
        koji.__tagged__[b.nvr] = [release.testing_tag,
                                  release.pending_signing_tag,
                                  release.pending_testing_tag,
                                  # Add an unknown tag that we shouldn't touch
                                  release.dist_tag + '-compose']
        self.obj.builds[0].unpush(koji)
        assert koji.__moved__ == [('dist-f11-updates-testing',
                                   'dist-f11-updates-candidate',
                                   'TurboGears-1.0.8-3.fc11')]
        assert koji.__untag__ == [('dist-f11-updates-testing-signing',
                                   'TurboGears-1.0.8-3.fc11'),
                                  ('dist-f11-updates-testing-pending',
                                   'TurboGears-1.0.8-3.fc11')]

    def test_unpush_pending_stable(self):
        """Test unpush() on a pending stable tagged build."""
        release = self.obj.release
        build = self.obj.builds[0]
        koji = buildsys.get_session()
        koji.__tagged__[build.nvr] = [
            release.testing_tag, release.pending_signing_tag, release.pending_testing_tag,
            release.pending_stable_tag,
            # Add an unknown tag that we shouldn't touch
            release.dist_tag + '-compose']

        build.unpush(koji)

        assert koji.__moved__ == [('dist-f11-updates-testing',
                                   'dist-f11-updates-candidate',
                                   'TurboGears-1.0.8-3.fc11')]
        assert koji.__untag__ == [
            ('dist-f11-updates-testing-signing', 'TurboGears-1.0.8-3.fc11'),
            ('dist-f11-updates-testing-pending', 'TurboGears-1.0.8-3.fc11'),
            ('dist-f11-updates-pending', 'TurboGears-1.0.8-3.fc11')]

    def test_unpush_pending_stable_from_sidetag(self):
        """Test unpush() on a pending stable tagged build originated from side-tag."""
        release = self.obj.release
        build = self.obj.builds[0]
        koji = buildsys.get_session()
        koji.__tagged__[build.nvr] = [
            release.testing_tag, release.pending_signing_tag, release.pending_testing_tag,
            release.pending_stable_tag, 'f35-build-side-12345',
            # Add an unknown tag that we shouldn't touch
            release.dist_tag + '-compose']

        build.unpush(koji, from_side_tag=True)

        assert koji.__untag__ == [
            ('dist-f11-updates-testing', 'TurboGears-1.0.8-3.fc11'),
            ('dist-f11-updates-testing-signing', 'TurboGears-1.0.8-3.fc11'),
            ('dist-f11-updates-testing-pending', 'TurboGears-1.0.8-3.fc11'),
            ('dist-f11-updates-pending', 'TurboGears-1.0.8-3.fc11')]

    @mock.patch('bodhi.server.models.log.info')
    def test_unpush_update(self, info):
        """Unpushing an update shouldn't clear the override tag from builds."""
        self.obj.status = UpdateStatus.testing
        assert len(self.obj.builds) == 1
        b = self.obj.builds[0]
        release = self.obj.release
        koji = buildsys.get_session()
        koji.__tagged__[b.nvr] = [release.testing_tag,
                                  release.pending_signing_tag,
                                  release.pending_testing_tag,
                                  release.override_tag,
                                  # Add an unknown tag that we shouldn't touch
                                  release.dist_tag + '-compose']
        self.obj.unpush(self.db)
        info.assert_any_call("Skipping override tag")

    @mock.patch('bodhi.server.models.log.debug')
    def test_unpush_stable(self, debug):
        """unpush() should raise a BodhiException on a stable update."""
        self.obj.status = UpdateStatus.stable
        self.obj.untag = mock.MagicMock()

        with pytest.raises(BodhiException) as exc:
            self.obj.unpush(self.db)
        assert str(exc.value) == "Can't unpush a stable update"
        debug.assert_called_once_with('Unpushing %s', self.obj.alias)
        assert self.obj.untag.call_count == 0

    @mock.patch('bodhi.server.models.log.debug')
    def test_unpush_unpushed(self, debug):
        """unpush() should do nothing on an unpushed update."""
        self.obj.status = UpdateStatus.unpushed
        self.obj.untag = mock.MagicMock()

        self.obj.unpush(self.db)

        assert debug.mock_calls == (
            [mock.call('Unpushing %s', self.obj.alias),
             mock.call('%s already unpushed', self.obj.alias)])
        assert self.obj.untag.call_count == 0

    def test_title(self):
        assert self.obj.title == 'TurboGears-1.0.8-3.fc11'

    def test_get_title_display_name(self):
        """If the user has set a display_name on the update, get_title() should use that."""
        update = self.get_update()
        update.display_name = 'some human made title'

        assert update.get_title(beautify=True) == 'some human made title'

    @pytest.mark.parametrize('beautify', (False, True))
    def test_get_title_no_builds(self, beautify):
        """If the update include no builds, return update alias."""
        update = self.get_update()
        update.builds = []
        assert update.get_title(beautify=beautify) == update.alias

        update.display_name = 'some human made title'
        if beautify:
            assert update.get_title(beautify=beautify) == 'some human made title'
        else:
            assert update.get_title(beautify=beautify) == update.alias

    def test_get_title_with_beautify(self):
        update = self.get_update()
        rpm_build = update.builds[0]
        assert update.get_title(beautify=True) == 'TurboGears'
        assert update.get_title(nvr=True, beautify=True) == 'TurboGears-1.0.8-3.fc11'

        update.builds.append(rpm_build)
        assert update.get_title(beautify=True) == 'TurboGears and TurboGears'
        assert update.get_title(nvr=True, beautify=True) == (
            'TurboGears-1.0.8-3.fc11 and TurboGears-1.0.8-3.fc11')

        update.builds.append(rpm_build)
        assert update.get_title(beautify=True), 'TurboGears, TurboGears == and 1 more'
        assert update.get_title(nvr=True, beautify=True) == (
            'TurboGears-1.0.8-3.fc11, TurboGears-1.0.8-3.fc11, and 1 more')

        assert html.unescape(update.get_title(amp=True, beautify=True)) == (
            'TurboGears, TurboGears, & 1 more')
        assert html.unescape(update.get_title(amp=True, nvr=True, beautify=True)) == (
            'TurboGears-1.0.8-3.fc11, TurboGears-1.0.8-3.fc11, & 1 more')

    def test_pkg_str(self):
        """ Ensure str(pkg) is correct """
        assert str(self.obj.builds[0].package) == (
            '================================================================================\n   '
            '  TurboGears\n======================================================================='
            '=========\n\n Pending Updates (1)\n    o TurboGears-1.0.8-3.fc11\n')

    def test_bugstring(self):
        assert self.obj.get_bugstring() == '1 2'

    def test_epel_id(self):
        """ Make sure we can handle id_prefixes that contain dashes.
        eg: FEDORA-EPEL
        """
        self.db.add(model.User(name='guest'))
        release = model.Release(
            name='EL-5', long_name='Fedora EPEL 5', id_prefix='FEDORA-EPEL',
            dist_tag='dist-5E-epel', stable_tag='dist-5E-epel',
            testing_tag='dist-5E-epel-testing', candidate_tag='dist-5E-epel-testing-candidate',
            pending_signing_tag='dist-5E-epel-testing-signing',
            pending_testing_tag='dist-5E-epel-testing-pending',
            pending_stable_tag='dist-5E-epel-pending', override_tag='dist-5E-epel-override',
            branch='el5', version='5')
        self.db.add(release)
        self.db.flush()
        update = self.create_update(build_nvrs=['TurboGears-2.1-1.el5'],
                                    release_name=release.name)
        assert update.alias.startswith(f'FEDORA-EPEL-{time.localtime()[0]}')

    def test_dupe(self):
        with pytest.raises(IntegrityError):
            session = Session()
            session.add(self.get_update())
            session.commit()

    def test_karma_no_comments(self):
        """Check that karma returns the correct value with one negative and two positive comments.
        """
        assert self.obj.karma == 0

    def test_karma_one_negative_two_positive(self):
        """Check that karma returns the correct value with one negative and two positive comments.
        """
        self.obj.comment(self.db, "foo", 1, 'foo')
        self.obj.comment(self.db, "foo", -1, 'bar')
        self.obj.comment(self.db, "foo", 1, 'biz')

        assert self.obj.karma == 1

    def test_karma_two_negative_one_positive(self):
        """Check that karma returns the correct value with two negative and one positive comments.
        """
        self.obj.comment(self.db, "foo", -1, 'foo')
        self.obj.comment(self.db, "foo", -1, 'bar')
        self.obj.comment(self.db, "foo", 1, 'biz')

        assert self.obj.karma == -1

    def test__composite_karma_ignores_comments_before_new_build(self):
        """Assert that _composite_karma ignores karma from before a new build karma reset event."""
        self.obj.comment(self.db, "foo", -1, 'foo')
        self.obj.comment(self.db, "foo", -1, 'bar')
        # This is a "karma reset event", so the above comments should not be counted in the karma.
        self.obj.comment(self.db, "New build", 0, 'bodhi')
        self.obj.comment(self.db, "foo", 1, 'biz')

        assert self.obj._composite_karma == (1, 0)

    def test__composite_karma_ignores_comments_before_removed_build(self):
        """Assert that _composite_karma ignores karma from before a removed build karma reset event.
        """
        self.obj.comment(self.db, "foo", 1, 'foo')
        self.obj.comment(self.db, "foo", 1, 'bar')
        # This is a "karma reset event", so the above comments should not be counted in the karma.
        self.obj.comment(self.db, "Removed build", 0, 'bodhi')
        self.obj.comment(self.db, "foo", -1, 'biz')

        assert self.obj._composite_karma == (0, -1)

    def test__composite_karma_ignores_comments_without_karma(self):
        """
        Assert that _composite_karma ignores comments that don't carry karma.

        See https://github.com/fedora-infra/bodhi/issues/829
        """
        self.obj.comment(self.db, "It ate my ostree", -1, 'dusty')
        self.obj.comment(self.db, "i love it push to stable now", 1, 'ididntreallytestitlol')
        # In bug #829, this comment would have overridden dusty's earlier -1 changing his vote to be
        # 0.
        self.obj.comment(self.db, "plz no don't… my ostreeeeee!", 0, 'dusty')

        # The composite karma should be 1, -1 since dusty's earlier vote should still count.
        assert self.obj._composite_karma == (1, -1)

    def test__composite_karma_ignores_old_comments(self):
        """Assert that _composite_karma ignores karma from a user's previous responses."""
        self.obj.comment(self.db, "I", -1, 'foo')
        self.obj.comment(self.db, "can't", 1, 'foo')
        self.obj.comment(self.db, "make", -1, 'foo')
        self.obj.comment(self.db, "up", 1, 'foo')
        self.obj.comment(self.db, "my", -1, 'foo')
        self.obj.comment(self.db, "mind", 1, 'foo')
        self.obj.comment(self.db, ".", -37, 'foo')

        assert self.obj._composite_karma == (0, -37)

    def test__composite_karma_mixed_case(self):
        """Assert _composite_karma with mixed responses that hits a lot of the method."""
        self.obj.comment(self.db, "ignored", -1, 'foo1')
        self.obj.comment(self.db, "forgotten", -1, 'foo2')
        # This is a "karma reset event", so the above comments should not be counted in the karma.
        self.obj.comment(self.db, "Removed build", 0, 'bodhi')
        self.obj.comment(self.db, "Nice job", -1, 'foo')
        self.obj.comment(self.db, "Whoops my last comment was wrong", 1, 'foo')
        self.obj.comment(self.db, "LGTM", 1, 'foo2')
        self.obj.comment(self.db, "Don't ignore me", -1, 'foo1')

        assert self.obj._composite_karma == (2, -1)

    def test__composite_karma_no_comments(self):
        """Assert _composite_karma with no comments is (0, 0)."""
        assert self.obj._composite_karma == (0, 0)

    def test__composite_karma_one_negative_two_positive(self):
        """Assert that _composite_karma returns (2, -1) with one negative and two positive comments.
        """
        self.obj.comment(self.db, "foo", 1, 'foo')
        self.obj.comment(self.db, "foo", -1, 'bar')
        self.obj.comment(self.db, "foo", 1, 'biz')

        assert self.obj._composite_karma == (2, -1)

    def test_check_karma_thresholds_obsolete(self):
        """check_karma_thresholds() should no-op on an obsolete update."""
        self.obj.status = UpdateStatus.obsolete
        self.obj.request = None
        self.obj.comment(self.db, "foo", 1, 'biz')
        self.obj.stable_karma = 1

        self.obj.check_karma_thresholds(self.db, 'bowlofeggs')

        assert self.obj.request is None
        assert self.obj.status == UpdateStatus.obsolete

    def test_check_karma_thresholds_gating_fail(self):
        """check_karma_thresholds should no-op on an update that meets
        the threshold but does not meet gating requirements.
        """
        config["test_gating.required"] = True
        self.obj.status = UpdateStatus.testing
        self.obj.request = None
        self.obj.autokarma = True
        self.obj.comment(self.db, "foo", 1, 'biz')
        self.obj.stable_karma = 1
        self.obj.test_gating_status = TestGatingStatus.failed

        self.obj.check_karma_thresholds(self.db, 'bowlofeggs')

        assert self.obj.request is None
        assert self.obj.status == UpdateStatus.testing

    def test_critpath_approved_no_release_requirements(self):
        """critpath_approved() should use the broad requirements if the release doesn't have any."""
        self.obj.critpath = True
        self.obj.comment(self.db, "foo", 1, 'biz')
        release_name = self.obj.release.name.lower().replace('-', '')

        with mock.patch.dict(
                config,
                {'{}.status'.format(release_name): 'stable', 'critpath.num_admin_approvals': 0,
                 'critpath.min_karma': 1}):
            assert self.obj.critpath_approved

    def test_critpath_approved_release_requirements(self):
        """critpath_approved() should use the release requirements if they are defined."""
        self.obj.critpath = True
        self.obj.comment(self.db, "foo", 1, 'biz')
        release_name = self.obj.release.name.lower().replace('-', '')

        with mock.patch.dict(
                config,
                {'{}.status'.format(release_name): 'stable', 'critpath.num_admin_approvals': 0,
                 'critpath.min_karma': 1,
                 '{}.{}.critpath.num_admin_approvals'.format(release_name, 'stable'): 0,
                 '{}.{}.critpath.min_karma'.format(release_name, 'stable'): 2}):
            assert not self.obj.critpath_approved

    def test_last_modified_no_dates(self):
        """last_modified() should raise ValueError if there are no available dates."""
        self.obj.date_submitted = None
        self.obj.date_modified = None

        with pytest.raises(ValueError) as exc:
            self.obj.last_modified
        assert 'Update has no timestamps set:' in str(exc.value)

    def test_stable_karma(self):
        update = self.obj
        update.request = None
        update.status = UpdateStatus.testing
        assert update.karma == 0
        assert update.request is None
        update.comment(self.db, "foo", 1, 'foo')
        assert update.karma == 1
        assert update.request is None
        update.comment(self.db, "foo", 1, 'bar')
        assert update.karma == 2
        assert update.request is None
        # Let's flush out any messages that have been sent.
        self.db.info['messages'] = []
        expected_message_0 = update_schemas.UpdateCommentV1.from_dict(
            {'comment': self.obj['comments'][0], 'agent': 'biz'})
        expected_message_1 = update_schemas.UpdateKarmaThresholdV1.from_dict(
            {'update': self.obj, 'status': 'stable'})
        expected_message_2 = update_schemas.UpdateRequestStableV1.from_dict(
            {'update': self.obj, 'agent': 'bodhi'})

        with mock_sends(expected_message_2, expected_message_1, expected_message_0):
            update.comment(self.db, "foo", 1, 'biz')
            # comment alters the update a bit, so we need to adjust the expected messages to
            # reflect those changes so the mock_sends() check will pass.
            expected_message_0.body['comment'] = self.obj['comments'][-2].__json__()
            # Since we cheated and copied comment 0, we need to change the headers to show biz
            # as the user instead of foo.
            expected_message_0._headers['fedora_messaging_user_biz'] = True
            del expected_message_0._headers['fedora_messaging_user_foo']
            expected_message_1.body['update'] = self.obj.__json__()
            expected_message_2.body['update'] = self.obj.__json__()
            self.db.commit()

        assert update.karma == 3
        assert update.request == UpdateRequest.stable

    def test_obsolete_if_unstable_unstable(self):
        """Test obsolete_if_unstable() when all conditions are met for instability."""
        self.obj.autokarma = True
        self.obj.status = UpdateStatus.pending
        self.obj.request = UpdateRequest.testing
        self.obj.unstable_karma = -1
        self.obj.comment(self.db, 'foo', -1, 'foo', check_karma=False)

        assert self.obj.status == UpdateStatus.obsolete

    @mock.patch('bodhi.server.models.log.warning')
    def test_remove_tag_emptystring(self, warning):
        """Test remove_tag() with a tag of ''."""
        assert self.obj.remove_tag('') == []

        warning.assert_called_once_with(
            'Not removing builds of %s from empty tag', self.obj.title)

    def test_revoke_no_request(self):
        """revoke() should raise BodhiException on an Update with no request."""
        self.obj.request = None

        with pytest.raises(BodhiException) as exc:
            self.obj.revoke()
        assert str(exc.value) == 'Can only revoke an update with an existing request'

    def test_unstable_karma(self):
        update = self.obj
        update.status = UpdateStatus.testing
        assert update.karma == 0
        assert update.status == UpdateStatus.testing
        update.comment(self.db, "foo", -1, 'foo')
        assert update.status == UpdateStatus.testing
        assert update.karma == -1
        update.comment(self.db, "bar", -1, 'bar')
        assert update.status == UpdateStatus.testing
        assert update.karma == -2
        # Let's flush out any messages that have been sent.
        self.db.info['messages'] = []
        expected_message_0 = update_schemas.UpdateCommentV1.from_dict(
            {'comment': self.obj['comments'][0], 'agent': 'biz'})
        expected_message_1 = update_schemas.UpdateKarmaThresholdV1.from_dict(
            {'update': self.obj, 'status': 'unstable'})

        with mock_sends(expected_message_1, expected_message_0):
            update.comment(self.db, "biz", -1, 'biz')
            # comment alters the update a bit, so we need to adjust the expected messages to
            # reflect those changes so the mock_sends() check will pass.
            expected_message_0.body['comment'] = self.obj['comments'][-2].__json__()
            # Since we cheated and copied comment 0, we need to change the headers to show biz
            # as the user instead of foo.
            expected_message_0._headers['fedora_messaging_user_biz'] = True
            del expected_message_0._headers['fedora_messaging_user_foo']
            expected_message_1.body['update'] = self.obj.__json__()
            self.db.commit()

        assert update.karma == -3
        assert update.status == UpdateStatus.obsolete

    def test_update_bugs(self):
        update = self.obj
        assert len(update.bugs) == 2
        session = self.db

        # try just adding bugs
        bugs = ['1234']
        update.update_bugs(bugs, session)
        assert len(update.bugs) == 1
        assert update.bugs[0].bug_id == 1234

        # try just removing
        bugs = []
        update.update_bugs(bugs, session)
        assert len(update.bugs) == 0
        assert self.db.query(model.Bug).filter_by(bug_id=1234).first() is None

        # Test new duplicate bugs
        bugs = ['1234', '1234']
        update.update_bugs(bugs, session)
        assert len(update.bugs) == 1

        # Try adding a new bug, and removing the rest
        bugs = ['4321']
        update.update_bugs(bugs, session)
        assert len(update.bugs) == 1
        assert update.bugs[0].bug_id == 4321
        assert self.db.query(model.Bug).filter_by(bug_id=1234).first() is None

        # Try removing a bug when it already has BugKarma
        karma = BugKarma(bug_id=4321, karma=1)
        self.db.add(karma)
        self.db.flush()
        bugs = ['5678']
        update.update_bugs(bugs, session)
        assert len(update.bugs) == 1
        assert update.bugs[0].bug_id == 5678
        assert self.db.query(model.Bug).filter_by(bug_id=4321).count() == 1

    def test_update_bugs_security(self):
        """Associating an Update with a security Bug should mark the Update as security."""
        bug = model.Bug(bug_id=1075839, security=True)
        self.db.add(bug)
        self.obj.type = UpdateType.enhancement

        self.obj.update_bugs([1075839], self.db)

        assert self.obj.type == UpdateType.security

    def test_unicode_bug_title(self):
        bug = self.obj.bugs[0]
        bug.title = 'foo\xe9bar'
        from bodhi.server.util import bug_link
        link = bug_link(None, bug)

        assert link == ("<a target='_blank' href='https://bugzilla.redhat.com/show_bug.cgi?id=1'"
                        " class='notblue'>BZ#1</a> foo\xe9bar")

    def test_set_request_pending_testing_gating_false(self):
        """Ensure that test gating is not updated when it is disabled in config."""
        config["test_gating.required"] = False
        req = DummyRequest(user=DummyUser())
        req.errors = cornice.Errors()
        req.koji = buildsys.get_session()
        self.obj.request = None
        self.obj.test_gating_status = None
        assert self.obj.status == UpdateStatus.pending

        with mock.patch('bodhi.server.models.util.greenwave_api_post') as mock_greenwave:
            greenwave_response = {
                'policies_satisfied': False,
                'summary': 'what have you done‽',
                'applicable_policies': ['taskotron_release_critical_tasks'],
                'unsatisfied_requirements': [
                    {'testcase': 'dist.rpmdeplint',
                     'item': {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                     'type': 'test-result-failed', 'scenario': None},
                    {'testcase': 'dist.rpmdeplint',
                     'item': {'item': self.obj.alias, 'type': 'bodhi_update'},
                     'type': 'test-result-failed', 'scenario': None}]}
            mock_greenwave.return_value = greenwave_response
            with mock_sends(Message):
                self.obj.set_request(self.db, UpdateRequest.testing, req.user.name)

        assert self.obj.request == UpdateRequest.testing
        assert self.obj.test_gating_status is None

    def test_set_request_pending_testing_gating_true(self):
        """Ensure that test gating is  updated when it is enabled in config."""
        config["test_gating.required"] = True
        req = DummyRequest(user=DummyUser())
        req.errors = cornice.Errors()
        req.koji = buildsys.get_session()
        self.obj.request = None
        self.obj.test_gating_status = None
        assert self.obj.status == UpdateStatus.pending

        with mock.patch('bodhi.server.models.util.greenwave_api_post') as mock_greenwave:
            greenwave_response = {
                'policies_satisfied': False,
                'summary': 'what have you done‽',
                'applicable_policies': ['taskotron_release_critical_tasks'],
                'unsatisfied_requirements': [
                    {'testcase': 'dist.rpmdeplint',
                     'item': {'item': 'bodhi-2.0-1.fc17', 'type': 'koji_build'},
                     'type': 'test-result-failed', 'scenario': None},
                    {'testcase': 'dist.rpmdeplint',
                     'item': {'item': self.obj.alias, 'type': 'bodhi_update'},
                     'type': 'test-result-failed', 'scenario': None}]}
            mock_greenwave.return_value = greenwave_response
            with mock_sends(Message):
                self.obj.set_request(self.db, UpdateRequest.testing, req.user.name)

        assert self.obj.request == UpdateRequest.testing
        assert self.obj.test_gating_status == TestGatingStatus.failed

    def test_set_request_pending_stable(self):
        """Ensure that we can submit an update to stable if it is pending and has enough karma."""
        req = DummyRequest(user=DummyUser())
        req.errors = cornice.Errors()
        req.koji = buildsys.get_session()
        assert self.obj.status == UpdateStatus.pending
        self.obj.stable_karma = 1
        with mock_sends(Message):
            self.obj.comment(self.db, 'works', karma=1, author='bowlofeggs')

        self.obj.set_request(self.db, UpdateRequest.stable, req.user.name)

        assert self.obj.request == UpdateRequest.stable
        assert self.obj.status == UpdateStatus.pending

        self.obj = mock.Mock()
        self.obj.remove_tag(self.obj.release.pending_testing_tag)
        self.obj.remove_tag.assert_called_once_with(self.obj.release.pending_testing_tag)

    @mock.patch('bodhi.server.models.buildsys.get_session')
    def test_set_request_resubmit_candidate_tag_missing(self, get_session):
        """Ensure that set_request() adds the candidate tag back to a resubmitted build."""
        req = DummyRequest(user=DummyUser())
        req.errors = cornice.Errors()
        req.koji = get_session.return_value
        self.obj.status = UpdateStatus.unpushed
        self.obj.request = None
        expected_message = update_schemas.UpdateRequestTestingV1.from_dict(
            {'update': self.obj, 'agent': req.user.name})

        with mock_sends(expected_message):
            self.obj.set_request(self.db, 'testing', req.user.name)
            # set_request alters the update a bit, so we need to adjust the expected message to
            # reflect those changes so the mock_sends() check will pass.
            expected_message.body['update']['status'] = 'pending'
            expected_message.body['update']['request'] = 'testing'
            expected_message.body['update']['comments'] = self.obj.__json__()['comments']
            self.db.commit()

        assert self.obj.status == UpdateStatus.pending
        assert self.obj.request == UpdateRequest.testing
        assert get_session.return_value.tagBuild.mock_calls == (
            [mock.call(self.obj.release.pending_signing_tag, self.obj.builds[0].nvr, force=True),
             mock.call(self.obj.release.candidate_tag, self.obj.builds[0].nvr, force=True)])

    def test_set_request_revoke_pending_stable(self):
        """Ensure that we can revoke a pending/stable update with set_request()."""
        req = DummyRequest(user=DummyUser())
        req.errors = cornice.Errors()
        req.koji = buildsys.get_session()
        self.obj.status = UpdateStatus.pending
        self.obj.request = UpdateRequest.stable
        expected_message = update_schemas.UpdateRequestRevokeV1.from_dict(
            {'update': self.obj, 'agent': req.user.name})

        with mock_sends(expected_message):
            self.obj.set_request(self.db, UpdateRequest.revoke, req.user.name)
            # set_request alters obj, so let's modify the expected_message with the updated obj.
            expected_message.body['update'] = self.obj.__json__()
            self.db.commit()

        assert self.obj.request is None
        assert self.obj.status == UpdateStatus.pending

    def test_set_request_untested_stable(self):
        """
        Ensure that we can't submit an update for stable if it hasn't met the
        minimum testing requirements.
        """
        req = DummyRequest(user=DummyUser())
        req.errors = cornice.Errors()
        req.koji = buildsys.get_session()
        assert self.obj.status == UpdateStatus.pending
        with pytest.raises(BodhiException) as exc:
            self.obj.set_request(self.db, UpdateRequest.stable, req.user.name)
        assert str(exc.value) == config.get('not_yet_tested_msg')
        assert self.obj.request == UpdateRequest.testing
        assert self.obj.status == UpdateStatus.pending

    def test_set_request_stable_after_week_in_testing(self):
        req = DummyRequest()
        req.errors = cornice.Errors()
        req.koji = buildsys.get_session()
        req.user = model.User(name='bob')

        self.obj.status = UpdateStatus.testing
        self.obj.request = None

        # Pretend it's been in testing for a week
        self.obj.comment(
            self.db, 'This update has been pushed to testing.', author='bodhi')
        self.obj.date_testing = self.obj.comments[-1].timestamp - timedelta(days=7)
        assert self.obj.days_in_testing == 7
        assert self.obj.meets_testing_requirements
        expected_message = update_schemas.UpdateRequestStableV1.from_dict(
            {'update': self.obj, 'agent': req.user.name})

        self.db.info['messages'] = []
        with mock_sends(expected_message):
            self.obj.set_request(self.db, UpdateRequest.stable, req.user.name)
            # set_request alters the update a bit, so we need to adjust the expected message to
            # reflect those changes so the mock_sends() check will pass.
            expected_message.body['update']['status'] = 'testing'
            expected_message.body['update']['request'] = 'stable'
            expected_message.body['update']['comments'] = self.obj.__json__()['comments']
            self.db.commit()

        assert self.obj.request == UpdateRequest.stable
        assert len(req.errors) == 0

    def test_set_request_stable_when_release_is_frozen(self):
        """Ensure that Bodhi will infom user about push to stable delay when release is frozen."""
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
        assert self.obj.days_in_testing == 7
        assert self.obj.meets_testing_requirements

        # Make release frozen
        self.obj.release.state = ReleaseState.frozen

        expected_message = update_schemas.UpdateRequestStableV1.from_dict(
            {'update': self.obj, 'agent': req.user.name})

        self.db.info['messages'] = []
        with mock_sends(expected_message):
            self.obj.set_request(self.db, UpdateRequest.stable, req.user.name)
            # set_request alters the update a bit, so we need to adjust the expected message to
            # reflect those changes so the mock_sends() check will pass.
            expected_message.body['update']['status'] = 'testing'
            expected_message.body['update']['request'] = 'stable'
            expected_message.body['update']['comments'] = self.obj.__json__()['comments']
            self.db.commit()
        assert self.obj.request == UpdateRequest.stable
        assert len(req.errors) == 0

        # Check for information about frozen release in comment
        expected_info = ("There is an ongoing freeze; "
                         "this will be pushed to stable after the freeze is over.")
        assert expected_info in self.obj.comments[-1].text

    def test_set_request_stable_epel_requirements_not_met(self):
        """Test set_request() for EPEL update requesting stable that doesn't meet requirements."""
        req = DummyRequest()
        req.errors = cornice.Errors()
        req.koji = buildsys.get_session()
        req.user = model.User(name='bob')
        self.obj.release.id_prefix = 'FEDORA-EPEL'
        self.obj.status = UpdateStatus.testing
        self.obj.request = None

        with pytest.raises(BodhiException) as exc:
            with mock_sends():
                self.obj.set_request(self.db, UpdateRequest.stable, req.user.name)
        assert str(exc.value) == config['not_yet_tested_epel_msg']

        assert self.obj.request is None

    def test_set_request_stable_epel_requirements_not_met_not_testing(self):
        """Test set_request() for EPEL update not meeting requirements that isn't testing."""
        req = DummyRequest()
        req.errors = cornice.Errors()
        req.koji = buildsys.get_session()
        req.user = model.User(name='bob')
        self.obj.release.id_prefix = 'FEDORA-EPEL'
        self.obj.status = UpdateStatus.pending
        self.obj.request = None
        expected_message = update_schemas.UpdateRequestTestingV1.from_dict(
            {'update': self.obj, 'agent': req.user.name})

        with mock_sends(expected_message):
            self.obj.set_request(self.db, UpdateRequest.stable, req.user.name)
            # set_request alters the update a bit, so we need to adjust the expected message to
            # reflect those changes so the mock_sends() check will pass.
            expected_message.body['update'] = self.obj.__json__()
            self.db.commit()

        # The request should have gotten switched to testing.
        assert self.obj.request == UpdateRequest.testing

    def test_set_request_stable_for_critpath_update_when_test_gating_enabled(self):
        """
        Ensure that we can't submit a critpath update for stable if it hasn't passed the
        test gating and return the error message as expected.
        """
        config["test_gating.required"] = True
        req = DummyRequest()
        req.errors = cornice.Errors()
        req.koji = buildsys.get_session()
        req.user = model.User(name='bob')

        self.obj.status = UpdateStatus.testing
        self.obj.request = None
        self.obj.critpath = True
        self.obj.test_gating_status = TestGatingStatus.failed

        with pytest.raises(BodhiException) as exc:
            self.obj.set_request(self.db, UpdateRequest.stable, req.user.name)

        expected_msg = (
            'This critical path update has not yet been approved for pushing to the '
            'stable repository.  It must first reach a karma of %s, consisting of %s '
            'positive karma from proventesters, along with %d additional karma from '
            'the community. Or, it must spend %s days in testing without any negative '
            'feedback')
        expected_msg = expected_msg % (
            config.get('critpath.min_karma'),
            config.get('critpath.num_admin_approvals'),
            (config.get('critpath.min_karma') - config.get('critpath.num_admin_approvals')),
            config.get('critpath.stable_after_days_without_negative_karma'))
        expected_msg += ' Additionally, it must pass automated tests.'
        assert str(exc.value) == expected_msg

    def test_set_request_string_action(self):
        """Ensure that the action can be passed as a str."""
        req = DummyRequest(user=DummyUser())
        req.errors = cornice.Errors()
        req.koji = buildsys.get_session()
        assert self.obj.status == UpdateStatus.pending
        self.obj.stable_karma = 1
        with mock_sends(Message):
            self.obj.comment(self.db, 'works', karma=1, author='bowlofeggs')

        self.obj.set_request(self.db, 'stable', req.user.name)

        assert self.obj.request == UpdateRequest.stable
        assert self.obj.status == UpdateStatus.pending

    def test_has_stable_comment_at_7_days_after_bodhi_comment(self):
        """
        Ensure a correct True return value from Update.has_stable_comment() after an update
        has been in testing for 7 days and after bodhi has commented about it.
        """
        self.obj.status = UpdateStatus.testing
        # Pretend it's been in testing for a week
        self.obj.comment(
            self.db, 'This update has been pushed to testing.', author='bodhi')
        self.obj.date_testing = self.obj.comments[-1].timestamp - timedelta(days=7)
        assert self.obj.days_in_testing == 7
        # The update should be eligible to receive the testing_approval_msg now.
        assert self.obj.meets_testing_requirements
        # Add the testing_approval_message
        text = str(config.get('testing_approval_msg'))
        self.obj.comment(self.db, text, author='bodhi')

        # met_testing_requirement() should return True since Bodhi has commented on the Update to
        # say that it can now be pushed to stable.
        assert self.obj.has_stable_comment

    def test_has_stable_comment_at_7_days_before_bodhi_comment(self):
        """
        Ensure a correct False return value from Update.has_stable_comment() after an update
        has been in testing for 7 days but before bodhi has commented about it.
        """
        self.obj.status = UpdateStatus.testing
        # Pretend it's been in testing for a week
        self.obj.comment(
            self.db, 'This update has been pushed to testing.', author='bodhi')
        self.obj.date_testing = self.obj.comments[-1].timestamp - timedelta(days=7)
        assert self.obj.days_in_testing == 7
        # The update should be eligible to receive the testing_approval_msg now.
        assert self.obj.meets_testing_requirements

        # Since bodhi hasn't added the testing_approval_message yet, this should be False.
        assert not self.obj.has_stable_comment

    def test_has_stable_comment_with_karma_after_bodhi_comment(self):
        """
        Ensure a correct True return value from Update.has_stable_comment() after a
        non-autokarma update has reached the karma requirement and after bodhi has commented about
        it.
        """
        self.obj.autokarma = False
        self.obj.status = UpdateStatus.testing
        # Pretend it's been in testing for a day
        self.obj.comment(
            self.db, 'This update has been pushed to testing.', author='bodhi')
        self.obj.date_testing = self.obj.comments[-1].timestamp - timedelta(days=1)
        assert self.obj.days_in_testing == 1
        # Now let's add some karma to get it to the required threshold
        self.obj.comment(self.db, 'testing', author='hunter1', karma=1)
        self.obj.comment(self.db, 'testing', author='hunter2', karma=1)
        self.obj.comment(self.db, 'testing', author='hunter3', karma=1)
        # Add the testing_approval_message
        text = config.get('testing_approval_msg')
        self.obj.comment(self.db, text, author='bodhi')

        # met_testing_requirement() should return True since Bodhi has commented on the Update to
        # say that it can now be pushed to stable.
        assert self.obj.has_stable_comment

    def test_has_stable_comment_with_karma_before_bodhi_comment(self):
        """
        Ensure a correct False return value from Update.has_stable_comment() after a
        non-autokarma update has reached the karma requirement but before bodhi has commented about
        it.
        """
        self.obj.autokarma = False
        self.obj.status = UpdateStatus.testing
        # Pretend it's been in testing for a day
        self.obj.comment(
            self.db, 'This update has been pushed to testing.', author='bodhi')
        self.obj.date_testing = self.obj.comments[-1].timestamp - timedelta(days=1)
        assert self.obj.days_in_testing == 1
        # Now let's add some karma to get it to the required threshold
        self.obj.comment(self.db, 'testing', author='hunter1', karma=1)
        self.obj.comment(self.db, 'testing', author='hunter2', karma=1)
        self.obj.comment(self.db, 'testing', author='hunter3', karma=1)

        # met_testing_requirement() should return False since Bodhi has not yet commented on the
        # Update to say that it can now be pushed to stable.
        assert not self.obj.has_stable_comment

    def test_set_request_obsolete(self):
        req = DummyRequest(user=DummyUser())
        req.errors = cornice.Errors()
        assert self.obj.status == UpdateStatus.pending

        with mock_sends(update_schemas.UpdateRequestObsoleteV1):
            self.obj.set_request(self.db, UpdateRequest.obsolete, req.user.name)
            self.db.commit()

        assert self.obj.status == UpdateStatus.obsolete
        assert len(req.errors) == 0

    def test_status_comment(self):
        self.obj.status = UpdateStatus.testing
        self.obj.status_comment(self.db)
        assert len(self.obj.comments) == 1
        assert self.obj.comments[0].user.name == 'bodhi'
        assert self.obj.comments[0].text == 'This update has been pushed to testing.'
        self.obj.status = UpdateStatus.stable
        self.obj.status_comment(self.db)
        assert len(self.obj.comments) == 2
        assert self.obj.comments[1].user.name == 'bodhi'
        assert self.obj.comments[1].text == 'This update has been pushed to stable.'
        assert str(self.obj.comments[1]).endswith('This update has been pushed to stable.')

    def test_status_comment_obsolete(self):
        """Test status_comment() with an obsolete update."""
        self.obj.status = UpdateStatus.obsolete

        self.obj.status_comment(self.db)

        assert [c.text for c in self.obj.comments] == ['This update has been obsoleted.']

    @mock.patch.dict(config, {'critpath.num_admin_approvals': 2})
    def test_comment_critpath_unapproved(self):
        """Test a comment reaching karma threshold when update is not critpath approved."""
        self.obj.autokarma = True
        self.obj.critpath = True
        self.obj.stable_karma = 1
        self.obj.status = UpdateStatus.testing

        # This should cause a caveat.
        comments, caveats = self.obj.comment(self.db, 'testing 3', author='me3', karma=1)

        assert caveats == (
            [{'name': 'karma',
              'description': ('This critical path update has not yet been approved for pushing to '
                              'the stable repository.  It must first reach a karma of 2, '
                              'consisting of 2 positive karma from proventesters, along with 0 '
                              'additional karma from the community. Or, it must spend 14 days in '
                              'testing without any negative feedback')}])

    def test_comment_emails_other_commenters(self):
        """comment() should send e-mails to the other maintainers."""
        bowlofeggs = model.User(name='bowlofeggs', email='bowlofeggs@fp.o')
        self.db.add(bowlofeggs)
        self.db.flush()
        self.obj.comment(self.db, 'im a commenter', author='bowlofeggs')

        with mock.patch('bodhi.server.mail.smtplib.SMTP') as SMTP:
            with mock.patch.dict('bodhi.server.models.config',
                                 {'bodhi_email': 'bodhi@fp.o', 'smtp_server': 'smtp.fp.o'}):
                self.obj.comment(self.db, 'Here is a cool e-mail for you.', author='someoneelse')

        bodies = [c[1][2].decode('utf-8') for c in SMTP.return_value.sendmail.mock_calls]
        assert 'lmacken' in bodies[0]
        # In Python 2 this address is in the middle e-mail and in Python 3 it's in the last e-mail
        assert 'bowlofeggs@fp.o' in '\n'.join(bodies)
        assert 'someoneelse' in bodies[1]
        assert all(['Here is a cool e-mail for you.' in b for b in bodies])

    def test_comment_no_author(self):
        """A comment with no author should raise a ValueError."""
        with pytest.raises(ValueError) as exc:
            self.obj.comment(self.db, 'Broke.', -1)
        assert str(exc.value) == 'You must provide a comment author'

    def test_comment_empty(self):
        """A comment with no text or feedback should raise a ValueError."""
        with pytest.raises(ValueError) as exc:
            self.obj.comment(self.db, '', author='bowlofeggs')
        assert str(exc.value) == 'You must provide either some text or feedback'

    def test_get_url(self):
        assert self.obj.get_url() == f'updates/{self.obj.alias}'

    def test_bug(self):
        bug = self.obj.bugs[0]
        assert bug.url == 'https://bugzilla.redhat.com/show_bug.cgi?id=1'
        with pytest.raises(ValueError) as exc:
            bug.testing(self.obj)
        assert 'is not in Stable or Testing status' in str(exc.value)
        self.obj.status = UpdateStatus.testing
        bug.testing(self.obj)
        bug.add_comment(self.obj)
        bug.add_comment(self.obj, comment='testing')
        bug.close_bug(self.obj)
        self.obj.status = UpdateStatus.stable
        bug.add_comment(self.obj)

    def test_expand_messages(self):
        """Ensure all messages can be expanded properly"""
        self.obj.comment(self.db, 'test', 0, 'guest')
        for value in mail.MESSAGES.values():
            value['body'] % value['fields']('guest', self.obj)

    @mock.patch('bodhi.server.mail.get_template')
    def test_send_update_notice_message_template_fedora(self, get_template):
        """Ensure update message template reflects fedora when it should"""
        update = self.obj
        update.status = UpdateStatus.stable

        update.send_update_notice()

        get_template.assert_called_with(update, 'fedora_errata_template')

    @mock.patch('bodhi.server.mail.get_template')
    def test_send_update_notice_message_template_el7(self, get_template):
        """Ensure update message template reflects EL <= 7 when it should"""
        update = self.get_update(name='TurboGears-3.1-1.el7')
        release = model.Release(
            name='EL-7', long_name='Fedora EPEL 7', id_prefix='FEDORA-EPEL',
            dist_tag='dist-7E-epel', stable_tag='dist-7E-epel',
            testing_tag='dist-7E-epel-testing', candidate_tag='dist-7E-epel-testing-candidate',
            pending_testing_tag='dist-7E-epel-testing-pending',
            pending_stable_tag='dist-7E-epel-pending', override_tag='dist-7E-epel-override',
            branch='el7', version='7', mail_template='fedora_epel_legacy_errata_template')
        update.release = release
        update.status = UpdateStatus.stable

        update.send_update_notice()

        get_template.assert_called_with(update, 'fedora_epel_legacy_errata_template')

    @mock.patch('bodhi.server.mail.get_template')
    def test_send_update_notice_message_template_el8(self, get_template):
        """Ensure update message template reflects EL >= 8 when it should"""
        update = self.get_update(name='TurboGears-4.1-1.el8')
        release = model.Release(
            name='EL-8', long_name='Fedora EPEL 8', id_prefix='FEDORA-EPEL',
            dist_tag='dist-8E-epel', stable_tag='dist-8E-epel',
            testing_tag='dist-8E-epel-testing', candidate_tag='dist-8E-epel-testing-candidate',
            pending_testing_tag='dist-8E-epel-testing-pending',
            pending_stable_tag='dist-8E-epel-pending', override_tag='dist-8E-epel-override',
            branch='el8', version='8', mail_template='fedora_epel_errata_template')
        update.release = release
        update.status = UpdateStatus.stable

        update.send_update_notice()

        get_template.assert_called_with(update, 'fedora_epel_errata_template')

    @mock.patch('bodhi.server.models.log.error')
    @mock.patch('bodhi.server.models.mail.send_mail')
    @mock.patch.dict('bodhi.server.models.config', {'bodhi_email': None})
    def test_send_update_notice_no_email_configured(self, send_mail, error):
        """Test send_update_notice() when no e-mail address is configured."""
        self.obj.send_update_notice()

        error.assert_called_once_with(
            'bodhi_email not defined in configuration!  Unable to send update notice')
        assert send_mail.call_count == 0

    @mock.patch('bodhi.server.models.log.error')
    @mock.patch('bodhi.server.models.mail.send_mail')
    @mock.patch.dict('bodhi.server.models.config',
                     {'bodhi_email': 'bodhi@fp.o', 'fedora_test_announce_list': None})
    def test_send_update_notice_no_mailinglist_configured(self, send_mail, error):
        """Test send_update_notice() when no e-mail address is configured."""
        self.obj.send_update_notice()

        assert error.mock_calls == (
            [mock.call('Cannot find mailing list address for update notice'),
             mock.call('release_name = %r', 'fedora')])
        assert send_mail.call_count == 0

    @mock.patch('bodhi.server.mail.smtplib.SMTP')
    @mock.patch.dict('bodhi.server.models.config',
                     {'bodhi_email': 'bodhi@fp.o', 'smtp_server': 'smtp.fp.o'})
    def test_send_update_notice_status_testing(self, SMTP):
        """Assert the test_announce_list setting is used for the mailing list of testing updates."""
        self.obj.status = UpdateStatus.testing
        subject, body = mail.get_template(self.obj, self.obj.release.mail_template)[0]
        expected_message = errata_schemas.ErrataPublishV1.from_dict({
            'subject': subject, 'body': body, 'update': self.obj})

        self.db.info['messages'] = []
        with mock_sends(expected_message):
            self.obj.send_update_notice()
            self.db.commit()

        release_name = self.obj.release.id_prefix.lower().replace('-', '_')
        msg = ('From: {}\r\nTo: {}\r\nX-Bodhi: {}'
               '\r\nSubject: [SECURITY] Fedora 11 Test Update: {}\r\n\r\n{}')
        msg = msg.format(
            config['bodhi_email'], config['{}_test_announce_list'.format(release_name)],
            config['default_email_domain'], self.obj.builds[0].nvr, body)
        SMTP.return_value.sendmail.assert_called_once_with(
            config['bodhi_email'],
            [config['{}_test_announce_list'.format(release_name)]],
            msg.encode('utf-8'))

    def test_check_requirements_empty(self):
        '''Empty requirements are OK'''
        update = self.obj
        settings = {'resultsdb_api_url': ''}

        for req in ['', None]:
            update.requirements = req

            result, reason = update.check_requirements(None, settings)

            assert result
            assert reason == "No checks required."

    @mock.patch('bodhi.server.models.Update.last_modified',
                new_callable=mock.PropertyMock)
    def test_check_requirements_no_last_modified(self, mock_last_modified):
        '''Missing last_modified should fail the check'''
        update = self.obj
        mock_last_modified.return_value = None
        update.requirements = 'rpmlint abicheck'
        settings = {'resultsdb_api_url': ''}

        result, reason = update.check_requirements(None, settings)

        assert not result
        assert "Failed to determine last_modified" in reason

    @mock.patch('bodhi.server.util.taskotron_results')
    def test_check_requirements_query_error(self, mock_taskotron_results):
        '''Error during retrieving results should fail'''
        update = self.obj
        update.requirements = 'rpmlint abicheck'
        settings = {'resultsdb_api_url': ''}
        mock_taskotron_results.side_effect = Exception('Query failed')

        result, reason = update.check_requirements(None, settings)

        assert not result
        assert "Failed retrieving requirements results" in reason

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

        assert not result
        assert reason == "No result found for required testcase abicheck"

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

        assert not result
        assert reason == "Required task rpmlint returned FAILED"

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

        assert result
        assert reason == "All checks pass."

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

        assert not result
        assert "Failed retrieving requirements results:" in reason
        assert "Error retrieving data from Koji for" in reason

    def test_check_requirements_test_gating_status_failed(self):
        """check_requirements() should return False when test_gating_status is failed."""
        self.obj.requirements = ''
        self.obj.test_gating_status = model.TestGatingStatus.failed

        with mock.patch.dict(config, {'test_gating.required': True}):
            assert self.obj.check_requirements(self.db, config) == (
                (False, 'Required tests did not pass on this update'))

    def test_check_requirements_test_gating_status_passed(self):
        """check_requirements() should return True when test_gating_status is passed."""
        self.obj.requirements = ''
        self.obj.test_gating_status = model.TestGatingStatus.passed

        with mock.patch.dict(config, {'test_gating.required': True}):
            assert self.obj.check_requirements(self.db, config) == (True, 'No checks required.')

    def test_num_admin_approvals_after_karma_reset(self):
        """Make sure number of admin approvals is counted correctly for the build."""
        update = model.Update.query.first()

        # Approval from admin 'bodhiadmin' {config.admin_groups}
        user_group = [model.Group(name='bodhiadmin')]
        user = model.User(name='bodhiadmin', groups=user_group)
        comment = model.Comment(text='Test comment', karma=1, user=user)
        self.db.add(comment)
        update.comments.append(comment)

        assert update.num_admin_approvals == 1

        # This is a "karma reset event", so the above comments should not be counted in the karma.
        user = model.User(name='bodhi')
        comment = model.Comment(text="New build", karma=0, user=user)
        self.db.add(comment)
        update.comments.append(comment)

        assert update.num_admin_approvals == 0

    def test_validate_release_failure(self):
        """Test the validate_release() method for the failure case."""
        user = self.db.query(model.User).first()

        release = model.Release(
            name='F18M', long_name='Fedora 18 Modular',
            id_prefix='FEDORA-MODULE', version='18',
            dist_tag='f18m', stable_tag='f18-modular-updates',
            testing_tag='f18-modular-updates-testing',
            candidate_tag='f18-modular-updates-candidate',
            pending_signing_tag='f18-modular-updates-testing-signing',
            pending_testing_tag='f18-modular-updates-testing-pending',
            pending_stable_tag='f18-modular-updates-pending',
            override_tag='f18-modular-override',
            state=ReleaseState.current,
            branch='f18m')
        self.db.add(release)
        package = model.Package(name='testmodule',
                                type=model.ContentType.module)
        self.db.add(package)
        build = model.ModuleBuild(nvr='testmodule-master-2.fc18',
                                  release=release, signed=True,
                                  package=package)
        self.db.add(build)
        update = model.Update(
            release=release,
            builds=[build], user=user,
            status=UpdateStatus.testing,
            request=UpdateRequest.stable,
            type=UpdateType.enhancement,
            notes='Useful details!',
            stable_karma=3,
            unstable_karma=-3)
        self.db.add(update)
        self.db.flush()

        # We should not be allowed to add our RPM Update to the Module release.
        with pytest.raises(ValueError) as exc:
            self.obj.release = release
        assert str(exc.value) == 'A release must contain updates of the same type.'

    def test_validate_release_none(self):
        """Test validate_release() with the release set to None."""
        # This should not raise an Exception.
        self.obj.release = None

        assert self.obj.release is None

    def test_validate_release_success(self):
        """Test validate_release() for the success case."""
        user = self.db.query(model.User).first()

        release = model.Release(
            name='F18M', long_name='Fedora 18 Modular',
            id_prefix='FEDORA-MODULE', version='18',
            dist_tag='f18m', stable_tag='f18-modular-updates',
            testing_tag='f18-modular-updates-testing',
            candidate_tag='f18-modular-updates-candidate',
            pending_signing_tag='f18-modular-updates-testing-signing',
            pending_testing_tag='f18-modular-updates-testing-pending',
            pending_stable_tag='f18-modular-updates-pending',
            override_tag='f18-modular-override',
            state=ReleaseState.current,
            branch='f18m')
        self.db.add(release)
        package = model.Package(name='testmodule',
                                type=model.ContentType.module)
        self.db.add(package)
        build1 = model.ModuleBuild(nvr='testmodule-master-1.fc18',
                                   release=release, signed=True,
                                   package=package)
        self.db.add(build1)
        build2 = model.ModuleBuild(nvr='testmodule-master-2.fc18',
                                   release=release, signed=True,
                                   package=package)
        self.db.add(build2)
        update1 = model.Update(
            builds=[build1], user=user,
            status=UpdateStatus.testing,
            request=UpdateRequest.stable,
            notes='Useful details!',
            release=release)

        self.db.add(update1)

        # This should not raise an Exception.
        update2 = model.Update(
            builds=[build2], user=user,
            status=UpdateStatus.testing,
            request=UpdateRequest.stable,
            notes='Useful details!',
            release=release)

        self.db.add(update2)

        assert update2.release == release

    def test_cannot_waive_test_results_of_an_update_when_test_gating_is_off(self):
        update = self.obj
        with pytest.raises(BodhiException) as exc:
            update.waive_test_results('foo')
        assert str(exc.value) == "Test gating is not enabled"

    def test_cannot_waive_test_results_of_an_update_which_passes_gating(self):
        config["test_gating.required"] = True
        update = self.obj
        with pytest.raises(BodhiException) as exc:
            update.waive_test_results('foo')
        assert str(exc.value) == "Can't waive test results on an update that passes test gating"

    def test_cannot_waive_test_results_of_an_update_which_is_locked(self):
        config["test_gating.required"] = True
        update = self.obj
        update.locked = True
        with pytest.raises(LockedUpdateException) as exc:
            update.waive_test_results('foo')
        assert str(exc.value) == "Can't waive test results on a locked update"

    @mock.patch('bodhi.server.util.greenwave_api_post')
    @mock.patch('bodhi.server.util.http_session.post')
    def test_can_waive_multiple_test_results_of_an_update(self, post, greenwave_api_post):
        """Multiple failed tests getting waived should cause multiple calls to waiverdb."""
        self.obj.status = UpdateStatus.testing
        self.obj.test_gating_status = TestGatingStatus.failed
        greenwave_api_post.return_value = {
            "policies_satisfied": False,
            "summary": "3 of 15 required tests failed",
            "applicable_policies": ["1"],
            "unsatisfied_requirements": [
                {'item': {"item": "bodhi-3.6.0-1.fc28", "type": "koji_build"}, 'result_id': "123",
                 'testcase': 'dist.depcheck', 'type': 'test-result-failed'},
                {'item': {"item": "bodhi-3.6.0-1.fc28", "type": "koji_build"}, 'result_id': "124",
                 'testcase': 'dist.rpmdeplint', 'type': 'test-result-failed'},
                {'item': {"item": "bodhi-3.6.0-1.fc28", "type": "koji_build"}, 'result_id': "125",
                 'testcase': 'dist.someothertest', 'type': 'test-result-failed'}]}
        post.return_value.status_code = 200

        config.update({
            'test_gating.required': True,
            'waiverdb.access_token': 'abc',
        })
        self.obj.waive_test_results('foo', 'this is not true!')

        # Check for the comment
        expected_comment = "This update's test gating status has been changed to 'waiting'."
        assert self.obj.comments[-1].text == expected_comment

        expected_calls = []
        for test in ('dist.depcheck', 'dist.rpmdeplint', 'dist.someothertest'):
            data = {
                "username": "foo", "comment": "this is not true!", "waived": True,
                "product_version": "{}".format(self.obj.product_version),
                "testcase": "{}".format(test),
                "subject": {"item": "bodhi-3.6.0-1.fc28", "type": "koji_build"}}
            expected_calls.append(mock.call(
                '{}/waivers/'.format(config.get('waiverdb_api_url')),
                data=json.dumps(data),
                headers={'Content-Type': 'application/json', 'Authorization': 'Bearer abc'},
                timeout=60))
            expected_calls.append(mock.call().json())
        for i, v in enumerate(expected_calls):
            # The even numbered calls have a JSON serialized data string in them, and the order of
            # the keys is not guaranteed to be the same by Python. For these, we will just make sure
            # that the interpreted JSON is equal rather than verifying that the strings are equal.
            if not i % 2:
                assert post.mock_calls[i][1] == expected_calls[i][1]
                assert post.mock_calls[i][2].keys() == v[2].keys()
                for k in v[2].keys():
                    if k == 'data':
                        assert json.loads(post.mock_calls[i][2]['data']) == (
                            json.loads(v[2]['data']))
                    else:
                        assert post.mock_calls[i][2][k] == expected_calls[i][2][k]
            else:
                assert post.mock_calls[i] == v

    @mock.patch('bodhi.server.util.greenwave_api_post')
    @mock.patch('bodhi.server.util.waiverdb_api_post')
    def test_can_waive_test_results_of_an_update(self, mock_waiverdb, mock_greenwave):
        update = self.obj
        update.status = UpdateStatus.testing
        update.test_gating_status = TestGatingStatus.failed
        decision = {
            "policies_satisfied": False,
            "summary": "1 of 15 required tests failed",
            "applicable_policies": ["1"],
            "unsatisfied_requirements": [
                {
                    'item': {"item": "%s" % update.builds[0].nvr, "type": "koji_build"},
                    'result_id': "123",
                    'testcase': 'dist.depcheck',
                    'type': 'test-result-failed'
                }
            ]
        }
        mock_greenwave.return_value = decision
        config.update({
            'test_gating.required': True,
            'waiverdb.access_token': 'abc',
        })
        update.waive_test_results('foo', 'this is not true!')
        wdata = {
            'subject': {"item": "%s" % update.builds[0].nvr, "type": "koji_build"},
            'testcase': 'dist.depcheck',
            'product_version': update.product_version,
            'waived': True,
            'username': 'foo',
            'comment': 'this is not true!'
        }
        mock_waiverdb.assert_called_once_with(
            '{}/waivers/'.format(config.get('waiverdb_api_url')), wdata)

        # Check for the comment
        expected_comment = "This update's test gating status has been changed to 'waiting'."
        assert update.comments[-1].text == expected_comment

    @mock.patch('bodhi.server.models.mail')
    def test_comment_on_test_gating_status_change(self, mail):
        """Assert that Bodhi will leave comment only when test_gating_status changes."""
        # Let's make sure that update has no comments.
        assert len(self.obj.comments) == 0

        self.obj.test_gating_status = TestGatingStatus.waiting

        # Check for the comment about test_gating_status change
        expected_comment = "This update's test gating status has been changed to 'waiting'."
        assert self.obj.comments[0].text == expected_comment
        assert len(self.obj.comments) == 1

        # Let's set test_gating_status to 'waiting' once again.
        self.obj.test_gating_status = TestGatingStatus.waiting

        # We should have still only one comment about test_gating_status change.
        assert len(self.obj.comments) == 1

        # Check that no email were sent:
        assert mail.send.call_count == 0

    @mock.patch('bodhi.server.models.mail')
    def test_comment_on_test_gating_status_change_email(self, mail):
        """Assert that Bodhi will leave comment only when test_gating_status changes."""
        # Let's make sure that update has no comments.
        assert len(self.obj.comments) == 0

        # Check that no email were sent:
        assert mail.send.call_count == 0

        self.obj.test_gating_status = TestGatingStatus.failed

        # Check that one email was sent:
        assert mail.send.call_count == 1

        # Check for the comment about test_gating_status change
        expected_comment = "This update's test gating status has been changed to 'failed'."
        assert self.obj.comments[0].text == expected_comment
        assert len(self.obj.comments) == 1

        # Let's set test_gating_status to 'waiting' once again.
        self.obj.test_gating_status = TestGatingStatus.waiting

        # Check that still only one email was sent:
        assert mail.send.call_count == 1

        # We should have two comments, one for each test_gating_status change
        assert len(self.obj.comments) == 2

    def test_set_status_testing(self):
        """Test that setting an update's status to testing sends a message."""
        self.db.info['messages'] = []
        with mock_sends(update_schemas.UpdateReadyForTestingV2):
            self.obj.status = UpdateStatus.testing
            msg = self.db.info['messages'][0]
            self.db.commit()
        assert msg.body["artifact"]["builds"][0]["component"] == "TurboGears"
        assert msg.body["artifact"]["id"].startswith("FEDORA-")
        assert msg.body["artifact"]["type"] == "koji-build-group"
        assert msg.packages == ['TurboGears']

    def test_create_with_status_testing(self):
        """Test that creating an update with the status set to testing sends a message."""
        self.db.info['messages'] = []
        with mock_sends(update_schemas.UpdateReadyForTestingV2):
            self.get_update(name="TurboGears-1.0.8-4.fc11", override_args={
                "status": UpdateStatus.testing,
                "user": self.db.query(model.User).filter_by(name='lmacken').one()
            })
            assert len(self.db.info['messages']) == 1
            msg = self.db.info['messages'][0]
            self.db.commit()
        assert msg.body["artifact"]["builds"][0]["component"] == "TurboGears"
        assert msg.body["artifact"]["id"].startswith("FEDORA-")
        assert msg.body["artifact"]["type"] == "koji-build-group"
        assert msg.packages == ['TurboGears']


class TestUser(ModelTest):
    klass = model.User
    attrs = dict(name='Bob Vila')

    def do_get_dependencies(self):
        group = model.Group(name='proventesters')
        return dict(groups=[group])


class TestGroup(ModelTest):
    klass = model.Group
    attrs = dict(name='proventesters')

    def do_get_dependencies(self):
        user = model.User(name='bob')
        return dict(users=[user])


class TestBuildrootOverride(ModelTest):
    klass = model.BuildrootOverride
    attrs = dict(notes='This is needed to build foobar',
                 expiration_date=datetime.utcnow())

    def do_get_dependencies(self):
        return dict(
            build=model.RpmBuild(
                nvr='TurboGears-1.0.8-3.fc11', package=model.RpmPackage(**TestRpmPackage.attrs),
                release=model.Release(**TestRelease.attrs)),
            submitter=model.User(name='lmacken'))

    @mock.patch('bodhi.server.models.buildsys.get_session')
    @mock.patch('bodhi.server.models.log.error')
    def test_expire_exception(self, error, get_session):
        """Exceptions raised by koji untag_build() should be caught and logged by expire()."""
        get_session.return_value.untagBuild.side_effect = IOError('oh no!')
        bro = model.BuildrootOverride.query.first()

        bro.expire()

        get_session.return_value.untagBuild.assert_called_once_with(bro.build.release.override_tag,
                                                                    bro.build.nvr, strict=True)
        error.assert_called_once_with('Unable to untag override {}: {}'.format(bro.nvr, 'oh no!'))

    def test_new_already_exists(self):
        """new() should put an error on the request if the BRO already exists."""
        req = DummyRequest(user=DummyUser())
        req.db = self.db
        req.errors = cornice.Errors()
        bro = model.BuildrootOverride.query.first()

        resp = model.BuildrootOverride.new(req, build=bro.build)

        assert resp is None
        assert req.errors == (
            [{'location': 'body', 'name': 'nvr',
              'description': '{} is already in a override'.format(bro.build.nvr)}])
