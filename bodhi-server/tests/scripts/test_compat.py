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
"""This module contains tests for the compatibility scripts."""

from unittest.mock import patch, Mock

from click.testing import CliRunner

from bodhi.server.scripts import compat
from ..base import BasePyTestCase


# Don't muck around with global log level.
@patch('bodhi.server.scripts.compat.logging.basicConfig',
       new=lambda *p, **k: None)
class TestCompat(BasePyTestCase):
    """This class contains tests for the compatibility scripts."""

    def setup_method(self, method):
        super().setup_method(method)
        self.task_result = Mock(name="task_result")
        self.task_mock = Mock(name="task")
        self.task_mock.delay.return_value = self.task_result

    def test_approve_testing(self):
        """Ensure the approve_testing task is called."""
        cli = CliRunner()
        with patch('bodhi.server.tasks.approve_testing_task', self.task_mock):
            result = cli.invoke(compat.approve_testing)
        assert result.exit_code == 0
        self.task_mock.delay.assert_called_with()
        self.task_result.get.assert_called_with(propagate=True)

    def test_check_policies(self):
        """Ensure the check_policies task is called."""
        cli = CliRunner()
        with patch('bodhi.server.tasks.check_policies_task', self.task_mock):
            result = cli.invoke(compat.check_policies)
        assert result.exit_code == 0
        self.task_mock.delay.assert_called_with()
        self.task_result.get.assert_called_with(propagate=True)

    def test_clean_old_composes(self):
        """Ensure the clean_old_composes task is called."""
        cli = CliRunner()
        with patch('bodhi.server.tasks.clean_old_composes_task', self.task_mock):
            result = cli.invoke(compat.clean_old_composes)
        assert result.exit_code == 0
        self.task_mock.delay.assert_called_with(num_to_keep=10)
        self.task_result.get.assert_called_with(propagate=True)

    def test_expire_overrides(self):
        """Ensure the expire_overrides task is called."""
        cli = CliRunner()
        with patch('bodhi.server.tasks.expire_overrides_task', self.task_mock):
            result = cli.invoke(compat.expire_overrides)
        assert result.exit_code == 0
        self.task_mock.delay.assert_called_with()
        self.task_result.get.assert_called_with(propagate=True)

    def test_propagate_exceptions(self):
        """Ensure the exceptions cause the script to exit with a non-zero status."""
        self.task_result.get.side_effect = RuntimeError("Kaboom!")
        cli = CliRunner()
        with patch('bodhi.server.tasks.expire_overrides_task', self.task_mock):
            result = cli.invoke(compat.expire_overrides)
        assert result.exit_code == 1
        assert "Kaboom!" in result.output

    @patch("bodhi.server.scripts.compat.get_appsettings")
    @patch("bodhi.server.scripts.compat.config")
    def test_arg_config_uri(self, config, get_appsettings):
        """Ensure the path to the configuration file can be passed."""
        get_appsettings.return_value = {"foo": "bar"}
        cli = CliRunner()
        with patch('bodhi.server.tasks.expire_overrides_task', self.task_mock):
            result = cli.invoke(compat.expire_overrides, ["test-config.ini"])
        assert result.exit_code == 0
        get_appsettings.assert_called_with("test-config.ini")
        config.load_config.assert_called_with({"foo": "bar"})

    def test_no_result_backend(self):
        """Ensure we don't crash when no result backend has been set."""
        cli = CliRunner()
        # mock.patch.dict() fails because the conf object is too complex, mock manually:
        import bodhi.server.tasks
        app = bodhi.server.tasks.app
        old_result_backend = app.conf.result_backend
        app.conf.result_backend = None

        try:
            with patch('bodhi.server.tasks.expire_overrides_task', self.task_mock):
                result = cli.invoke(compat.expire_overrides)
        finally:
            app.conf.result_backend = old_result_backend

        assert result.exit_code == 0
        self.task_mock.delay.assert_called_with()
        self.task_result.get.assert_not_called()
        assert result.output.strip() == (
            "No result backend have been configured in Celery, "
            "I cannot wait for the task to complete."
        )
