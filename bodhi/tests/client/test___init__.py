# -*- coding: utf-8 -*-

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
"""This module contains tests for bodhi.client."""

import unittest

from click import testing
import fedora.client
import mock

from bodhi import client
from bodhi.tests import client as client_test_data


EXAMPLE_UPDATE_OUTPUT = u"""================================================================================
     bodhi-2.2.4-1.el7
================================================================================
  Update ID: FEDORA-EPEL-2016-3081a94111
    Release: Fedora EPEL 7
     Status: stable
       Type: bugfix
      Karma: 0
  Autokarma: True  [-3, 3]
      Notes: Update to 2.2.4. Release notes available at https://github.com
           : /fedora-infra/bodhi/releases/tag/2.2.4
  Submitter: bowlofeggs
  Submitted: 2016-10-05 18:10:22
   Comments: bodhi - 2016-10-05 18:10:22 (karma 0)
             This update has been submitted for testing by
             bowlofeggs.
             bodhi - 2016-10-05 18:10:27 (karma 0)
             This update has obsoleted [bodhi-2.2.3-1.el7](https://
             bodhi.fedoraproject.org/updates/FEDORA-
             EPEL-2016-a0eb4cc41f), and has inherited its bugs and
             notes.

  http://example.com/tests/updates/FEDORA-EPEL-2016-3081a94111

"""


class TestRequest(unittest.TestCase):
    """
    This class tests the request() function.
    """
    @mock.patch('bodhi.client.bindings.BodhiClient.__init__', return_value=None)
    @mock.patch.object(client.bindings.BodhiClient, 'base_url', 'http://example.com/tests/',
                       create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH)
    def test_successful_operation(self, send_request, __init__):
        """
        Assert that a successful operation is handled properly.
        """
        runner = testing.CliRunner()

        result = runner.invoke(client.request, ['bodhi-2.2.4-1.el7', 'revoke', '--user',
                                                'some_user', '--password', 's3kr3t'])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, EXAMPLE_UPDATE_OUTPUT)
        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-1.el7/request', verb='POST', auth=True,
            data={'csrf_token': 'a_csrf_token', 'request': u'revoke',
                  'update': u'bodhi-2.2.4-1.el7'})
        __init__.assert_called_once_with(username='some_user', password='s3kr3t', staging=False)

    @mock.patch('bodhi.client.bindings.BodhiClient.__init__', return_value=None)
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                side_effect=fedora.client.ServerError(
                    url='http://example.com/tests/updates/bodhi-2.2.4-99.el7/request', status=404,
                    msg='update not found'))
    def test_update_not_found(self, send_request, __init__):
        """
        Assert that request() transforms a bodhi.client.bindings.UpdateNotFound into a
        click.BadParameter so that the user gets a nice error message.
        """
        runner = testing.CliRunner()

        result = runner.invoke(client.request, ['bodhi-2.2.4-99.el7', 'revoke', '--user',
                                                'some_user', '--password', 's3kr3t'])

        self.assertEqual(result.exit_code, 2)
        self.assertEqual(
            result.output,
            (u'Usage: request [OPTIONS] UPDATE STATE\n\nError: Invalid value for UPDATE: Update not'
             u' found: bodhi-2.2.4-99.el7\n'))
        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-99.el7/request', verb='POST', auth=True,
            data={'csrf_token': 'a_csrf_token', 'request': u'revoke',
                  'update': u'bodhi-2.2.4-99.el7'})
        __init__.assert_called_once_with(username='some_user', password='s3kr3t', staging=False)
