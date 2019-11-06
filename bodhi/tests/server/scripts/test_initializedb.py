# Copyright © 2017-2019 Red Hat, Inc.
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
"""Contains tests for the bodhi.server.scripts.initializedb module."""

from io import StringIO
from unittest import mock

import pytest

from bodhi.server.scripts import initializedb


class TestMain:
    """Contains tests for the main() function."""
    @mock.patch.object(initializedb.Base, 'metadata', mock.MagicMock())
    @mock.patch('bodhi.server.scripts.initializedb.get_appsettings')
    @mock.patch('bodhi.server.scripts.initializedb.initialize_db')
    @mock.patch('bodhi.server.scripts.initializedb.setup_logging')
    def test_successful_usage(self, setup_logging, initialize_db, get_appsettings):
        """Assert correct behavior when the right arguments are supplied."""
        initializedb.main(argv=['initializedb', '/etc/bodhi/production.ini'])

        setup_logging.assert_called_once_with()
        get_appsettings.assert_called_once_with('/etc/bodhi/production.ini')
        initialize_db.assert_called_once_with(get_appsettings.return_value)
        assert initializedb.Base.metadata.bind == initialize_db.return_value
        initializedb.Base.metadata.create_all.assert_called_once_with(initialize_db.return_value)

    @mock.patch.object(initializedb.Base, 'metadata', mock.MagicMock())
    @mock.patch('bodhi.server.scripts.initializedb.get_appsettings')
    @mock.patch('bodhi.server.scripts.initializedb.initialize_db')
    @mock.patch('bodhi.server.scripts.initializedb.setup_logging')
    @mock.patch('bodhi.server.scripts.initializedb.sys.exit',
                side_effect=RuntimeError('program exited'))
    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_wrong_args(self, stdout, exit, setup_logging, initialize_db, get_appsettings):
        """Assert that usage() gets called if the wrong number of args are supplied."""
        pytest.raises(
            RuntimeError, initializedb.main,
            argv=['initializedb', '/etc/bodhi/production.ini', 'this does not belong'])

        assert stdout.getvalue() == \
            'usage: initializedb <config_uri>\n(example: "initializedb development.ini")\n'
        exit.assert_called_once_with(1)
        # None of the other stuff should have happened since we bailed out.
        assert setup_logging.call_count == 0
        assert initialize_db.call_count == 0
        assert get_appsettings.call_count == 0


class TestUsage:
    """Contains tests for the usage() function."""
    @mock.patch('bodhi.server.scripts.initializedb.sys.exit')
    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_usage(self, stdout, exit):
        """Assert correct behavior of the usage() function."""
        initializedb.usage(['initializedb'])

        assert stdout.getvalue() == \
            'usage: initializedb <config_uri>\n(example: "initializedb development.ini")\n'
        exit.assert_called_once_with(1)
