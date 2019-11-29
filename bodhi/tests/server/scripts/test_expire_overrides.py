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
This module contains tests for the bodhi.server.scripts.expire_overrides module.
"""
from datetime import timedelta
from io import StringIO
from unittest import mock

from fedora_messaging import api, testing as fml_testing

from bodhi.server import models
from bodhi.server.scripts import expire_overrides
from bodhi.tests.server.base import BasePyTestCase


class TestUsage:
    """
    This class contains tests for the usage() function.
    """
    @mock.patch('sys.exit')
    @mock.patch('sys.stdout.write')
    def test_usage(self, write, exit):
        """
        Test that the right output and exit code are generated.
        """
        argv = ['/usr/bin/bodhi-expire-overrides']

        expire_overrides.usage(argv)

        message = ''.join([c[1][0] for c in write.mock_calls])
        assert message == \
            ('usage: bodhi-expire-overrides <config_uri>\n(example: "bodhi-expire-overrides '
             'development.ini")\n')
        exit.assert_called_once_with(1)


class TestMain(BasePyTestCase):
    """
    This class contains tests for the main() function.
    """
    @mock.patch('sys.exit')
    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_invalid_arguments(self, stdout, exit):
        """
        Assert that the usage message is returned to the user if not exactly 2 arguments are given
        """
        with mock.patch('bodhi.server.scripts.expire_overrides.initialize_db'):
            with mock.patch('bodhi.server.scripts.expire_overrides.get_appsettings',
                            return_value=''):
                with mock.patch('bodhi.server.scripts.expire_overrides.setup_logging'):
                    expire_overrides.main(['expire_overrides', 'some_config.ini', 'testnoses'])

        assert stdout.getvalue() == \
            'usage: expire_overrides <config_uri>\n(example: "expire_overrides development.ini")\n'
        exit.assert_called_once_with(1)

    @mock.patch('bodhi.server.scripts.expire_overrides.logging.Logger.info')
    def test_no_expire(self, log_info):
        """
        Assert that we don't expire a buildroot override with an expiration date in the future
        """
        buildrootoverride = self.db.query(models.BuildrootOverride).all()[0]
        buildrootoverride.expiration_date = buildrootoverride.expiration_date + timedelta(days=500)
        self.db.commit()

        with mock.patch('bodhi.server.scripts.expire_overrides.initialize_db'):
            with mock.patch('bodhi.server.scripts.expire_overrides.get_appsettings',
                            return_value=''):
                with mock.patch('bodhi.server.scripts.expire_overrides.setup_logging'):
                    expire_overrides.main(['expire_overrides', 'some_config.ini'])

        log_info.assert_called_once_with("No active buildroot override to expire")
        buildrootoverride = self.db.query(models.BuildrootOverride).all()[0]
        assert buildrootoverride.expired_date is None

    @mock.patch('bodhi.server.scripts.expire_overrides.logging.Logger.info')
    def test_expire(self, log_info):
        """
        Assert that we expire a buildroot override with an expiration date in the past
        """
        buildrootoverride = self.db.query(models.BuildrootOverride).all()[0]
        buildrootoverride.expiration_date = buildrootoverride.expiration_date - timedelta(days=500)
        self.db.commit()

        with mock.patch('bodhi.server.scripts.expire_overrides.initialize_db'):
            with mock.patch('bodhi.server.scripts.expire_overrides.get_appsettings',
                            return_value=''):
                with mock.patch('bodhi.server.scripts.expire_overrides.setup_logging'):
                    with fml_testing.mock_sends(api.Message):
                        expire_overrides.main(['expire_overrides', 'some_config.ini'])

        log_info.assert_has_calls([mock.call('Expiring %d buildroot overrides...', 1),
                                   mock.call('Expired bodhi-2.0-1.fc17')], any_order=True)
        assert buildrootoverride.expired_date is not None

    @mock.patch('sys.exit')
    @mock.patch('bodhi.server.scripts.expire_overrides.logging.Logger.error')
    def test_exception(self, log_error, exit):
        """
        Test the exception handling
        """
        buildrootoverride = self.db.query(models.BuildrootOverride).all()[0]
        buildrootoverride.expiration_date = buildrootoverride.expiration_date - timedelta(days=500)
        self.db.commit()

        with mock.patch('bodhi.server.scripts.expire_overrides.initialize_db'):
            with mock.patch('bodhi.server.scripts.expire_overrides.get_appsettings',
                            return_value=''):
                with mock.patch('bodhi.server.scripts.expire_overrides.setup_logging'):
                    with mock.patch('bodhi.server.scripts.expire_overrides.logging.Logger.info',
                                    side_effect=ValueError()):
                        expire_overrides.main(['expire_overrides', 'some_config.ini'])

        log_error.assert_called_once()
        exit.assert_called_once_with(1)
