# Copyright © 2016-2020 Red Hat, Inc. and others.
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
This module contains tests for the bodhi.server.work_on_bugs module.
"""

from unittest.mock import patch

import pytest

from bodhi.server import config, models
from bodhi.server.exceptions import BodhiException, ExternalCallException
from bodhi.server.tasks import work_on_bugs_task
from bodhi.server.tasks.work_on_bugs import main as work_on_bugs_main
from ..base import BasePyTestCase
from .base import BaseTaskTestCase


class TestTask(BasePyTestCase):
    """Test the task in bodhi.server.tasks."""

    @patch("bodhi.server.tasks.buildsys")
    @patch("bodhi.server.tasks.initialize_db")
    @patch("bodhi.server.tasks.config")
    @patch("bodhi.server.tasks.work_on_bugs.main")
    def test_task(self, main_function, config_mock, init_db_mock, buildsys):
        work_on_bugs_task('foo', [12345, 67890])
        config_mock.load_config.assert_called_with()
        init_db_mock.assert_called_with(config_mock)
        buildsys.setup_buildsystem.assert_called_with(config_mock)
        main_function.assert_called_with('foo', [12345, 67890])


class TestWorkOnBugs(BaseTaskTestCase):
    """This test class contains tests for the main() function."""

    @patch.dict(config.config, {'query_wiki_test_cases': True})
    def test_update_nonexistent(self):
        """
        Assert BodhiException is raised if the update doesn't exist.
        """
        with pytest.raises(BodhiException) as exc:
            work_on_bugs_main('foo', [])

        assert str(exc.value) == "Couldn't find alias foo in DB"

    def test_security_bug_sets_update_to_security(self):
        """Assert that associating a security bug with an Update changes the Update to security."""
        update = models.Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        # The update should start out in a non-security state so we know that work_on_bugs() changed
        # it.
        assert update.type == models.UpdateType.bugfix
        bug = models.Bug.query.first()
        # Set this bug to security, so that the update gets switched to security.
        bug.security = True
        self.db.flush()
        bugs = models.Bug.query.all()
        bug_ids = [bug.bug_id for bug in bugs]

        work_on_bugs_main(update.alias, bug_ids)

        assert update.type == models.UpdateType.security

    @patch('bodhi.server.tasks.work_on_bugs.log.warning')
    def test_work_on_bugs_exception(self, warning):
        """
        Assert that work_on_bugs logs a warning when an exception is raised.
        """
        update = models.Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        bugs = models.Bug.query.all()
        bug_ids = [bug.bug_id for bug in bugs]

        with patch('bodhi.server.tasks.work_on_bugs.bug_module.bugtracker.getbug',
                   side_effect=RuntimeError("oh no!")):
            with pytest.raises(ExternalCallException):
                work_on_bugs_main(update.alias, bug_ids)

        warning.assert_called_once_with('Error occurred during updating single bug', exc_info=True)

    @patch('bodhi.server.models.Bug.modified')
    def test_bug_not_in_database(self, modified):
        """Test that a bug is automatically created if not present in database."""
        update = models.Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update

        bug = models.Bug.query.filter_by(bug_id=123456).first()
        assert bug is None

        work_on_bugs_main(update.alias, [123456, ])

        bug = models.Bug.query.filter_by(bug_id=123456).one()
        update = models.Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        assert bug in update.bugs
        assert modified.assert_called_once

    @patch('bodhi.server.models.Bug.modified')
    def test_bug_not_associated_to_update(self, modified):
        """Test that a bug is added to the update if not already associated."""
        bug = models.Bug(bug_id=123456)
        self.db.add(bug)
        self.db.commit()
        update = models.Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update

        work_on_bugs_main(update.alias, [123456, ])

        bug = models.Bug.query.filter_by(bug_id=123456).one()
        update = models.Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update
        assert bug in update.bugs
        assert modified.assert_called_once
