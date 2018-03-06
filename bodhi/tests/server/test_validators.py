# Copyright 2017 Red Hat, Inc.
# This file is part of bodhi.
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
"""This module contains tests for bodhi.server.validators."""
import unittest

import mock
from cornice.errors import Errors
from pyramid import exceptions

from bodhi.server import validators
from bodhi.tests.server.base import BaseTestCase
from bodhi.server import captcha, models


class TestValidateCSRFToken(BaseTestCase):
    """Test the validate_csrf_token() function."""
    def test_invalid_token(self):
        update = models.Update.query.one()
        """colander.Invalid should be raised if the CSRF token doesn't match."""
        comment = {'update': update.title, 'text': 'invalid CSRF', 'karma': 0,
                   'csrf_token': 'wrong_token'}

        # Surprisingly, using the wrong CSRF token gives a 404 code because it thinks the update is
        # also not found.
        r = self.app.post_json('/comments/', comment, status=404)

        expected_reponse = {
            u'status': u'error',
            u'errors': [
                {u'description':
                 (u'CSRF tokens do not match.  This happens if you have the page open for a long '
                  u'time. Please reload the page and try to submit your data again. Make sure to '
                  u'save your input somewhere before reloading. '),
                 u'location': u'body', u'name': u'csrf_token'},
                {u'description': u'Invalid update specified: None', u'location': u'url',
                 u'name': u'update'}]}
        self.assertEqual(r.json, expected_reponse)

    def test_valid_token(self):
        """No exception should be raised with a valid token."""
        update = models.Update.query.one()
        """colander.Invalid should be raised if the CSRF token doesn't match."""
        comment = {'update': update.title, 'text': 'invalid CSRF', 'karma': 0,
                   'csrf_token': self.get_csrf_token()}

        # This should not cause any error.
        self.app.post_json('/comments/', comment, status=200)


class TestGetValidRequirements(unittest.TestCase):
    """Test the _get_valid_requirements() function."""
    @mock.patch('bodhi.server.util.requests.get')
    def test__get_valid_requirements(self, get):
        """Test normal operation."""
        get.return_value.status_code = 200
        get.return_value.json.side_effect = [
            {'next': '/something?', 'data': [{'name': 'one'}, {'name': 'two'}]},
            {'next': None, 'data': []}]

        result = list(validators._get_valid_requirements(request=None,
                                                         requirements=['one', 'two']))

        self.assertEqual(result, ['one', 'two'])

    @mock.patch('bodhi.server.util.taskotron_results')
    def test_no_requirements(self, mock_taskotron_results):
        """Empty requirements means empty output"""
        result = list(validators._get_valid_requirements(request=None,
                                                         requirements=[]))

        mock_taskotron_results.assert_not_called()
        self.assertEqual(result, [])


@mock.patch.dict(
    'bodhi.server.validators.config',
    {'pagure_url': u'http://domain.local', 'admin_packager_groups': [u'provenpackager'],
     'mandatory_packager_groups': [u'packager']})
class TestValidateAcls(BaseTestCase):
    """ Test the validate_acls() function.
    """
    def get_mock_request(self):
        """
        A helper function that creates a mock request.
        :return: a Mock object representing a request
        """
        update = self.db.query(models.Update).filter_by(
            title=u'bodhi-2.0-1.fc17').one()
        user = self.db.query(models.User).filter_by(id=1).one()
        mock_request = mock.Mock()
        mock_request.user = user
        mock_request.db = self.db
        mock_request.errors = Errors()
        mock_request.validated = {'update': update}
        mock_request.buildinfo = {'bodhi-2.0-1.fc17': {}}
        return mock_request

    # Mocking the get_pkg_committers_from_pagure function because it will
    # simplify the overall number of mocks. This function is tested on its own
    # elsewhere.
    @mock.patch('bodhi.server.models.Package.get_pkg_committers_from_pagure',
                return_value=(['guest'], []))
    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': 'pagure'})
    def test_validate_acls_pagure(self, mock_gpcfp):
        """ Test validate_acls when the acl system is Pagure.
        """
        mock_request = self.get_mock_request()
        validators.validate_acls(mock_request)
        assert len(mock_request.errors) == 0, mock_request.errors
        mock_gpcfp.assert_called_once()

    @mock.patch('bodhi.server.models.Package.get_pkg_committers_from_pagure',
                return_value=(['tbrady'], []))
    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': 'pagure'})
    def test_validate_acls_pagure_proven_packager(self, mock_gpcfp):
        """ Test validate_acls when the acl system is Pagure when the user is
        a proven packager but doesn't have access through Pagure.
        """
        user = self.db.query(models.User).filter_by(id=1).one()
        group = self.db.query(models.Group).filter_by(
            name=u'provenpackager').one()
        user.groups.pop(0)
        user.groups.append(group)
        self.db.flush()
        mock_request = self.get_mock_request()
        validators.validate_acls(mock_request)
        assert len(mock_request.errors) == 0, mock_request.errors
        mock_gpcfp.assert_not_called()

    @mock.patch('bodhi.server.models.Package.get_pkg_committers_from_pagure',
                return_value=(['guest'], []))
    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': 'pagure'})
    def test_validate_acls_pagure_not_a_packager(self, mock_gpcfp):
        """ Test validate_acls when the acl system is Pagure when the user is
        not a packager but has access through Pagure. This should not be
        allowed.
        """
        user = self.db.query(models.User).filter_by(id=1).one()
        user.groups.pop(0)
        self.db.flush()
        mock_request = self.get_mock_request()
        validators.validate_acls(mock_request)
        error = [{
            'location': 'body',
            'name': 'builds',
            'description': ('guest is not a member of "packager", which is a '
                            'mandatory packager group')
        }]
        assert mock_request.errors == error, mock_request.errors
        mock_gpcfp.assert_not_called()

    @mock.patch('bodhi.server.models.Package.get_pkg_committers_from_pagure',
                return_value=(['tbrady'], []))
    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': 'pagure'})
    def test_validate_acls_pagure_no_commit_access(self, mock_gpcfp):
        """ Test validate_acls when the acl system is Pagure when the user is
        a packager but doesn't have access through Pagure.
        """
        mock_request = self.get_mock_request()
        validators.validate_acls(mock_request)
        error = [{
            'location': 'body',
            'name': 'builds',
            'description': 'guest does not have commit access to bodhi'
        }]
        assert mock_request.errors == error, mock_request.errors
        mock_gpcfp.assert_called_once()

    @mock.patch('bodhi.server.models.Package.get_pkg_committers_from_pagure',
                return_value=(['guest'], []))
    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': 'pagure'})
    def test_validate_acls_pagure_runtime_error(self, mock_gpcfp):
        """ Test validate_acls when the acl system is Pagure and a RuntimeError
        is raised.
        """
        mock_request = self.get_mock_request()
        mock_gpcfp.side_effect = RuntimeError('some error')
        validators.validate_acls(mock_request)
        assert len(mock_request.errors) == 1, mock_request.errors
        expected_error = [{
            'location': 'body',
            'name': 'builds',
            'description': 'some error'
        }]
        assert mock_request.errors == expected_error, mock_request.errors
        mock_gpcfp.assert_called_once()

    @mock.patch('bodhi.server.models.Package.get_pkg_committers_from_pagure',
                return_value=(['guest'], []))
    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': 'pagure'})
    def test_validate_acls_pagure_exception(self, mock_gpcfp):
        """ Test validate_acls when the acl system is Pagure and an exception
        that isn't a RuntimeError is raised.
        """
        mock_request = self.get_mock_request()
        mock_gpcfp.side_effect = ValueError('some error')
        validators.validate_acls(mock_request)
        assert len(mock_request.errors) == 1, mock_request.errors
        expected_error = [{
            'location': 'body',
            'name': 'builds',
            'description': ('Unable to access Pagure to check ACLs. Please '
                            'try again later.')
        }]
        assert mock_request.errors == expected_error, mock_request.errors
        mock_gpcfp.assert_called_once()

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': 'dummy'})
    def test_validate_acls_dummy(self):
        """ Test validate_acls when the acl system is dummy.
        """
        mock_request = self.get_mock_request()
        validators.validate_acls(mock_request)
        assert len(mock_request.errors) == 0, mock_request.errors

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': 'nonexistent'})
    def test_validate_acls_invalid_acl_system(self):
        """ Test validate_acls when the acl system is invalid.
        This will ensure that the user does not have rights.
        """
        mock_request = self.get_mock_request()
        validators.validate_acls(mock_request)
        error = [{
            'location': 'body',
            'name': 'builds',
            'description': 'guest does not have commit access to bodhi'
        }]
        assert mock_request.errors == error, mock_request.errors


class TestValidateCaptcha(BaseTestCase):
    """Test the validate_captcha() function."""

    @mock.patch.dict('bodhi.server.validators.config',
                     {'captcha.secret': '_fnIOv2bxXaz4FLECjUikl46VFn6HuJYzXjx_43XC1I='})
    def test_authenticated_user(self):
        """An authenticated user should not have to solve a captcha."""
        request = mock.Mock()
        request.errors = Errors()
        request.errors.status = None
        request.user = models.User.query.first()
        request.validated = {}

        validators.validate_captcha(request)

        self.assertEqual(request.errors, [])
        self.assertEqual(request.errors.status, None)

    @mock.patch.dict('bodhi.server.validators.config',
                     {'captcha.secret': '_fnIOv2bxXaz4FLECjUikl46VFn6HuJYzXjx_43XC1I='})
    def test_captcha_does_not_match_key(self):
        """Assert an error when the captcha in the session does not match the key."""
        request = mock.Mock()
        request.errors = Errors()
        request.session = {'captcha': 'some_other_key'}
        request.user = None
        request.validated = {'captcha_key': 'some_key', 'captcha_value': 'some_value'}

        validators.validate_captcha(request)

        self.assertEqual(
            request.errors,
            [{'location': 'cookies', 'name': 'captcha',
              'description': ("No captcha session cipher match (replay). 'some_other_key' "
                              "'some_key'")}])
        self.assertEqual(request.errors.status, exceptions.HTTPBadRequest.code)

    @mock.patch.dict('bodhi.server.validators.config',
                     {'captcha.secret': '_fnIOv2bxXaz4FLECjUikl46VFn6HuJYzXjx_43XC1I='})
    def test_captcha_validate_fail(self):
        """Assert an error when the captcha fails validation."""
        request = mock.Mock()
        request.errors = Errors()
        request.errors.status = None
        request.registry.settings = validators.config
        request.user = None
        # We'll cheat since we know the captcha.secret and figure out the solution.
        plainkey, value = captcha.math_generator(None, validators.config)
        cipherkey = captcha.encrypt(plainkey, validators.config)
        request.session = {'captcha': cipherkey}
        # By adding a 0 onto the end of the value, we are wrong by 100!
        request.validated = {'captcha_key': cipherkey, 'captcha_value': value + '0'}

        validators.validate_captcha(request)

        self.assertEqual(
            request.errors,
            [{'location': 'body', 'name': 'captcha_value',
              'description': 'Incorrect response to the captcha.'}])
        self.assertEqual(request.errors.status, exceptions.HTTPBadRequest.code)

    @mock.patch.dict('bodhi.server.validators.config',
                     {'captcha.secret': '_fnIOv2bxXaz4FLECjUikl46VFn6HuJYzXjx_43XC1I='})
    def test_captcha_validate_success(self):
        """Assert an error when the captcha fails validation."""
        request = mock.Mock()
        request.errors = Errors()
        request.errors.status = None
        request.registry.settings = validators.config
        request.user = None
        # We'll cheat since we know the captcha.secret and figure out the solution.
        plainkey, value = captcha.math_generator(None, validators.config)
        cipherkey = captcha.encrypt(plainkey, validators.config)
        request.session = {'captcha': cipherkey}
        request.validated = {'captcha_key': cipherkey, 'captcha_value': value}

        validators.validate_captcha(request)

        self.assertEqual(request.errors, [])
        self.assertEqual(request.errors.status, None)
        self.assertTrue('captcha' not in request.session)

    @mock.patch.dict('bodhi.server.validators.config', {'captcha.secret': ''})
    def test_captcha_not_configured(self):
        """Assert that no errors are noted if captcha is not configured."""
        request = mock.Mock()
        request.errors = Errors()
        request.errors.status = None
        request.user = None
        request.validated = {}

        validators.validate_captcha(request)

        self.assertEqual(request.errors, [])
        self.assertEqual(request.errors.status, None)

    @mock.patch.dict('bodhi.server.validators.config',
                     {'captcha.secret': '_fnIOv2bxXaz4FLECjUikl46VFn6HuJYzXjx_43XC1I='})
    def test_captcha_not_in_session(self):
        """Assert an error when the captcha isn't in the session."""
        request = mock.Mock()
        request.errors = Errors()
        request.session = {}
        request.user = None
        request.validated = {'captcha_key': 'some_key', 'captcha_value': 'some_value'}

        validators.validate_captcha(request)

        self.assertEqual(
            request.errors,
            [{'location': 'cookies', 'name': 'captcha',
              'description': 'Captcha cipher not in the session (replay).'}])
        self.assertEqual(request.errors.status, exceptions.HTTPBadRequest.code)

    @mock.patch.dict('bodhi.server.validators.config',
                     {'captcha.secret': '_fnIOv2bxXaz4FLECjUikl46VFn6HuJYzXjx_43XC1I='})
    def test_no_key(self):
        """Assert that an error is added to the request if the captcha key is missing."""
        request = mock.Mock()
        request.errors = Errors()
        request.user = None
        request.validated = {}

        validators.validate_captcha(request)

        self.assertEqual(
            request.errors,
            [{'location': 'body', 'name': 'captcha_key',
              'description': 'You must provide a captcha_key.'}])
        self.assertEqual(request.errors.status, exceptions.HTTPBadRequest.code)

    @mock.patch.dict('bodhi.server.validators.config',
                     {'captcha.secret': '_fnIOv2bxXaz4FLECjUikl46VFn6HuJYzXjx_43XC1I='})
    def test_no_value(self):
        """Assert that an error is added to the request if the captcha value is missing."""
        request = mock.Mock()
        request.errors = Errors()
        request.user = None
        request.validated = {'captcha_key': 'some_key'}

        validators.validate_captcha(request)

        self.assertEqual(
            request.errors,
            [{'location': 'body', 'name': 'captcha_value',
              'description': 'You must provide a captcha_value.'}])
        self.assertEqual(request.errors.status, exceptions.HTTPBadRequest.code)
