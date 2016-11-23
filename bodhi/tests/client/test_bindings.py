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
"""This module contains tests for bodhi.client.bindings."""

import unittest

import fedora.client
import mock

from bodhi.client import bindings
from bodhi.tests import client as client_test_data


class TestBodhiClient_Resource(unittest.TestCase):
    """
    This class contains tests for BodhiClient.resource().
    """
    @mock.patch('bodhi.client.bindings.BodhiClient.__init__', return_value=None)
    @mock.patch.object(bindings.BodhiClient, 'base_url', 'http://example.com/tests/',
                       create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                side_effect=fedora.client.ServerError(
                    url='http://example.com/tests/updates/bodhi-2.2.4-99.el7/request', status=404,
                    msg='update not found'))
    def test_404_error(self, send_request, __init__):
        """
        Test for the case when the server returns a 404 error code.
        """
        client = bindings.BodhiClient(username='some_user', password='s3kr3t', staging=False)

        with self.assertRaises(bindings.UpdateNotFound) as exc:
            client.request('bodhi-2.2.4-1.el7', 'revoke')

            self.assertEqual(exc.update, 'bodhi-2.2.4-1.el7')

        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-1.el7/request', verb='POST', auth=True,
            data={'csrf_token': 'a_csrf_token', 'request': u'revoke',
                  'update': u'bodhi-2.2.4-1.el7'})
        __init__.assert_called_once_with(username='some_user', password='s3kr3t', staging=False)

    @mock.patch('bodhi.client.bindings.BodhiClient.__init__', return_value=None)
    @mock.patch.object(bindings.BodhiClient, 'base_url', 'http://example.com/tests/',
                       create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request',
                return_value=client_test_data.EXAMPLE_UPDATE_MUNCH)
    def test_successful_request(self, send_request, __init__):
        """
        Test with a successful request.
        """
        client = bindings.BodhiClient(username='some_user', password='s3kr3t', staging=False)

        response = client.request('bodhi-2.2.4-1.el7', 'revoke')

        self.assertEqual(response, client_test_data.EXAMPLE_UPDATE_MUNCH)
        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-1.el7/request', verb='POST', auth=True,
            data={'csrf_token': 'a_csrf_token', 'request': u'revoke',
                  'update': u'bodhi-2.2.4-1.el7'})
        __init__.assert_called_once_with(username='some_user', password='s3kr3t', staging=False)

    @mock.patch('bodhi.client.bindings.BodhiClient.__init__', return_value=None)
    @mock.patch.object(bindings.BodhiClient, 'base_url', 'http://example.com/tests/',
                       create=True)
    @mock.patch('bodhi.client.bindings.BodhiClient.csrf',
                mock.MagicMock(return_value='a_csrf_token'))
    @mock.patch('bodhi.client.bindings.BodhiClient.send_request')
    def test_other_ServerError(self, send_request, __init__):
        """
        Test for the case when a non-404 ServerError is raised.
        """
        server_error = fedora.client.ServerError(
            url='http://example.com/tests/updates/bodhi-2.2.4-99.el7/request', status=500,
            msg='Internal server error')
        send_request.side_effect = server_error
        client = bindings.BodhiClient(username='some_user', password='s3kr3t', staging=False)

        with self.assertRaises(fedora.client.ServerError) as exc:
            client.request('bodhi-2.2.4-1.el7', 'revoke')

            self.assertTrue(exc is server_error)

        send_request.assert_called_once_with(
            'updates/bodhi-2.2.4-1.el7/request', verb='POST', auth=True,
            data={'csrf_token': 'a_csrf_token', 'request': u'revoke',
                  'update': u'bodhi-2.2.4-1.el7'})
        __init__.assert_called_once_with(username='some_user', password='s3kr3t', staging=False)


class TestUpdateNotFound(unittest.TestCase):
    """
    This class tests the UpdateNotFound class.
    """
    def test___init__(self):
        """
        Assert that __init__() works properly.
        """
        exc = bindings.UpdateNotFound('bodhi-2.2.4-1.el7')

        self.assertEqual(exc.update, u'bodhi-2.2.4-1.el7')
        self.assertEqual(type(exc.update), unicode)

    def test___unicode__(self):
        """
        Assert that __unicode__() works properly.
        """
        exc = bindings.UpdateNotFound('bodhi-2.2.4-1.el7')

        self.assertEqual(unicode(exc.update), u'bodhi-2.2.4-1.el7')
        self.assertEqual(type(unicode(exc.update)), unicode)
