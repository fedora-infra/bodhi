# -*- coding: utf-8 -*-
# Copyright © 2017 Red Hat, Inc.
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
"""This module contains tests for bodhi.server.scripts.manage_releases."""
import unittest

from click import testing
import mock
import munch

from bodhi.server.scripts import manage_releases


EXAMPLE_RELEASE_MUNCH = munch.Munch({
    u'dist_tag': u'f27', u'name': u'F27', u'testing_tag': u'f27-updates-testing',
    u'pending_stable_tag': u'f27-updates-pending', u'pending_signing_tag': u'f27-signing-pending',
    u'long_name': u'Fedora 27', u'state': u'pending', u'version': u'27',
    u'override_tag': u'f27-override', u'branch': u'f27', u'id_prefix': u'FEDORA',
    u'pending_testing_tag': u'f27-updates-testing-pending', u'stable_tag': u'f27-updates',
    u'candidate_tag': u'f27-updates-candidate'})


EXPECTED_RELEASE_OUTPUT = """Saved release:
  Name:                F27
  Long Name:           Fedora 27
  Version:             27
  Branch:              f27
  ID Prefix:           FEDORA
  Dist Tag:            f27
  Stable Tag:          f27-updates
  Testing Tag:         f27-updates-testing
  Candidate Tag:       f27-updates-candidate
  Pending Signing Tag: f27-signing-pending
  Pending Testing Tag: f27-updates-testing-pending
  Pending Stable Tag:  f27-updates-pending
  Override Tag:        f27-override
  State:               pending
"""


class TestCreate(unittest.TestCase):
    """
    Test the create() function.
    """
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=EXAMPLE_RELEASE_MUNCH, autospec=True)
    def test_url_flag(self, send_request):
        """
        Assert correct behavior with the --url flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            manage_releases.create,
            ['--name', 'F27', '--url', 'http://localhost:6543', '--username', 'bowlofeggs',
             '--password', 's3kr3t'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, EXPECTED_RELEASE_OUTPUT)
        bindings_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(
            bindings_client, 'releases/', verb='POST', auth=True,
            data={'dist_tag': None, 'csrf_token': 'a_csrf_token', 'name': u'F27',
                  'testing_tag': None, 'pending_stable_tag': None, 'long_name': None, 'state': None,
                  'version': None, 'override_tag': None, 'branch': None, 'id_prefix': None,
                  'pending_testing_tag': None, 'stable_tag': None, 'candidate_tag': None})
        self.assertEqual(bindings_client.base_url, 'http://localhost:6543/')

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value={"errors": [{"description": "an error was encountered... :("}]},
                autospec=True)
    def test_create_with_errors(self, send_request):
        """
        Assert errors are printed if returned back in the request
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            manage_releases.create,
            ['--name', 'F27', '--url', 'http://localhost:6543', '--username', 'bowlofeggs',
             '--password', 's3kr3t'])

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.output, "ERROR: an error was encountered... :(\n")


class TestEdit(unittest.TestCase):
    """
    Test the edit() function.
    """
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=EXAMPLE_RELEASE_MUNCH, autospec=True)
    def test_url_flag(self, send_request):
        """
        Assert correct behavior with the --url flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            manage_releases.edit,
            ['--name', 'F27', '--long-name', 'Fedora 27, the Greatest Fedora!', '--url',
             'http://localhost:6543', '--username', 'bowlofeggs', '--password', 's3kr3t'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, EXPECTED_RELEASE_OUTPUT)
        bindings_client = send_request.mock_calls[0][1][0]
        self.assertEqual(send_request.call_count, 2)
        self.assertEqual(send_request.mock_calls[0],
                         mock.call(bindings_client, 'releases/F27', verb='GET', auth=True))
        self.assertEqual(
            send_request.mock_calls[1],
            mock.call(
                bindings_client, 'releases/', verb='POST', auth=True,
                data={'dist_tag': 'f27', 'csrf_token': 'a_csrf_token', 'name': 'F27',
                      'testing_tag': 'f27-updates-testing', 'edited': 'F27',
                      'pending_stable_tag': 'f27-updates-pending',
                      'pending_signing_tag': 'f27-signing-pending',
                      'long_name': 'Fedora 27, the Greatest Fedora!', 'state': 'pending',
                      'version': '27', 'override_tag': 'f27-override', 'branch': 'f27',
                      'id_prefix': 'FEDORA', 'pending_testing_tag': 'f27-updates-testing-pending',
                      'stable_tag': 'f27-updates', 'candidate_tag': 'f27-updates-candidate'}))
        self.assertEqual(bindings_client.base_url, 'http://localhost:6543/')

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=EXAMPLE_RELEASE_MUNCH, autospec=True)
    def test_new_name_flag(self, send_request):
        """
        Assert correct behavior with the --new-name flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            manage_releases.edit,
            ['--name', 'F27', '--new-name', 'fedora27', '--url',
             'http://localhost:6543', '--username', 'bowlofeggs', '--password', 's3kr3t'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, EXPECTED_RELEASE_OUTPUT)
        bindings_client = send_request.mock_calls[0][1][0]
        self.assertEqual(send_request.call_count, 2)
        self.assertEqual(send_request.mock_calls[0],
                         mock.call(bindings_client, 'releases/F27', verb='GET', auth=True))
        self.assertEqual(
            send_request.mock_calls[1],
            mock.call(
                bindings_client, 'releases/', verb='POST', auth=True,
                data={'dist_tag': 'f27', 'csrf_token': 'a_csrf_token', 'name': 'fedora27',
                      'testing_tag': 'f27-updates-testing', 'edited': 'F27',
                      'pending_stable_tag': 'f27-updates-pending',
                      'pending_signing_tag': 'f27-signing-pending',
                      'long_name': 'Fedora 27', 'state': 'pending',
                      'version': '27', 'override_tag': 'f27-override', 'branch': 'f27',
                      'id_prefix': 'FEDORA', 'pending_testing_tag': 'f27-updates-testing-pending',
                      'stable_tag': 'f27-updates', 'candidate_tag': 'f27-updates-candidate'}))

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request')
    def test_edit_no_name_provided(self, send_request):
        """
        Assert we print an error and no request is sent if a --name is not provided.
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            manage_releases.edit,
            ['--long-name', 'Fedora 27, the Greatest Fedora!', '--url',
             'http://localhost:6543', '--username', 'bowlofeggs', '--password', 's3kr3t'])

        self.assertEqual(result.output, "ERROR: Please specify the name of the release to edit\n")
        send_request.assert_not_called()

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value={"errors": [{"description": "an error was encountered... :("}]},
                autospec=True)
    def test_edit_with_errors(self, send_request):
        """
        Assert errors are printed if returned back in the request
        """
        runner = testing.CliRunner()

        result = runner.invoke(
            manage_releases.edit,
            ['--name', 'F27', '--long-name', 'Fedora 27, the Greatest Fedora!', '--url',
             'http://localhost:6543', '--username', 'bowlofeggs', '--password', 's3kr3t'])

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.output, "ERROR: an error was encountered... :(\n")


class TestInfo(unittest.TestCase):
    """
    Test the info() function.
    """
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=EXAMPLE_RELEASE_MUNCH, autospec=True)
    def test_url_flag(self, send_request):
        """
        Assert correct behavior with the --url flag.
        """
        runner = testing.CliRunner()

        result = runner.invoke(manage_releases.info, ['--url', 'http://localhost:6543', 'F27'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, EXPECTED_RELEASE_OUTPUT.replace('Saved r', 'R'))
        bindings_client = send_request.mock_calls[0][1][0]
        send_request.assert_called_once_with(bindings_client, 'releases/F27', verb='GET',
                                             auth=False)
        self.assertEqual(bindings_client.base_url, 'http://localhost:6543/')

    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value={"errors": [{"description": "an error was encountered... :("}]},
                autospec=True)
    def test_info_with_errors(self, send_request):
        """
        Assert errors are printed if returned back in the request
        """
        runner = testing.CliRunner()

        result = runner.invoke(manage_releases.info, ['--url', 'http://localhost:6543', 'F27'])

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.output, "ERROR: an error was encountered... :(\n")
