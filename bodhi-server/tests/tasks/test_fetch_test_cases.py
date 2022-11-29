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
This module contains tests for the bodhi.server.fetch_test_cases module.
"""

from unittest.mock import patch
from urllib.error import URLError

import pytest

from bodhi.server import config, models
from bodhi.server.exceptions import BodhiException, ExternalCallException
from bodhi.server.tasks import fetch_test_cases_task
from bodhi.server.tasks.fetch_test_cases import main as fetch_test_cases_main

from ..base import BasePyTestCase
from .base import BaseTaskTestCase


class TestTask(BasePyTestCase):
    """Test the task in bodhi.server.tasks."""

    @patch("bodhi.server.tasks.buildsys")
    @patch("bodhi.server.tasks.initialize_db")
    @patch("bodhi.server.tasks.config")
    @patch("bodhi.server.tasks.fetch_test_cases.main")
    def test_task(self, main_function, config_mock, init_db_mock, buildsys):
        fetch_test_cases_task('foo')
        config_mock.load_config.assert_called_with()
        init_db_mock.assert_called_with(config_mock)
        buildsys.setup_buildsystem.assert_called_with(config_mock)
        main_function.assert_called_with('foo')


class TestFetchTestCases(BaseTaskTestCase):
    """This test class contains tests for the main() function."""

    @patch.dict(config.config, {'query_wiki_test_cases': True})
    @patch('bodhi.server.models.Build.update_test_cases')
    def test_update_nonexistent(self, fetch):
        """
        Assert BodhiException is raised if the update doesn't exist.
        """
        with pytest.raises(BodhiException) as exc:
            fetch_test_cases_main('foo')

        assert str(exc.value) == "Couldn't find alias foo in DB"
        fetch.assert_not_called()

    @patch.dict(config.config, {'query_wiki_test_cases': True})
    @patch('bodhi.server.models.MediaWiki')
    @patch('bodhi.server.tasks.fetch_test_cases.log.warning')
    def test_fetch_test_cases_exception(self, warning, MediaWiki):
        """
        Assert that fetch_test_cases logs a warning when an exception is raised.
        """
        MediaWiki.return_value.call.side_effect = URLError("oh no!")

        update = self.db.query(models.Update).join(models.Build).filter(
            models.Build.nvr == 'bodhi-2.0-1.fc17').one()

        with pytest.raises(ExternalCallException):
            fetch_test_cases_main(update.alias)

        warning.assert_called_once_with('Error occurred during fetching testcases', exc_info=True)

    @patch.dict(config.config, {'query_wiki_test_cases': True})
    @patch('bodhi.server.models.Build.update_test_cases')
    def test_fetch_test_cases_run(self, fetch):
        """
        Assert that Build.update_test_cases is called.
        """
        update = self.db.query(models.Update).join(models.Build).filter(
            models.Build.nvr == 'bodhi-2.0-1.fc17').one()
        fetch_test_cases_main(update.alias)

        fetch.assert_called_once()
