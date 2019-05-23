# Copyright © 2019 Red Hat, Inc.
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
"""These are tests for the bodhi.server.consumers.automatic_updates module."""

from copy import deepcopy
from unittest import mock
import logging

from fedora_messaging.api import Message
from fedora_messaging.testing import mock_sends
import pytest

from bodhi.messages.schemas.update import UpdateMessage
from bodhi.server.consumers.automatic_updates import AutomaticUpdateHandler
from bodhi.server.exceptions import BodhiException
from bodhi.server.models import Build, Release, Update, UpdateType, User
from bodhi.tests.server import base


class TestAutomaticUpdateHandler(base.BasePyTestCase):
    """Test the automatic update handler."""

    def setup_method(self, method):
        """Set up environment for each test."""
        super().setup_method(method)

        self.release = self.db.query(Release).filter_by(name='F17').first()
        if self.release:
            self.release.create_automatic_updates = True
            self.db.flush()
        else:
            self.release = self.create_release('17', create_automatic_updates=True)

        body = {
            'build_id': 442562,
            'name': 'colord',
            'tag_id': 214,
            'instance': 's390',
            'tag': 'f17-updates-candidate',
            'user': 'sharkcz',
            'version': '1.3.4',
            'owner': 'sharkcz',
            'release': '1.fc26',
        }

        self.sample_message = Message(topic='', body=body)
        self.sample_nvr = f"{body['name']}-{body['version']}-{body['release']}"

        self.db_factory = base.TransactionalSessionMaker(self.Session)
        self.handler = AutomaticUpdateHandler(self.db_factory)

    # Test the main code path.
    def test_consume(self):
        """Assert that messages about tagged builds create an update."""
        # process the message
        with mock_sends(UpdateMessage):
            self.handler(self.sample_message)

        # check if the update exists...
        update = self.db.query(Update).filter(
            Update.builds.any(Build.nvr == self.sample_nvr)
        ).first()

        # ...and some of its properties
        assert update is not None
        assert update.type == UpdateType.unspecified

        expected_username = base.buildsys.DevBuildsys._build_data['owner_name']
        assert update.user and update.user.name == expected_username

    # The following tests cover lesser-travelled code paths.

    @mock.patch('bodhi.server.consumers.automatic_updates.transactional_session_maker')
    def test___init___without_db_factory(self, transactional_session_maker):
        """__init__() should create db_factory if missing."""
        handler = AutomaticUpdateHandler()

        assert handler.db_factory is transactional_session_maker.return_value
        transactional_session_maker.assert_called_once_with()

    # Test robustness: malformed messages, unknown koji builds, incomplete
    # buildinfo, release missing from the DB

    def test_missing_mandatory_elems(self):
        """Test tag message without mandatory elements."""
        msg = deepcopy(self.sample_message)
        for elem in ('build_id', 'name', 'version', 'release'):
            del msg.body[elem]
        with pytest.raises(BodhiException):
            self.handler(msg)

    def test_unknown_koji_build(self):
        """Test tag message about unknown koji build."""
        msg = deepcopy(self.sample_message)
        msg.body['release'] += '.youdontknowme'
        with pytest.raises(BodhiException):
            self.handler(msg)

    def test_incomplete_koji_buildinfo_nvr(self):
        """Test koji returning incomplete buildinfo: no nvr."""
        msg = deepcopy(self.sample_message)
        msg.body['release'] += '.testmissingnvr'
        with pytest.raises(BodhiException):
            self.handler(msg)

    def test_incomplete_koji_buildinfo_owner(self, caplog):
        """Test koji returning incomplete buildinfo: no owner."""
        caplog.set_level(logging.DEBUG)

        msg = deepcopy(self.sample_message)
        msg.body['release'] += '.noowner'

        with pytest.raises(BodhiException):
            self.handler(msg)

    def test_missing_user(self, caplog):
        """Test Koji build user missing from DB."""
        caplog.set_level(logging.DEBUG)

        expected_username = base.buildsys.DevBuildsys._build_data['owner_name']

        # ensure user with expected name doesn't exist
        self.db.query(User).filter_by(name=expected_username).delete()
        self.db.flush()

        with mock_sends(UpdateMessage):
            self.handler(self.sample_message)

        assert(f"Creating bodhi user for '{expected_username}'."
               in caplog.messages)

    def test_existing_user(self, caplog):
        """Test Koji build user existing in DB."""
        caplog.set_level(logging.DEBUG)

        expected_username = base.buildsys.DevBuildsys._build_data['owner_name']

        # ensure user with expected name exists
        user = self.db.query(User).filter_by(name=expected_username).first()
        if not user:
            user = User(name=expected_username)
            self.db.add(user)
        self.db.flush()

        with mock_sends(UpdateMessage):
            self.handler(self.sample_message)

        assert(f"Creating bodhi user for '{expected_username}'."
               not in caplog.messages)

    # Test messages that should be ignored.

    def test_ignored_tag(self, caplog):
        """Test messages re: tags not configured for automatic updates."""
        caplog.set_level(logging.DEBUG)

        msg = deepcopy(self.sample_message)
        bogus_tag = 'thisisntthetagyourelookingfor'
        msg.body['tag'] = bogus_tag
        self.handler(msg)

        assert any(x.startswith(f"Ignoring build being tagged into '{bogus_tag}'")
                   for x in caplog.messages)

    def test_duplicate_message(self, caplog):
        """Assert that duplicate messages ignore existing build/update."""
        caplog.set_level(logging.DEBUG)

        with mock_sends(UpdateMessage):
            self.handler(self.sample_message)

        caplog.clear()

        self.handler(self.sample_message)

        assert (f"Build, active update for {self.sample_nvr} exists already, skipping."
                in caplog.messages)
