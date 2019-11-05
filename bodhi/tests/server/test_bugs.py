# Copyright © 2007-2019 Red Hat, Inc. and others.
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
"""This test suite contains tests for bodhi.server.bugs."""

from unittest import mock
import xmlrpc.client

from bodhi.server import bugs, models


class TestBugzilla:
    """This test class contains tests for the Bugzilla class."""
    def test___init__(self):
        """Assert that the __init__ method sets up the Bugzilla object correctly."""
        bz = bugs.Bugzilla()

        assert bz._bz is None

    @mock.patch('bodhi.server.bugs.bugzilla.Bugzilla.__init__', return_value=None)
    def test__connect_with_api_key(self, __init__):
        """Test the _connect() method when the config contains an api_key."""
        bz = bugs.Bugzilla()
        patch_config = {'bz_server': 'https://example.com/bz', 'bugzilla_api_key': 'api_key'}

        with mock.patch.dict('bodhi.server.bugs.config', patch_config):
            bz._connect()

        __init__.assert_called_once_with(url='https://example.com/bz', api_key='api_key',
                                         cookiefile=None, tokenfile=None)

    @mock.patch('bodhi.server.bugs.bugzilla.Bugzilla.__init__', return_value=None)
    def test__connect_with_creds(self, __init__):
        """Test the _connect() method when the config contains credentials."""
        bz = bugs.Bugzilla()
        patch_config = {'bodhi_email': 'bodhi@example.com', 'bodhi_password': 'bodhi_secret',
                        'bz_server': 'https://example.com/bz'}

        with mock.patch.dict('bodhi.server.bugs.config', patch_config):
            bz._connect()

        __init__.assert_called_once_with(url='https://example.com/bz', user='bodhi@example.com',
                                         password='bodhi_secret', cookiefile=None, tokenfile=None)

    @mock.patch('bodhi.server.bugs.bugzilla.Bugzilla.__init__', return_value=None)
    def test__connect_with_creds_and_api_key(self, __init__):
        """Test the _connect() method when the config contains credentials and an api_key."""
        bz = bugs.Bugzilla()
        patch_config = {'bodhi_email': 'bodhi@example.com', 'bodhi_password': 'bodhi_secret',
                        'bz_server': 'https://example.com/bz', 'bugzilla_api_key': 'api_key'}

        with mock.patch.dict('bodhi.server.bugs.config', patch_config):
            bz._connect()

        # Using an API key should cause the credentials to be ignored.
        __init__.assert_called_once_with(url='https://example.com/bz', api_key='api_key',
                                         cookiefile=None, tokenfile=None)

    @mock.patch('bodhi.server.bugs.bugzilla.Bugzilla.__init__', return_value=None)
    def test__connect_without_creds(self, __init__):
        """Test the _connect() method when the config does not contain credentials."""
        bz = bugs.Bugzilla()
        patch_config = {'bz_server': 'https://example.com/bz'}

        with mock.patch.dict('bodhi.server.bugs.config', patch_config):
            bz._connect()

        __init__.assert_called_once_with(url='https://example.com/bz',
                                         cookiefile=None, tokenfile=None)

    @mock.patch('bodhi.server.bugs.bugzilla.Bugzilla.__init__', return_value=None)
    def test_bz_with__bz_None(self, __init__):
        """
        Assert correct behavior of the bz() method when _bz is None.
        """
        bz = bugs.Bugzilla()
        patch_config = {'bz_server': 'https://example.com/bz'}

        with mock.patch.dict('bodhi.server.bugs.config', patch_config):
            return_value = bz.bz

        __init__.assert_called_once_with(url='https://example.com/bz',
                                         cookiefile=None, tokenfile=None)
        assert return_value is bz._bz

    @mock.patch('bodhi.server.bugs.Bugzilla._connect')
    def test_bz_with__bz_set(self, _connect):
        """
        Assert correct behavior of the bz() method when _bz is already set.
        """
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()

        return_value = bz.bz

        assert return_value is bz._bz
        assert _connect.call_count == 0

    @mock.patch('bodhi.server.bugs.log.error')
    @mock.patch.dict('bodhi.server.bugs.config', {'bz_products': 'aproduct'})
    def test_close_fault(self, error):
        """Assert that an xmlrpc Fault is caught and logged by close()."""
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.return_value.product = 'aproduct'
        bz._bz.getbug.return_value.close.side_effect = xmlrpc.client.Fault(
            410, 'You must log in before using this part of Red Hat Bugzilla.')

        # This should not raise an Exception.
        bz.close(12345, {'bodhi': 'bodhi-3.1.0-1.fc27'}, 'whabam!')

        error.assert_called_once_with(
            'Got fault from Bugzilla on #%d: fault code: %d, fault string: %s',
            12345, 410, 'You must log in before using this part of Red Hat Bugzilla.',
            exc_info=True)

    @mock.patch('bodhi.server.bugs.log.info')
    @mock.patch.dict('bodhi.server.bugs.config', {'bz_products': 'aproduct'})
    def test_close_successful(self, info):
        """Test the close() method with a success case."""
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.return_value.component = 'bodhi'
        bz._bz.getbug.return_value.product = 'aproduct'

        bz.close(12345, {'bodhi': 'bodhi-3.1.0-1.fc27'},
                 'Fixed. Closing bug and adding version to fixed_in field.')

        bz._bz.getbug.assert_called_once_with(12345)
        bz._bz.getbug.return_value.close.assert_called_once_with(
            'ERRATA',
            comment='Fixed. Closing bug and adding version to fixed_in field.',
            fixedin='bodhi-3.1.0-1.fc27')
        assert info.call_count == 0

    @mock.patch('bodhi.server.bugs.log.info')
    @mock.patch.dict('bodhi.server.bugs.config', {'bz_products': 'aproduct'})
    def test_close_fixedin_maxlength(self, info):
        """Test the close() method when fixed_in field may go over 255 chars."""
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.return_value.component = 'bodhi'
        bz._bz.getbug.return_value.product = 'aproduct'
        fill_text = ' '.join(['exactly-10', ] * 23)
        bz._bz.getbug.return_value.fixed_in = fill_text

        bz.close(12345, {'bodhi': 'bodhi-3.1.0-1.fc27'},
                 'Closing, but don\'t modify fixed_in field to not cross 255 chars limit.')

        bz._bz.getbug.assert_called_once_with(12345)
        bz._bz.getbug.return_value.close.assert_called_once_with(
            'ERRATA',
            comment='Closing, but don\'t modify fixed_in field to not cross 255 chars limit.')
        assert info.call_count == 0

    @mock.patch('bodhi.server.bugs.log.info')
    @mock.patch.dict('bodhi.server.bugs.config', {'bz_products': 'aproduct'})
    def test_close_pre_existing_fixedin(self, info):
        """Test the close() method at the edge of the allowed size of the fixedin field (254)."""
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.return_value.component = 'bodhi'
        bz._bz.getbug.return_value.product = 'aproduct'
        fill_text = ' '.join(['exactly-10', ] * 21)
        bz._bz.getbug.return_value.fixed_in = fill_text

        bz.close(12345, {'bodhi': 'bodhi-35.103.109-1.fc27'},
                 'Fixed. Closing bug and adding version to fixed_in field.')

        bz._bz.getbug.assert_called_once_with(12345)
        expected_fixedin = '{} bodhi-35.103.109-1.fc27'.format(fill_text)
        assert len(expected_fixedin) == 254
        bz._bz.getbug.return_value.close.assert_called_once_with(
            'ERRATA',
            comment='Fixed. Closing bug and adding version to fixed_in field.',
            fixedin=expected_fixedin)
        assert info.call_count == 0

    @mock.patch('bodhi.server.bugs.log.info')
    def test_close_private_bug(self, info):
        """close() should gracefully handle private bugs."""
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.side_effect = xmlrpc.client.Fault(
            102,
            ('You are not authorized to access bug #1563797. To see this bug, you must first log in'
             'to an account with the appropriate permissions.'))

        bz.close(1563797, {'bodhi': 'bodhi-35.103.109-1.fc27'},
                 'Fixed. Closing bug and adding version to fixed_in field.')

        bz._bz.getbug.assert_called_once_with(1563797)
        info.assert_called_once_with(
            'Cannot retrieve private bug #%d.', 1563797)

    @mock.patch('bodhi.server.bugs.log.info')
    def test_close_product_skipped(self, info):
        """Test the close() method when the bug's product is not in the bz_products config."""
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.return_value.product = 'not fedora!'

        bz.close(12345, {'bodhi': 'bodhi-35.103.109-1.fc27'},
                 'Fixed. Closing bug and adding version to fixed_in field.')

        bz._bz.getbug.assert_called_once_with(12345)
        info.assert_called_once_with("Skipping set closed on 'not fedora!' bug #12345")
        assert bz._bz.getbug.return_value.setstatus.call_count == 0

    @mock.patch('bodhi.server.bugs.log.exception')
    def test_comment_fault(self, exception):
        """comment() should gracefully handle Bugzilla faults."""
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.side_effect = xmlrpc.client.Fault(
            42, 'The meaning')

        bz.comment(1563797, 'Bodhi has fixed all of your bugs.')

        bz._bz.getbug.assert_called_once_with(1563797)
        exception.assert_called_once_with(
            'Got fault from Bugzilla on #%d: fault code: %d, fault string: %s', 1563797, 42,
            'The meaning')

    @mock.patch('bodhi.server.bugs.log.info')
    def test_comment_private_bug(self, info):
        """comment() should gracefully handle private bugs."""
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.side_effect = xmlrpc.client.Fault(
            102,
            ('You are not authorized to access bug #1563797. To see this bug, you must first log in'
             'to an account with the appropriate permissions.'))

        bz.comment(1563797, 'Bodhi has fixed all of your bugs.')

        bz._bz.getbug.assert_called_once_with(1563797)
        info.assert_called_once_with(
            'Cannot retrieve private bug #%d.', 1563797)

    @mock.patch('bodhi.server.bugs.log.info')
    def test_comment_successful(self, info):
        """Test the comment() method with a success case."""
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()

        bz.comment(1411188, 'A nice message.')

        bz._bz.getbug.assert_called_once_with(1411188)
        bz._bz.getbug.return_value.addcomment.assert_called_once_with('A nice message.')
        # No exceptions should have been logged
        assert info.call_count == 0

    @mock.patch('bodhi.server.bugs.log.error')
    def test_comment_too_long(self, error):
        """Assert that the comment() method gets angry if the comment is too long."""
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        oh_my = 'All work aind no play makes bowlofeggs a dull… something something… '
        long_comment = oh_my * (65535 // len(oh_my) + 1)

        bz.comment(1411188, long_comment)

        assert bz._bz.getbug.call_count == 0
        # An exception should have been logged
        error.assert_called_once_with(
            'Comment too long for bug #1411188:  {}'.format(long_comment))

    @mock.patch('bodhi.server.bugs.log.error')
    def test_comment_too_many_attempts(self, error):
        """Assert that only 5 attempts are made to comment before giving up."""
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.return_value.addcomment.side_effect = \
            xmlrpc.client.Fault(
                42,
                'Someone turned the microwave on and now the WiFi is down.'
            )

        bz.comment(1411188, 'A nice message.')

        bz._bz.getbug.assert_called_once_with(1411188)
        assert len(bz._bz.getbug.return_value.addcomment.mock_calls) == 5
        assert all(c[1] == ('A nice message.',)
                   for c in bz._bz.getbug.return_value.addcomment.mock_calls)

        # Five exceptions should have been logged
        assert len(error.mock_calls) == 5
        assert all(c[1] == ('\nA fault has occurred \nFault code: 42 \nFault string: '
                            'Someone turned the microwave on and now the WiFi is down.',)
                   for c in error.mock_calls)

    @mock.patch('bodhi.server.bugs.log.exception')
    def test_comment_unexpected_exception(self, exception):
        """Test the comment() method with an unexpected Exception."""
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.return_value.addcomment.side_effect = Exception(
            'Ran out of internet fluid, please refill.')

        bz.comment(1411188, 'A nice message.')

        bz._bz.getbug.assert_called_once_with(1411188)
        bz._bz.getbug.return_value.addcomment.assert_called_once_with('A nice message.')
        exception.assert_called_once_with('Unable to add comment to bug #1411188')

    def test_getbug(self):
        """
        Assert correct behavior on the getbug() method.
        """
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()

        return_value = bz.getbug(1411188)

        assert return_value is bz._bz.getbug.return_value
        bz._bz.getbug.assert_called_once_with(1411188)

    @mock.patch('bodhi.server.bugs.log.info')
    @mock.patch.dict('bodhi.server.bugs.config', {'bz_products': 'aproduct'})
    def test_modified(self, info):
        """Ensure correct execution of the modified() method."""
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.return_value.product = 'aproduct'
        bz._bz.getbug.return_value.bug_status = 'NEW'

        bz.modified(1411188, 'A mean message.')

        bz._bz.getbug.assert_called_once_with(1411188)
        info.assert_called_once_with("Setting bug #1411188 status to MODIFIED")
        bz._bz.getbug.return_value.setstatus.assert_called_once_with('MODIFIED',
                                                                     comment='A mean message.')

    @mock.patch.dict('bodhi.server.bugs.config', {'bz_products': 'aproduct'})
    def test_modified_after_verified(self):
        """Test the modified() method when the status of bug is VERIFIED."""
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.return_value.product = 'aproduct'
        bz._bz.getbug.return_value.bug_status = 'VERIFIED'

        bz.modified(1411188, 'A mean message.')

        bz._bz.getbug.assert_called_once_with(1411188)
        bz._bz.getbug.return_value.addcomment.assert_called_once_with('A mean message.')

    @mock.patch('bodhi.server.bugs.log.exception')
    def test_modified_fault(self, exception):
        """modified() should gracefully handle Bugzilla faults."""
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.side_effect = xmlrpc.client.Fault(
            42, 'The meaning')

        bz.modified(1563797, 'Bodhi has fixed all of your bugs.')

        bz._bz.getbug.assert_called_once_with(1563797)
        exception.assert_called_once_with(
            'Got fault from Bugzilla on #%d: fault code: %d, fault string: %s', 1563797, 42,
            'The meaning')

    @mock.patch('bodhi.server.bugs.log.info')
    def test_modified_private_bug(self, info):
        """modified() should gracefully handle private bugs."""
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.side_effect = xmlrpc.client.Fault(
            102,
            ('You are not authorized to access bug #1563797. To see this bug, you must first log in'
             'to an account with the appropriate permissions.'))

        bz.modified(1563797, 'Bodhi has fixed all of your bugs.')

        bz._bz.getbug.assert_called_once_with(1563797)
        info.assert_called_once_with(
            'Cannot retrieve private bug #%d.', 1563797)

    @mock.patch('bodhi.server.bugs.log.info')
    def test_modified_product_skipped(self, info):
        """Test the modified() method when the bug's product is not in the bz_products config."""
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.return_value.product = 'not fedora!'

        bz.modified(1411188, 'A mean message.')

        bz._bz.getbug.assert_called_once_with(1411188)
        info.assert_called_once_with("Skipping set modified on 'not fedora!' bug #1411188")
        assert bz._bz.getbug.return_value.setstatus.call_count == 0

    @mock.patch('bodhi.server.bugs.log.exception')
    def test_modified_exception(self, exception_log):
        """Test the modified() method logs an exception if encountered"""
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.side_effect = Exception()

        bz.modified(1411188, 'A mean message.')

        bz._bz.getbug.assert_called_once_with(1411188)
        exception_log.assert_called_once_with("Unable to alter bug #1411188")
        assert bz._bz.getbug.return_value.setstatus.call_count == 0

    @mock.patch('bodhi.server.bugs.log.exception')
    def test_update_details_exception(self, mock_exceptionlog):
        """Test we log an exception if update_details raises one"""
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.side_effect = Exception()

        bz.update_details(0, 0)

        mock_exceptionlog.assert_called_once_with('Unknown exception from Bugzilla')

    def test_update_details_keywords_str(self):
        """Assert that we split the keywords into a list when they are a str."""
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bug = mock.MagicMock()
        bug.keywords = 'some words but sEcuriTy is in the middle of them'
        bug_entity = models.Bug()

        bz.update_details(bug, bug_entity)

        assert bug_entity.security is True

    def test_update_details_parent_bug(self):
        """Assert that a parent bug gets marked as such."""
        bz = bugs.Bugzilla()
        bug = mock.MagicMock()
        bug.product = 'Security Response'
        bug.short_desc = 'Fedora gets you, good job guys!'
        bug_entity = mock.MagicMock()
        bug_entity.bug_id = 1419157

        bz.update_details(bug, bug_entity)

        assert bug_entity.parent is True
        assert bug_entity.title == 'Fedora gets you, good job guys!'

    @mock.patch('bodhi.server.bugs.log.info')
    def test_update_details_private_bug(self, info):
        """update_details() should gracefully handle private bugs."""
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.side_effect = xmlrpc.client.Fault(
            102,
            ('You are not authorized to access bug #1563797. To see this bug, you must first log in'
             'to an account with the appropriate permissions.'))
        bug = mock.MagicMock()
        bug.bug_id = 1563797

        bz.update_details(None, bug)

        assert bug.title == 'Private bug'
        bz._bz.getbug.assert_called_once_with(1563797)
        info.assert_called_once_with(
            'Cannot retrieve private bug #%d.', 1563797)

    @mock.patch('bodhi.server.bugs.log.error')
    def test_update_details_xmlrpc_fault(self, error):
        """Test we log an error if update_details raises one"""
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.side_effect = xmlrpc.client.Fault(42, 'You found the meaning.')
        bug = mock.MagicMock()
        bug.bug_id = 123

        bz.update_details(0, bug)

        assert bug.title == 'Invalid bug number'
        bz._bz.getbug.assert_called_once_with(123)
        error.assert_called_once_with(
            'Got fault from Bugzilla on #%d: fault code: %d, fault string: %s', 123, 42,
            'You found the meaning.', exc_info=True)

    @mock.patch('bodhi.server.bugs.log.exception')
    @mock.patch.dict('bodhi.server.bugs.config', {'bz_products': 'aproduct'})
    def test_on_qa_failure(self, exception):
        """
        Test the on_qa() method with a failure case.
        """
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.return_value.product = 'aproduct'
        bz._bz.getbug.return_value.setstatus.side_effect = Exception(
            'You forgot to pay your oxygen bill. Your air supply will promptly be severed.')

        bz.on_qa(1411188, 'A mean message.')

        bz._bz.getbug.assert_called_once_with(1411188)
        bz._bz.getbug.return_value.setstatus.assert_called_once_with('ON_QA',
                                                                     comment='A mean message.')
        exception.assert_called_once_with('Unable to alter bug #1411188')

    @mock.patch('bodhi.server.bugs.log.exception')
    def test_on_qa_fault(self, exception):
        """on_qa() should gracefully handle Bugzilla faults."""
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.side_effect = xmlrpc.client.Fault(
            42, 'The meaning')

        bz.on_qa(1563797, 'Bodhi has fixed all of your bugs.')

        bz._bz.getbug.assert_called_once_with(1563797)
        exception.assert_called_once_with(
            'Got fault from Bugzilla on #%d: fault code: %d, fault string: %s', 1563797, 42,
            'The meaning')

    @mock.patch('bodhi.server.bugs.log.info')
    def test_on_qa_private_bug(self, info):
        """on_qa() should gracefully handle private bugs."""
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.side_effect = xmlrpc.client.Fault(
            102,
            ('You are not authorized to access bug #1563797. To see this bug, you must first log in'
             'to an account with the appropriate permissions.'))

        bz.on_qa(1563797, 'Bodhi has fixed all of your bugs.')

        bz._bz.getbug.assert_called_once_with(1563797)
        info.assert_called_once_with(
            'Cannot retrieve private bug #%d.', 1563797)

    @mock.patch('bodhi.server.bugs.log.info')
    @mock.patch.dict('bodhi.server.bugs.config', {'bz_products': 'aproduct'})
    def test_on_qa_success(self, info):
        """
        Test the on_qa() method with a success case.
        """
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.return_value.product = 'aproduct'

        bz.on_qa(1411188, 'A message.')

        bz._bz.getbug.assert_called_once_with(1411188)
        bz._bz.getbug.return_value.setstatus.assert_called_once_with('ON_QA', comment='A message.')
        assert info.call_count == 0

    @mock.patch('bodhi.server.bugs.log.info')
    @mock.patch.dict('bodhi.server.bugs.config', {'bz_products': 'aproduct'})
    def test_on_qa_skipped_because_closed(self, info):
        """
        Test the on_qa() method when the bug is already CLOSED.
        It must not change bug state, only post the comment.
        """
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.return_value.product = 'aproduct'
        bz._bz.getbug.return_value.bug_status = 'CLOSED'

        bz.on_qa(1411188, 'A message.')

        bz._bz.getbug.assert_called_once_with(1411188)
        bz._bz.getbug.return_value.addcomment.assert_called_once_with('A message.')
        bz._bz.getbug.return_value.setstatus.assert_not_called()
        assert info.call_count == 0

    @mock.patch('bodhi.server.bugs.log.info')
    @mock.patch.dict('bodhi.server.bugs.config', {'bz_products': 'aproduct'})
    def test_on_qa_skipped_because_verified(self, info):
        """
        Test the on_qa() method when the bug is already VERIFIED.
        It must not change bug state, only post the comment.
        """
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.return_value.product = 'aproduct'
        bz._bz.getbug.return_value.bug_status = 'VERIFIED'

        bz.on_qa(1411188, 'A message.')

        bz._bz.getbug.assert_called_once_with(1411188)
        bz._bz.getbug.return_value.addcomment.assert_called_once_with('A message.')
        bz._bz.getbug.return_value.setstatus.assert_not_called()
        assert info.call_count == 0

    @mock.patch('bodhi.server.bugs.log.info')
    @mock.patch.dict('bodhi.server.bugs.config', {'bz_products': 'aproduct'})
    def test_on_qa_skipped_because_already_set(self, info):
        """
        Test the on_qa() method when the bug is already ON_QA.
        It must not be set again ON_QA, only post the comment.
        """
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.return_value.product = 'aproduct'
        bz._bz.getbug.return_value.bug_status = 'ON_QA'

        bz.on_qa(1411188, 'A message.')

        bz._bz.getbug.assert_called_once_with(1411188)
        bz._bz.getbug.return_value.addcomment.assert_called_once_with('A message.')
        bz._bz.getbug.return_value.setstatus.assert_not_called()
        assert info.call_count == 0

    @mock.patch('bodhi.server.bugs.log.info')
    def test_on_qa_product_skipped(self, info):
        """Test the on_qa() method when the bug's product is not in the bz_products config."""
        bz = bugs.Bugzilla()
        bz._bz = mock.MagicMock()
        bz._bz.getbug.return_value.product = 'not fedora!'

        bz.on_qa(1411188, 'A message.')

        bz._bz.getbug.assert_called_once_with(1411188)
        info.assert_called_once_with("Skipping set on_qa on 'not fedora!' bug #1411188")
        assert bz._bz.getbug.return_value.setstatus.call_count == 0


class TestFakeBugTracker:
    """This test class contains tests for the FakeBugTracker class."""
    def test_getbug(self):
        """Ensure correct return value of the getbug() method."""
        bt = bugs.FakeBugTracker()

        b = bt.getbug(1234)

        assert isinstance(b, bugs.FakeBug)
        assert b.bug_id == 1234

    @mock.patch('bodhi.server.bugs.log.debug')
    def test___noop__(self, debug):
        """Assert correct behavior from the __noop__ method."""
        bt = bugs.FakeBugTracker()

        bt.__noop__(1, 2)

        debug.assert_called_once_with('__noop__((1, 2))')


class TestSetBugtracker:
    """
    Test the set_bugtracker() function.
    """
    @mock.patch('bodhi.server.bugs.bugtracker', None)
    @mock.patch.dict('bodhi.server.bugs.config', {'bugtracker': 'bugzilla'})
    def test_config_bugzilla(self):
        """
        Test when the config is set for bugzilla to be the bugtracker.
        """
        bugs.set_bugtracker()

        assert isinstance(bugs.bugtracker, bugs.Bugzilla)

    @mock.patch('bodhi.server.bugs.bugtracker', None)
    @mock.patch.dict('bodhi.server.bugs.config', {'bugtracker': 'fake'})
    def test_config_not_bugzilla(self):
        """
        Test when the config is no set for bugzilla to be the bugtracker.
        """
        bugs.set_bugtracker()

        assert isinstance(bugs.bugtracker, bugs.FakeBugTracker)
