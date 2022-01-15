# Copyright © 2016-2019 Red Hat, Inc. and others.
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
"""
This module contains tests for the bodhi.server.scripts.untag_branched module.
"""
from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import call, patch

import pytest

from bodhi.server import models
from bodhi.server.scripts import untag_branched
from ..base import BasePyTestCase


class TestMain(BasePyTestCase):
    """Test the main() function."""

    @patch('bodhi.server.models.buildsys.get_session')
    @patch('bodhi.server.scripts.untag_branched.get_appsettings', return_value={'some': 'settings'})
    @patch('bodhi.server.scripts.untag_branched.initialize_db')
    @patch('bodhi.server.scripts.untag_branched.logging.getLogger')
    @patch('bodhi.server.scripts.untag_branched.setup_logging')
    @patch('sys.exit')
    def test_exception_handler(self, exit, setup_logging, getLogger, initialize_db, get_appsettings,
                               get_session):
        """Test the exception handler."""
        log = getLogger.return_value
        koji = get_session.return_value
        release = models.Release.query.first()
        release.state = models.ReleaseState.pending
        update = models.Update.query.filter_by(release=release).first()
        update.date_stable = datetime.utcnow() - timedelta(days=2)
        update.status = models.UpdateStatus.stable
        # Since only the stable tag is not present, no calls to untagBuild should happen.
        koji.listTags.side_effect = IOError("Can't talk to koji bro")
        self.db.flush()

        untag_branched.main(['untag_branched', 'some_config_path'])

        setup_logging.assert_called_once_with()
        initialize_db.assert_called_once_with({'some': 'settings'})
        get_appsettings.assert_called_once_with('some_config_path')
        # Nothing should have been untagged
        assert koji.untagBuild.call_count == 0
        # An error should have been logged
        log.error.assert_called_once_with(koji.listTags.side_effect)
        koji.listTags.assert_called_once_with('bodhi-2.0-1.fc17')
        exit.assert_called_once_with(1)

    @patch('bodhi.server.models.buildsys.get_session')
    @patch('bodhi.server.scripts.untag_branched.get_appsettings', return_value={'some': 'settings'})
    @patch('bodhi.server.scripts.untag_branched.initialize_db')
    @patch('bodhi.server.scripts.untag_branched.logging.getLogger')
    @patch('bodhi.server.scripts.untag_branched.setup_logging')
    def test_no_tags_to_remove(self, setup_logging, getLogger, initialize_db, get_appsettings,
                               get_session):
        """Assert correct behavior when there are no tags to remove."""
        log = getLogger.return_value
        koji = get_session.return_value
        release = models.Release.query.first()
        release.state = models.ReleaseState.pending
        update = models.Update.query.filter_by(release=release).first()
        update.date_stable = datetime.utcnow() - timedelta(days=2)
        update.status = models.UpdateStatus.stable
        # Since only the stable tag is not present, no calls to untagBuild should happen.
        koji.listTags.return_value = [{'name': 'f17'}]
        self.db.flush()

        untag_branched.main(['untag_branched', 'some_config_path'])

        setup_logging.assert_called_once_with()
        initialize_db.assert_called_once_with({'some': 'settings'})
        get_appsettings.assert_called_once_with('some_config_path')
        # Nothing should have been untagged
        assert koji.untagBuild.call_count == 0
        # No errors should have been logged
        assert log.error.call_count == 0
        # The Release name should have been logged
        log.info.assert_called_once_with(release.name)
        koji.listTags.assert_called_once_with('bodhi-2.0-1.fc17')

    @patch('bodhi.server.models.buildsys.get_session')
    @patch('bodhi.server.scripts.untag_branched.get_appsettings', return_value={'some': 'settings'})
    @patch('bodhi.server.scripts.untag_branched.initialize_db')
    @patch('bodhi.server.scripts.untag_branched.logging.getLogger')
    @patch('bodhi.server.scripts.untag_branched.setup_logging')
    def test_pending_signing_tag_present(self, setup_logging, getLogger, initialize_db,
                                         get_appsettings, get_session):
        """The pending_signing tag should be removed if it is present."""
        log = getLogger.return_value
        koji = get_session.return_value
        release = models.Release.query.first()
        release.state = models.ReleaseState.pending
        update = models.Update.query.filter_by(release=release).first()
        update.date_stable = datetime.utcnow() - timedelta(days=2)
        update.status = models.UpdateStatus.stable
        # The pending_signing tag is present so it should be removed.
        koji.listTags.return_value = [{'name': 'f17-updates-signing-pending'}, {'name': 'f17'}]
        self.db.flush()

        untag_branched.main(['untag_branched', 'some_config_path'])

        setup_logging.assert_called_once_with()
        initialize_db.assert_called_once_with({'some': 'settings'})
        get_appsettings.assert_called_once_with('some_config_path')
        # Nothing should have been untagged
        koji.untagBuild.assert_called_once_with('f17-updates-signing-pending', 'bodhi-2.0-1.fc17')
        # An error should have been logged about the stable tag missing
        assert log.error.call_count == 0
        # The Release name should have been logged and a message should have been logged about
        # removing the tag.
        assert log.info.mock_calls == \
            [call(release.name),
             call('Removing f17-updates-signing-pending from bodhi-2.0-1.fc17')]
        koji.listTags.assert_called_once_with('bodhi-2.0-1.fc17')

    @patch('bodhi.server.models.buildsys.get_session')
    @patch('bodhi.server.scripts.untag_branched.get_appsettings', return_value={'some': 'settings'})
    @patch('bodhi.server.scripts.untag_branched.initialize_db')
    @patch('bodhi.server.scripts.untag_branched.logging.getLogger')
    @patch('bodhi.server.scripts.untag_branched.setup_logging')
    def test_pending_testing_tag_present(self, setup_logging, getLogger, initialize_db,
                                         get_appsettings, get_session):
        """The pending_testing tag should be removed if it is present."""
        log = getLogger.return_value
        koji = get_session.return_value
        release = models.Release.query.first()
        release.state = models.ReleaseState.pending
        update = models.Update.query.filter_by(release=release).first()
        update.date_stable = datetime.utcnow() - timedelta(days=2)
        update.status = models.UpdateStatus.stable
        # The pending_testing tag is present so it should be removed.
        koji.listTags.return_value = [{'name': 'f17-updates-testing-pending'}, {'name': 'f17'}]
        self.db.flush()

        untag_branched.main(['untag_branched', 'some_config_path'])

        setup_logging.assert_called_once_with()
        initialize_db.assert_called_once_with({'some': 'settings'})
        get_appsettings.assert_called_once_with('some_config_path')
        # Nothing should have been untagged
        koji.untagBuild.assert_called_once_with('f17-updates-testing-pending', 'bodhi-2.0-1.fc17')
        # An error should have been logged about the stable tag missing
        assert log.error.call_count == 0
        # The Release name should have been logged and a message should have been logged about
        # removing the tag.
        assert log.info.mock_calls ==\
            [call(release.name),
             call('Removing f17-updates-testing-pending from bodhi-2.0-1.fc17')]
        koji.listTags.assert_called_once_with('bodhi-2.0-1.fc17')

    @patch('bodhi.server.models.buildsys.get_session')
    @patch('bodhi.server.scripts.untag_branched.get_appsettings', return_value={'some': 'settings'})
    @patch('bodhi.server.scripts.untag_branched.initialize_db')
    @patch('bodhi.server.scripts.untag_branched.logging.getLogger')
    @patch('bodhi.server.scripts.untag_branched.setup_logging')
    def test_stable_tag_missing(self, setup_logging, getLogger, initialize_db, get_appsettings,
                                get_session):
        """An error should be logged if the stable tag is not on a stable build."""
        log = getLogger.return_value
        koji = get_session.return_value
        release = models.Release.query.first()
        release.state = models.ReleaseState.pending
        update = models.Update.query.filter_by(release=release).first()
        update.date_stable = datetime.utcnow() - timedelta(days=2)
        update.status = models.UpdateStatus.stable
        # Since the stable tag is not present, none of these should be removed.
        koji.listTags.return_value = [
            {'name': 'f17-updates-testing'}, {'name': 'f17-updates-signing-pending'},
            {'name': 'f17-updates-testing-pending'}]
        self.db.flush()

        untag_branched.main(['untag_branched', 'some_config_path'])

        setup_logging.assert_called_once_with()
        initialize_db.assert_called_once_with({'some': 'settings'})
        get_appsettings.assert_called_once_with('some_config_path')
        # Nothing should have been untagged
        assert koji.untagBuild.call_count == 0
        # An error should have been logged about the stable tag missing
        log.error.assert_called_once_with(
            ("bodhi-2.0-1.fc17 not tagged as stable ['f17-updates-testing', "
             "'f17-updates-signing-pending', 'f17-updates-testing-pending']"))
        # The Release name should have been logged
        log.info.assert_called_once_with(release.name)
        koji.listTags.assert_called_once_with('bodhi-2.0-1.fc17')

    @patch('bodhi.server.models.buildsys.get_session')
    @patch('bodhi.server.scripts.untag_branched.get_appsettings', return_value={'some': 'settings'})
    @patch('bodhi.server.scripts.untag_branched.initialize_db')
    @patch('bodhi.server.scripts.untag_branched.logging.getLogger')
    @patch('bodhi.server.scripts.untag_branched.setup_logging')
    def test_testing_tag_present(self, setup_logging, getLogger, initialize_db, get_appsettings,
                                 get_session):
        """The testing tag should be removed if it is present."""
        log = getLogger.return_value
        koji = get_session.return_value
        release = models.Release.query.first()
        release.state = models.ReleaseState.pending
        update = models.Update.query.filter_by(release=release).first()
        update.date_stable = datetime.utcnow() - timedelta(days=2)
        update.status = models.UpdateStatus.stable
        # The testing tag is present so it should be removed.
        koji.listTags.return_value = [{'name': 'f17-updates-testing'}, {'name': 'f17'}]
        self.db.flush()

        untag_branched.main(['untag_branched', 'some_config_path'])

        setup_logging.assert_called_once_with()
        initialize_db.assert_called_once_with({'some': 'settings'})
        get_appsettings.assert_called_once_with('some_config_path')
        # Nothing should have been untagged
        koji.untagBuild.assert_called_once_with('f17-updates-testing', 'bodhi-2.0-1.fc17')
        # An error should have been logged about the stable tag missing
        assert log.error.call_count == 0
        # The Release name should have been logged and a message should have been logged about
        # removing the tag.
        assert log.info.mock_calls == \
            [call(release.name), call('Removing f17-updates-testing from bodhi-2.0-1.fc17')]
        koji.listTags.assert_called_once_with('bodhi-2.0-1.fc17')

    @patch('bodhi.server.models.buildsys.get_session')
    @patch('bodhi.server.scripts.untag_branched.get_appsettings', return_value={'some': 'settings'})
    @patch('bodhi.server.scripts.untag_branched.initialize_db')
    @patch('bodhi.server.scripts.untag_branched.logging.getLogger')
    @patch('bodhi.server.scripts.untag_branched.setup_logging')
    def test_testing_tag_present_update_too_new(self, setup_logging, getLogger, initialize_db,
                                                get_appsettings, get_session):
        """The testing tag should stay if update is too new."""
        log = getLogger.return_value
        koji = get_session.return_value
        release = models.Release.query.first()
        release.state = models.ReleaseState.pending
        update = models.Update.query.filter_by(release=release).first()
        update.date_stable = datetime.utcnow()
        update.status = models.UpdateStatus.stable
        # The testing tag is present and should stay.
        koji.listTags.return_value = [{'name': 'f17-updates-testing'}, {'name': 'f17'}]
        self.db.flush()

        untag_branched.main(['untag_branched', 'some_config_path'])

        setup_logging.assert_called_once_with()
        initialize_db.assert_called_once_with({'some': 'settings'})
        get_appsettings.assert_called_once_with('some_config_path')
        # Nothing should have been untagged
        assert koji.untagBuild.call_count == 0
        # No errors should have been logged
        assert log.error.call_count == 0
        # The Release name should have been logged
        log.info.assert_called_once_with(release.name)
        # There should have been no attempts to list the tags
        assert koji.listTags.call_count == 0

    @patch('sys.exit')
    @patch('sys.stdout', new_callable=StringIO)
    def test_usage(self, stdout, exit):
        """Ensure that usage is called if not enough args are passed."""
        exit.side_effect = RuntimeError("We don't want the main() function to continue.")

        with pytest.raises(RuntimeError) as exc:
            untag_branched.main(['untag_branched'])

        assert exc.type is RuntimeError
        assert exc.value is exit.side_effect
        assert stdout.getvalue() == \
            'usage: untag_branched <config_uri>\n(example: "untag_branched development.ini")\n'
        exit.assert_called_once_with(1)


class TestUsage:
    """
    This class contains tests for the usage() function.
    """
    @patch('sys.exit')
    @patch('sys.stdout', new_callable=StringIO)
    def test_usage(self, stdout, exit):
        """
        Make sure the usage info is printed and then it exits.
        """
        argv = ['untag_branched']

        untag_branched.usage(argv)

        assert stdout.getvalue() == \
            'usage: untag_branched <config_uri>\n(example: "untag_branched development.ini")\n'
        exit.assert_called_once_with(1)
