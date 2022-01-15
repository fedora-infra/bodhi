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
import pytest

from bodhi.server.consumers.ci import CIHandler
from bodhi.server.models import (
    Build, Release, Package, Update, User, UpdateType
)
from .. import base


class TestCIHandler(base.BasePyTestCase):
    """Test the automatic update handler."""

    def setup_method(self, method):
        """Set up environment for each test."""
        super().setup_method(method)

        release = self.db.query(Release).filter_by(name='F17').first()
        package = self.db.query(Package).first()
        user = self.db.query(User).first()

        self.update = Update(
            release=release,
            stable_karma=0,
            unstable_karma=0,
            notes='',
            type=UpdateType.bugfix,
            user=user,
        )
        self.build = Build(
            nvr='colord-1.3.4-1.fc26',
            update=self.update,
            type=package.type,
            package=package
        )

        self.db.add(self.update)
        self.db.add(self.build)
        self.db.commit()

        body = {
            'contact': 'bodhi@fedoraproject.org',
            'run': {
                'url': 'https://example.url',
            },
            'artifact': {
                'nvr': 'colord-1.3.4-1.fc26'
            },
            'pipeline': {
                'id': 442562,
            },
            'test': 'test',
            'generated_at': 'somedate',
            'version': '1.3.4',
        }

        self.sample_message = Message(topic='', body=body)

        self.db_factory = base.TransactionalSessionMaker(self.Session)
        self.handler = CIHandler(self.db_factory)

    # Test the main code paths.

    def test_consume(self, caplog):
        """Assert that comment is added to update."""
        caplog.set_level(logging.DEBUG)

        # process the message
        self.handler(self.sample_message)

        comment = self.update.comments[-1]

        # Check if comment was created
        assert comment.text == "CI testing started: 'https://example.url'."
        assert comment.user.name == "bodhi"

        assert "Committing changes to the database." in caplog.text

    def test_consume_update_from_tag(self, caplog):
        """
        Assert that comment for update created from tag is not created.
        """
        caplog.set_level(logging.DEBUG)

        self.update.from_tag = "foo_tag"

        self.handler(self.sample_message)

        # assert that comment is not created
        assert len(self.update.comments) == 0

        assert "Update is created from tag. Skipping comment." \
               in caplog.text

    @mock.patch('bodhi.server.consumers.ci.transactional_session_maker')
    def test___init___without_db_factory(self, transactional_session_maker):
        """__init__() should create db_factory if missing."""
        handler = CIHandler()

        assert handler.db_factory is transactional_session_maker.return_value
        transactional_session_maker.assert_called_once_with()

    # Test robustness: malformed messages, unknown koji builds, incomplete
    # buildinfo, release missing from the DB

    @pytest.mark.parametrize('missing_elem',
                             ('contact', 'run', 'artifact', 'pipeline', 'test',
                              'generated_at', 'version'))
    def test_missing_mandatory_elems(self, missing_elem, caplog):
        """Test tag message without mandatory elements."""
        caplog.set_level(logging.DEBUG)
        msg = deepcopy(self.sample_message)
        del msg.body[missing_elem]
        self.handler(msg)
        assert any(r.levelno == logging.DEBUG
                   and r.getMessage() == f"Received incomplete CI message. Missing: {missing_elem}"
                   for r in caplog.records)

    def test_consume_build_not_exist(self, caplog):
        """
        Assert that missing build is handled correctly.
        """
        caplog.set_level(logging.DEBUG)

        body = {
            'contact': 'bodhi@fedoraproject.org',
            'run': {
                'url': 'https://example.url',
            },
            'artifact': {
                'nvr': 'colord-1.3.4-2.fc26'
            },
            'pipeline': {
                'id': 442562,
            },
            'test': 'test',
            'generated_at': 'somedate',
            'version': '1.3.4',
        }

        sample_message = Message(topic='', body=body)
        self.handler(sample_message)

        # assert that comment is not created
        assert len(self.update.comments) == 0

        assert "Can't get build for 'colord-1.3.4-2.fc26'." in caplog.text

    @mock.patch("bodhi.server.buildsys.DevBuildsys.getBuild", return_value={
        'nvr': 'colord-1.3.4-1.fc26'})
    def test_consume_nvr_field_missing(self, mock_getBuild, caplog):
        """
        Assert that we use build_id if nvr field is missing in message.
        """
        caplog.set_level(logging.DEBUG)

        body = {
            'contact': 'bodhi@fedoraproject.org',
            'run': {
                'url': 'https://example.url',
            },
            'artifact': {},
            'pipeline': {
                'id': 442562,
            },
            'test': 'test',
            'generated_at': 'somedate',
            'version': '1.3.4',
        }

        sample_message = Message(topic='', body=body)
        self.handler(sample_message)

        comment = self.update.comments[-1]

        # Check if comment was created
        assert comment.text == "CI testing started: 'https://example.url'."
        assert comment.user.name == "bodhi"

        mock_getBuild.assert_called_with(442562)

        assert "Committing changes to the database." in caplog.text

    def test_consume_nvr_and_id_missing(self, caplog):
        """
        Assert that we handle message correctly if both build id and nvr is missing.
        """
        caplog.set_level(logging.DEBUG)

        body = {
            'contact': 'bodhi@fedoraproject.org',
            'run': {
                'url': 'https://example.url',
            },
            'artifact': {},
            'pipeline': {},
            'test': 'test',
            'generated_at': 'somedate',
            'version': '1.3.4',
        }

        sample_message = Message(topic='', body=body)
        self.handler(sample_message)

        # assert that comment is not created
        assert len(self.update.comments) == 0

        assert "Received incomplete CI message. Missing: 'artifact.nvr', 'pipeline.id'." \
               in caplog.text

    @mock.patch("bodhi.server.models.mail")
    def test_no_email_notifications(self, mock_mail, caplog):
        """
        Assert that we do not send emails when adding a comment to the update
        """
        caplog.set_level(logging.DEBUG)

        # process the message
        self.handler(self.sample_message)

        comment = self.update.comments[-1]

        # Check if comment was created
        assert comment.text == "CI testing started: 'https://example.url'."
        assert comment.user.name == "bodhi"

        assert "Committing changes to the database." in caplog.text

        mock_mail.assert_not_called()

    def test_consume_run_url_field_is_missing(self, caplog):
        """
        Assert that comment is created when run.url field is missing.
        """
        caplog.set_level(logging.DEBUG)

        body = {
            'contact': 'bodhi@fedoraproject.org',
            'run': {},
            'artifact': {
                'nvr': 'colord-1.3.4-1.fc26'
            },
            'pipeline': {
                'id': 442562,
            },
            'test': 'test',
            'generated_at': 'somedate',
            'version': '1.3.4',
        }

        sample_message = Message(topic='', body=body)
        self.handler(sample_message)

        comment = self.update.comments[-1]

        # Check if comment was created
        assert comment.text == "CI testing started."
        assert comment.user.name == "bodhi"

        assert "Committing changes to the database." in caplog.text

    @mock.patch("bodhi.server.buildsys.DevBuildsys.getBuild", return_value=None)
    def test_consume_no_build_in_koji(self, mock_getBuild, caplog):
        """
        Assert that we handle message correctly if build is not found in koji.
        """
        caplog.set_level(logging.DEBUG)

        body = {
            'contact': 'bodhi@fedoraproject.org',
            'run': {
                'url': 'https://example.url',
            },
            'artifact': {},
            'pipeline': {
                'id': 442562,
            },
            'test': 'test',
            'generated_at': 'somedate',
            'version': '1.3.4',
        }

        sample_message = Message(topic='', body=body)

        self.handler(sample_message)

        # assert that comment is not created
        assert len(self.update.comments) == 0
        mock_getBuild.assert_called_with(442562)

        assert "Can't find Koji build with id '442562'." in caplog.text

    @mock.patch("bodhi.server.buildsys.DevBuildsys.getBuild", return_value={
        'build': 'foo'})
    def test_consume_no_nvr_in_kojiinfo(self, mock_getBuild, caplog):
        """
        Assert that we handle message correctly if build is found in koji,
        but doesn't contain nvr field.
        """
        caplog.set_level(logging.DEBUG)

        body = {
            'contact': 'bodhi@fedoraproject.org',
            'run': {
                'url': 'https://example.url',
            },
            'artifact': {},
            'pipeline': {
                'id': 442562,
            },
            'test': 'test',
            'generated_at': 'somedate',
            'version': '1.3.4',
        }

        sample_message = Message(topic='', body=body)

        self.handler(sample_message)

        # assert that comment is not created
        assert len(self.update.comments) == 0
        mock_getBuild.assert_called_with(442562)

        assert "Koji build info with id '442562' doesn't contain 'nvr'." in caplog.text

    def test_consume_update_not_exist(self, caplog):
        """
        Assert that missing update is handled correctly.
        """
        caplog.set_level(logging.DEBUG)

        self.build.update = None

        self.handler(self.sample_message)

        # assert that comment is not created
        assert len(self.update.comments) == 0

        assert "No update in Bodhi for 'colord-1.3.4-1.fc26'. Nothing to comment on." \
               in caplog.text
