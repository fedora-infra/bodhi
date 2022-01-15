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
This module contains tests for the bodhi.server.tasks.expire_overrides module.
"""

from datetime import timedelta
from unittest import mock

from fedora_messaging import api, testing as fml_testing

from bodhi.server import models
from bodhi.server.tasks import expire_overrides_task
from bodhi.server.tasks.expire_overrides import main as expire_overrides_main
from ..base import BasePyTestCase
from .base import BaseTaskTestCase


class TestTask(BasePyTestCase):
    """Test the task in bodhi.server.tasks."""

    @mock.patch("bodhi.server.tasks.bugs")
    @mock.patch("bodhi.server.tasks.buildsys")
    @mock.patch("bodhi.server.tasks.initialize_db")
    @mock.patch("bodhi.server.tasks.config")
    @mock.patch("bodhi.server.tasks.expire_overrides.main")
    def test_task(self, main_function, config_mock, init_db_mock, buildsys, bugs):
        expire_overrides_task()
        config_mock.load_config.assert_called_with()
        init_db_mock.assert_called_with(config_mock)
        buildsys.setup_buildsystem.assert_called_with(config_mock)
        bugs.set_bugtracker.assert_called_with()
        main_function.assert_called_with()


@mock.patch('bodhi.server.tasks.expire_overrides.log')
class TestMain(BaseTaskTestCase):
    """
    This class contains tests for the main() function.
    """

    def test_no_expire(self, log):
        """
        Assert that we don't expire a buildroot override with an expiration date in the future
        """
        buildrootoverride = self.db.query(models.BuildrootOverride).all()[0]
        buildrootoverride.expiration_date = buildrootoverride.expiration_date + timedelta(days=500)
        self.db.commit()

        expire_overrides_main()

        log.info.assert_called_once_with("No active buildroot override to expire")
        buildrootoverride = self.db.query(models.BuildrootOverride).all()[0]
        assert buildrootoverride.expired_date is None

    def test_expire(self, log):
        """
        Assert that we expire a buildroot override with an expiration date in the past
        """
        buildrootoverride = self.db.query(models.BuildrootOverride).all()[0]
        buildrootoverride.expiration_date = buildrootoverride.expiration_date - timedelta(days=500)
        self.db.commit()

        with fml_testing.mock_sends(api.Message):
            expire_overrides_main()

        log.info.assert_has_calls([mock.call('Expiring %d buildroot overrides...', 1),
                                   mock.call('Expired bodhi-2.0-1.fc17')], any_order=True)
        assert buildrootoverride.expired_date is not None

    def test_exception(self, log):
        """
        Test the exception handling
        """
        buildrootoverride = self.db.query(models.BuildrootOverride).all()[0]
        buildrootoverride.expiration_date = buildrootoverride.expiration_date - timedelta(days=500)
        self.db.commit()
        log.info.side_effect = ValueError()

        expire_overrides_main()

        log.exception.assert_called_once()
