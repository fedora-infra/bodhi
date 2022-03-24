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

from bodhi.server.config import config
from bodhi.server.consumers.automatic_updates import AutomaticUpdateHandler
from bodhi.server.models import (
    Build,
    Release,
    TestGatingStatus,
    Update,
    UpdateRequest,
    UpdateStatus,
    UpdateType,
    User,
)

from .. import base


@mock.patch('bodhi.server.consumers.automatic_updates.work_on_bugs_task', mock.Mock())
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

    # Test the main code paths.

    @pytest.mark.parametrize('critpath', (True, False))
    @mock.patch('bodhi.server.models.Update.contains_critpath_component')
    def test_consume(self, contains, critpath, caplog):
        """Assert that messages about tagged builds create an update."""
        caplog.set_level(logging.DEBUG)

        # The following is a really dirty hack
        # We can't better mock things because 'util.get_critpath_components' uses a custom
        # wrapper to "memoize" values that causes leakage between tests
        contains.return_value = critpath

        # process the message
        self.handler(self.sample_message)

        # check if the update exists...
        update = self.db.query(Update).join(Build).filter(
            Update.builds.any(Build.nvr == self.sample_nvr)
        ).first()

        # ...and some of its properties
        assert update is not None
        assert update.type == UpdateType.newpackage
        assert update.status == UpdateStatus.pending
        assert update.autokarma == False
        assert update.test_gating_status is None
        assert update.builds[0].release == self.release
        if critpath:
            assert update.critpath == True
        else:
            assert update.critpath == False

        expected_username = base.buildsys.DevBuildsys._build_data['owner_name']
        assert update.user and update.user.name == expected_username

        assert not any(r.levelno >= logging.WARNING for r in caplog.records)

    @pytest.mark.parametrize('changelog', (True, None, ""))
    @mock.patch('bodhi.server.models.RpmBuild.get_changelog')
    def test_changelog(self, mock_generate_changelog, changelog):
        """Assert that update notes contain the changelog if it exists."""
        if changelog:
            # fill the changelog here rather than in the decorator
            changelog = ('* Sat Aug  3 2013 Fedora Releng <rel-eng@lists.fedoraproject.org> - 2\n'
                         '- Added a free money feature.\n* Tue Jun 11 2013 Randy <bowlofeggs@fpo>'
                         ' - 2.0.1-2\n- Make users ☺\n')

        mock_generate_changelog.return_value = changelog

        # process the message
        self.handler(self.sample_message)

        # check if the update exists...
        update = self.db.query(Update).join(Build).filter(
            Update.builds.any(Build.nvr == self.sample_nvr)
        ).first()

        if changelog:
            assert update.notes == f"""Automatic update for colord-1.3.4-1.fc26.

##### **Changelog**

```
{changelog}
```"""
        else:  # no changelog
            assert update.notes == "Automatic update for colord-1.3.4-1.fc26."

    @mock.patch('bodhi.server.models.RpmBuild.get_changelog')
    def test_bug_added(self, mock_generate_changelog):
        """Assert that a bug is added to the update if proper string is in changelog."""
        changelog = ('* Sat Aug  3 2013 Fedora Releng <rel-eng@lists.fedoraproject.org> - 2\n'
                     '- Added a free money feature.\n- Fix rhbz#112233.')

        mock_generate_changelog.return_value = changelog

        # process the message
        self.handler(self.sample_message)

        # check if the update exists...
        update = self.db.query(Update).join(Build).filter(
            Update.builds.any(Build.nvr == self.sample_nvr)
        ).first()

        assert update.notes == f"""Automatic update for colord-1.3.4-1.fc26.

##### **Changelog**

```
{changelog}
```"""
        assert len(update.bugs) > 0
        assert update.bugs[0].bug_id == 112233

    @mock.patch.dict(config, [('bz_exclude_rels', ['F17'])])
    @mock.patch('bodhi.server.models.RpmBuild.get_changelog')
    def test_bug_not_added_excluded_release(self, mock_generate_changelog):
        """Assert that a bug is not added for excluded release."""
        changelog = ('* Sat Aug  3 2013 Fedora Releng <rel-eng@lists.fedoraproject.org> - 2\n'
                     '- Added a free money feature.\n- Fix rhbz#112233.')

        mock_generate_changelog.return_value = changelog

        # process the message
        self.handler(self.sample_message)

        # check if the update exists...
        update = self.db.query(Update).join(Build).filter(
            Update.builds.any(Build.nvr == self.sample_nvr)
        ).first()

        assert update.notes == f"""Automatic update for colord-1.3.4-1.fc26.

##### **Changelog**

```
{changelog}
```"""
        assert len(update.bugs) == 0

    @mock.patch('bodhi.server.consumers.automatic_updates.log.warning')
    @mock.patch('bodhi.server.consumers.automatic_updates.sleep')
    @mock.patch('bodhi.server.models.RpmBuild.get_changelog')
    def test_changelog_handled_exception(self, mock_generate_changelog, sleep, warning):
        """Assert that update creation is not successful if get_changelog() raises ValueError."""
        mock_generate_changelog.side_effect = ValueError('Handled exception')
        with pytest.raises(ValueError) as exc:
            self.handler(self.sample_message)
        assert str(exc.value) == 'Handled exception'
        sleep.assert_called_once_with(5)
        warning.assert_called_once_with('Handled exception')

    @mock.patch('bodhi.server.models.RpmBuild.get_changelog')
    def test_changelog_unhandled_exception(self, mock_generate_changelog):
        """Assert that update creation is not succesful if get_changelog() raises Exception."""
        mock_generate_changelog.side_effect = Exception('Unhandled exception')
        with pytest.raises(Exception) as exc:
            self.handler(self.sample_message)
        assert str(exc.value) == 'Unhandled exception'

    def test_consume_with_orphan_build(self, caplog):
        """
        Assert existing builds without an update can be handled.

        Such builds can exist e.g. if they're used in a buildroot override.
        """
        caplog.set_level(logging.DEBUG)

        # Run the handler to create the build & update, then remove the update.
        self.handler(self.sample_message)
        build = self.db.query(Build).filter_by(nvr=self.sample_nvr).one()
        update = build.update
        build.update = None  # satisfy foreign key constraint
        self.db.delete(update)

        # Now test with the same message again which should encounter the
        # build already existing in the database.
        self.handler(self.sample_message)

        # check if the update exists...
        update = self.db.query(Update).join(Build).filter(
            Update.builds.any(Build.nvr == self.sample_nvr)
        ).first()

        # ...and some of its properties
        assert update is not None
        assert update.type == UpdateType.unspecified
        assert update.status == UpdateStatus.pending
        assert update.test_gating_status is None

        expected_username = base.buildsys.DevBuildsys._build_data['owner_name']
        assert update.user and update.user.name == expected_username

        assert not any(r.levelno >= logging.WARNING for r in caplog.records)

    def test_existing_pending_update(self, caplog):
        """
        Ensure an update is not created if a matching pending one exists.
        """
        caplog.set_level(logging.DEBUG)

        self.handler(self.sample_message)
        update = self.db.query(Update).join(Build).filter(
            Update.builds.any(Build.nvr == self.sample_nvr)
        ).first()
        # Move it back to Pending as if the user has manually created it
        update.status = UpdateStatus.pending
        update.request = UpdateRequest.testing
        self.db.add(update)
        self.db.flush()
        # Clear pending messages
        self.db.info['messages'] = []

        caplog.clear()

        self.handler(self.sample_message)

        assert (f"Build, active update for {self.sample_nvr} exists already, skipping."
                in caplog.messages)

    def test_obsolete_testing_update(self, caplog):
        """Assert that older builds stuck in Testing get obsoleted."""
        caplog.set_level(logging.DEBUG)

        self.handler(self.sample_message)
        update = self.db.query(Update).join(Build).filter(
            Update.builds.any(Build.nvr == self.sample_nvr)
        ).first()
        assert update is not None
        # Simulate update status after failed gating
        update.status = UpdateStatus.testing
        update.test_gating_status = TestGatingStatus.failed
        self.db.flush()
        # Clear pending messages
        self.db.info['messages'] = []

        caplog.clear()

        # Create an update with a newer build
        msg = deepcopy(self.sample_message)
        msg.body['version'] = '1.3.5'
        msg.body['build_id'] = 442563
        self.handler(msg)
        nvr = self.sample_nvr.replace('1.3.4', '1.3.5')
        old_update = self.db.query(Update).join(Build).filter(
            Update.builds.any(Build.nvr == self.sample_nvr)
        ).first()
        new_update = self.db.query(Update).join(Build).filter(
            Update.builds.any(Build.nvr == nvr)
        ).first()
        assert new_update is not None
        assert old_update is not None
        assert new_update.status == UpdateStatus.pending
        assert old_update.status == UpdateStatus.obsolete

    def test_problem_obsoleting_older_update(self, caplog):
        """Assert that an error while obsoleting doesn't block a new update being created."""
        caplog.set_level(logging.DEBUG)

        self.handler(self.sample_message)
        update = self.db.query(Update).join(Build).filter(
            Update.builds.any(Build.nvr == self.sample_nvr)
        ).first()
        assert update is not None
        # Simulate update status after failed gating
        update.status = UpdateStatus.testing
        update.test_gating_status = TestGatingStatus.failed
        self.db.flush()
        # Clear pending messages
        self.db.info['messages'] = []

        caplog.clear()

        # Create an update with a newer build
        msg = deepcopy(self.sample_message)
        msg.body['version'] = '1.3.5'
        msg.body['build_id'] = 442563
        with mock.patch('bodhi.server.models.Update.obsolete_older_updates',
                        side_effect=Exception('Something gone wrong')):
            self.handler(msg)
        assert 'Problem obsoleting older updates: Something gone wrong' in caplog.messages

        # The new update should have been created and the old one should be stuck in testing
        nvr = self.sample_nvr.replace('1.3.4', '1.3.5')
        old_update = self.db.query(Update).join(Build).filter(
            Update.builds.any(Build.nvr == self.sample_nvr)
        ).first()
        new_update = self.db.query(Update).join(Build).filter(
            Update.builds.any(Build.nvr == nvr)
        ).first()
        assert new_update is not None
        assert old_update is not None
        assert new_update.status == UpdateStatus.pending
        assert old_update.status == UpdateStatus.testing

    # The following tests cover lesser-travelled code paths.

    @mock.patch('bodhi.server.consumers.automatic_updates.transactional_session_maker')
    def test___init___without_db_factory(self, transactional_session_maker):
        """__init__() should create db_factory if missing."""
        handler = AutomaticUpdateHandler()

        assert handler.db_factory is transactional_session_maker.return_value
        transactional_session_maker.assert_called_once_with()

    # Test robustness: malformed messages, unknown koji builds, incomplete
    # buildinfo, release missing from the DB

    @pytest.mark.parametrize('missing_elem', ('tag', 'build_id', 'name', 'version', 'release'))
    def test_missing_mandatory_elems(self, missing_elem, caplog):
        """Test tag message without mandatory elements."""
        caplog.set_level(logging.DEBUG)
        msg = deepcopy(self.sample_message)
        del msg.body[missing_elem]
        self.handler(msg)
        assert any(r.levelno == logging.DEBUG
                   and r.getMessage() == f"Received incomplete tag message. Missing: {missing_elem}"
                   for r in caplog.records)

    def test_unknown_koji_build(self, caplog):
        """Test tag message about unknown koji build."""
        caplog.set_level(logging.DEBUG)
        msg = deepcopy(self.sample_message)
        msg.body['release'] += '.youdontknowme'
        self.handler(msg)
        assert any(r.levelno == logging.DEBUG
                   and r.getMessage().startswith("Can't find Koji build for ")
                   for r in caplog.records)

    def test_incomplete_koji_buildinfo_nvr(self, caplog):
        """Test koji returning incomplete buildinfo: no nvr."""
        caplog.set_level(logging.DEBUG)
        msg = deepcopy(self.sample_message)
        msg.body['release'] += '.testmissingnvr'
        self.handler(msg)
        assert any(r.levelno == logging.DEBUG
                   and r.getMessage().startswith("Koji build info for ")
                   and r.getMessage().endswith(" doesn't contain 'nvr'.")
                   for r in caplog.records)

    def test_incomplete_koji_buildinfo_owner(self, caplog):
        """Test koji returning incomplete buildinfo: no owner."""
        caplog.set_level(logging.DEBUG)
        msg = deepcopy(self.sample_message)
        msg.body['release'] += '.noowner'
        self.handler(msg)
        assert any(r.levelno == logging.DEBUG
                   and r.getMessage().startswith("Koji build info for ")
                   and r.getMessage().endswith(" doesn't contain 'owner_name'.")
                   for r in caplog.records)

    def test_missing_user(self, caplog):
        """Test Koji build user missing from DB."""
        caplog.set_level(logging.DEBUG)

        expected_username = base.buildsys.DevBuildsys._build_data['owner_name']

        # ensure user with expected name doesn't exist
        self.db.query(User).filter_by(name=expected_username).delete()
        self.db.flush()

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

        assert(f"Creating bodhi user for '{expected_username}'."
               not in caplog.messages)

    # Test messages that should be ignored.

    def test_ignored_tag(self, caplog):
        """Test messages re: tags not configured for automatic updates."""
        caplog.set_level(logging.DEBUG)

        msg = deepcopy(self.sample_message)
        bogus_tag = 'thisisntthetagyourelookingfor'
        msg.body['tag'] = bogus_tag
        with mock_sends():
            self.handler(msg)

        assert any(x.startswith(f"Ignoring build being tagged into '{bogus_tag}'")
                   for x in caplog.messages)

    def test_duplicate_message(self, caplog):
        """Assert that duplicate messages ignore existing build/update."""
        caplog.set_level(logging.DEBUG)

        self.handler(self.sample_message)

        caplog.clear()

        with mock_sends():
            self.handler(self.sample_message)

        assert (f"Build, active update for {self.sample_nvr} exists already, skipping."
                in caplog.messages)

    @mock.patch.dict(config, [('automatic_updates_blacklist', ['lmacken'])])
    def test_user_in_blacklist(self, caplog):
        """Test that update not created if the koji build owner is in the blacklist"""
        caplog.set_level(logging.DEBUG)
        body = {
            'build_id': 4425622,
            'name': 'python-pants',
            'tag_id': 214,
            'instance': 's390',
            'tag': 'f17-updates-testing-pending',
            'user': 'lmacken',
            'version': '1.3.4',
            'owner': 'lmacken',
            'release': '1.fc26',
        }

        self.sample_message = Message(topic='', body=body)
        self.sample_nvr = f"{body['name']}-{body['version']}-{body['release']}"
        with mock_sends():
            self.handler(self.sample_message)
        assert (f"{self.sample_nvr} owned by lmacken who is listed in "
                "automatic_updates_blacklist, skipping." in caplog.messages)
