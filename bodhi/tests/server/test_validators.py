# -*- coding: utf-8 -*-
# Copyright © 2017-2018 Red Hat, Inc.
#
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
import datetime
import unittest

import mock
from cornice.errors import Errors
from pyramid import exceptions

from bodhi.tests.server.base import BaseTestCase
from bodhi.server import buildsys, captcha, config, models, validators


class TestValidateCSRFToken(BaseTestCase):
    """Test the validate_csrf_token() function."""
    def test_invalid_token(self):
        update = models.Update.query.one()
        """colander.Invalid should be raised if the CSRF token doesn't match."""
        comment = {'update': update.title, 'text': 'invalid CSRF', 'karma': 0,
                   'csrf_token': 'wrong_token'}

        r = self.app.post_json('/comments/', comment, status=400)

        expected_reponse = {
            u'status': u'error',
            u'errors': [
                {u'description':
                 (u'CSRF tokens do not match.  This happens if you have the page open for a long '
                  u'time. Please reload the page and try to submit your data again. Make sure to '
                  u'save your input somewhere before reloading. '),
                 u'location': u'body', u'name': u'csrf_token'}]}
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

    @mock.patch('bodhi.server.models.Package.get_pkg_committers_from_pagure',
                return_value=([], ['infra-sig']))
    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': 'pagure'})
    def test_allowed_via_group(self, gpcfp):
        """Ensure that packagers can be allowed via group membership."""
        user = self.db.query(models.User).filter_by(id=1).one()
        group = models.Group(name='infra-sig')
        self.db.add(group)
        user.groups.append(group)
        request = self.get_mock_request()

        validators.validate_acls(request)

        self.assertEqual(len(request.errors), 0)
        gpcfp.assert_called_once_with()

    @mock.patch('bodhi.server.models.Package.get_pkg_pushers',
                return_value=((['guest'], []), ([], [])))
    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': 'pkgdb'})
    def test_pkgdb_allowed(self, get_pkg_pushers):
        """Test the integration with pkgdb."""
        request = self.get_mock_request()

        validators.validate_acls(request)

        self.assertEqual(len(request.errors), 0)
        get_pkg_pushers.assert_called_once_with('f17', config.config)

    @mock.patch('bodhi.server.models.Package.get_pkg_pushers',
                return_value=(([], []), (['some_group_guest_is_not_in'], [])))
    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': 'pkgdb'})
    def test_pkgdb_disallowed(self, get_pkg_pushers):
        """Test the integration with pkgdb."""
        request = self.get_mock_request()

        validators.validate_acls(request)

        error = [{'location': 'body', 'name': 'builds',
                  'description': 'guest does not have commit access to bodhi'}]
        self.assertEqual(request.errors, error)
        get_pkg_pushers.assert_called_once_with('f17', config.config)

    def test_unable_to_infer_content_type(self):
        """Test the error handler for when Bodhi cannot determine the content type of a build."""
        request = self.get_mock_request()
        request.koji = buildsys.get_session()
        request.validated = {'builds': [b.nvr for b in models.Build.query.all()]}

        with mock.patch('bodhi.server.validators.ContentType.infer_content_class',
                        side_effect=IOError('oh no')):
            validators.validate_acls(request)

        self.assertEqual(
            request.errors,
            [{'location': 'body', 'name': 'builds',
              'description': "Unable to infer content_type.  'oh no'"}])
        self.assertEqual(request.errors.status, 400)

    def test_unable_to_infer_content_type_not_implemented(self):
        """Test error handler when Bodhi can't determine the content type due to NotImplemented."""
        request = self.get_mock_request()
        request.koji = buildsys.get_session()
        request.validated = {'builds': [b.nvr for b in models.Build.query.all()]}

        with mock.patch('bodhi.server.validators.ContentType.infer_content_class',
                        side_effect=NotImplementedError('oh no')):
            validators.validate_acls(request)

        self.assertEqual(
            request.errors,
            [{'location': 'body', 'name': 'builds',
              'description': "Unable to infer content_type.  'oh no'"}])
        self.assertEqual(request.errors.status, 501)

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

    @mock.patch.dict('bodhi.server.validators.config',
                     {'acl_system': 'dummy', 'acl_dummy_committer': 'mattia'})
    def test_validate_acls_dummy_committer(self):
        """ Test validate_acls when the acl system is dummy and a user
        adds himself to the committers list by the development.ini file.
        """
        user = self.db.query(models.User).filter_by(id=1).one()
        user.name = 'mattia'
        self.db.flush()
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


class TestValidateBugFeedback(BaseTestCase):
    """Test the validate_bug_feedback() function."""

    def test_invalid(self):
        """An invalid bug should add an error to the request."""
        request = mock.Mock()
        request.db = self.db
        request.errors = Errors()
        request.validated = {'bug_feedback': [{'bug_id': 'invalid'}],
                             'update': models.Update.query.first()}

        validators.validate_bug_feedback(request)

        self.assertEqual(
            request.errors,
            [{'location': 'querystring', 'name': 'bug_feedback',
              'description': 'Invalid bug ids specified: invalid'}])
        self.assertEqual(request.errors.status, exceptions.HTTPBadRequest.code)

    def test_no_feedbacks(self):
        """Nothing to do if no feedback."""
        request = mock.Mock()
        request.db = self.db
        request.errors = Errors()
        request.validated = {'update': models.Update.query.first()}

        validators.validate_bug_feedback(request)

        self.assertEqual(
            request.errors,
            [])


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


class TestValidateCommentId(BaseTestCase):
    """Test the validate_comment_id() function."""

    def test_invalid(self):
        """An invalid comment_id should add an error to the request."""
        request = mock.Mock()
        request.errors = Errors()
        request.matchdict = {'id': '42'}

        validators.validate_comment_id(request)

        self.assertEqual(
            request.errors,
            [{'location': 'url', 'name': 'id',
              'description': 'Invalid comment id'}])
        self.assertEqual(request.errors.status, exceptions.HTTPNotFound.code)


class TestValidateExpirationDate(BaseTestCase):
    """Test the validate_expiration_date() function."""

    def test_none(self):
        """An expiration_date of None should be OK."""
        request = mock.Mock()
        request.errors = Errors()
        request.validated = {'expiration_date': None}

        validators.validate_expiration_date(request)

        self.assertEqual(len(request.errors), 0)

    def test_past(self):
        """An expiration_date in the past should make it sad."""
        request = mock.Mock()
        request.errors = Errors()
        request.validated = {
            'expiration_date': datetime.datetime.utcnow() - datetime.timedelta(days=1)}

        validators.validate_expiration_date(request)

        self.assertEqual(
            request.errors,
            [{'location': 'body', 'name': 'expiration_date',
              'description': 'Expiration date in the past'}])
        self.assertEqual(request.errors.status, exceptions.HTTPBadRequest.code)


class TestValidateOverrideBuild(BaseTestCase):
    """Test the validate_override_build() function."""

    def test_no_build_exception(self):
        """Assert exception handling when the build is not found and koji is unavailable."""
        request = mock.Mock()
        request.db = self.db
        request.errors = Errors()
        request.koji.listTags.side_effect = IOError('You forgot to pay your ISP.')
        request.validated = {'edited': None}

        validators._validate_override_build(request, 'does not exist', self.db)

        self.assertEqual(
            request.errors,
            [{'location': 'body', 'name': 'nvr',
              'description': ("Couldn't determine koji tags for does not exist, 'You forgot to pay "
                              "your ISP.'")}])
        self.assertEqual(request.errors.status, exceptions.HTTPBadRequest.code)

    def test_indeterminate_release(self):
        """If a build does not have tags that identify a Release, the validator should complain."""
        request = mock.Mock()
        request.db = self.db
        request.errors = Errors()
        request.koji.listTags.return_value = [{'name': 'invalid'}]
        request.validated = {'edited': None}
        build = models.Build.query.first()
        build.release = None
        self.db.commit()

        validators._validate_override_build(request, build.nvr, self.db)

        self.assertEqual(
            request.errors,
            [{'location': 'body', 'name': 'nvr',
              'description': "Invalid build.  Couldn't determine release from koji tags."}])
        build = models.Build.query.filter_by(nvr=build.nvr).one()
        self.assertIsNone(build.release)
        self.assertEqual(request.errors.status, exceptions.HTTPBadRequest.code)

    def test_no_release(self):
        """If a build does not have a Release, the validator should set one."""
        release = models.Release.query.first()
        request = mock.Mock()
        request.db = self.db
        request.errors = Errors()
        request.koji.listTags.return_value = [{'name': release.candidate_tag}]
        request.validated = {'edited': None}
        build = models.Build.query.first()
        build.release = None
        self.db.commit()

        validators._validate_override_build(request, build.nvr, self.db)

        self.assertEqual(len(request.errors), 0)
        build = models.Build.query.filter_by(nvr=build.nvr).one()
        self.assertEqual(build.release.name, release.name)

    @mock.patch('bodhi.server.models.buildsys.get_session')
    def test_wrong_tag(self, get_session):
        """If a build does not have a canditate or testing tag, the validator should complain."""
        release = models.Release.query.first()
        request = mock.Mock()
        request.db = self.db
        request.errors = Errors()
        request.koji.listTags.return_value = [{'name': release.stable_tag}]
        request.validated = {'edited': None}
        get_session.return_value.listTags.return_value = request.koji.listTags.return_value
        build = models.Build.query.first()

        validators._validate_override_build(request, build.nvr, self.db)

        self.assertEqual(
            request.errors,
            [{'location': 'body', 'name': 'nvr',
              'description': "Invalid build.  It must be tagged as either candidate or testing."}])
        self.assertEqual(request.errors.status, exceptions.HTTPBadRequest.code)

    def test_test_gating_status_is_failed(self):
        """If a build's test gating status is failed, the validator should complain."""
        request = mock.Mock()
        request.db = self.db
        request.errors = Errors()
        request.validated = {'edited': None}
        build = models.Build.query.first()
        build.update.test_gating_status = models.TestGatingStatus.failed
        self.db.commit()

        validators._validate_override_build(request, build.nvr, self.db)

        self.assertEqual(
            request.errors,
            [{'location': 'body', 'name': 'nvr',
              'description': "Cannot create a buildroot override if build's "
                             "test gating status is failed."}])
        self.assertEqual(request.errors.status, exceptions.HTTPBadRequest.code)


class TestValidateOverrideBuilds(BaseTestCase):
    """Test the validate_override_builds() function."""

    def test_invalid_nvrs_given(self):
        """If the request has invalid nvrs, it should add an error to the request."""
        request = mock.Mock()
        request.db = self.db
        request.errors = Errors()
        request.koji.listTags.return_value = [{'name': 'invalid'}]
        request.validated = {'nvr': 'invalid'}

        validators.validate_override_builds(request)

        self.assertEqual(
            request.errors,
            [{'location': 'body', 'name': 'nvr',
              'description': 'Invalid build'}])
        self.assertEqual(request.errors.status, exceptions.HTTPBadRequest.code)

    def test_no_nvrs_given(self):
        """If the request has no nvrs, it should add an error to the request."""
        request = mock.Mock()
        request.db = self.db
        request.errors = Errors()
        request.validated = {'nvr': ''}

        validators.validate_override_builds(request)

        self.assertEqual(
            request.errors,
            [{'location': 'body', 'name': 'nvr',
              'description': 'A comma-separated list of NVRs is required.'}])
        self.assertEqual(request.errors.status, exceptions.HTTPBadRequest.code)


class TestValidateRelease(BaseTestCase):
    """Test the validate_release() function."""

    def test_invalid(self):
        """An invalid release should add an error to the request."""
        request = mock.Mock()
        request.db = self.db
        request.errors = Errors()
        request.validated = {'release': 'invalid'}

        validators.validate_release(request)

        self.assertEqual(
            request.errors,
            [{'location': 'querystring', 'name': 'release',
              'description': 'Invalid release specified: invalid'}])
        self.assertEqual(request.errors.status, exceptions.HTTPBadRequest.code)


class TestValidateTestcaseFeedback(BaseTestCase):
    """Test the validate_testcase_feedback() function."""

    def test_invalid(self):
        """An invalid testcase should add an error to the request."""
        request = mock.Mock()
        request.db = self.db
        request.errors = Errors()
        request.validated = {'testcase_feedback': [{'testcase_name': 'invalid'}],
                             'update': models.Update.query.first()}

        validators.validate_testcase_feedback(request)

        self.assertEqual(
            request.errors,
            [{'location': 'querystring', 'name': 'testcase_feedback',
              'description': 'Invalid testcase names specified: invalid'}])
        self.assertEqual(request.errors.status, exceptions.HTTPBadRequest.code)

    def test_no_feedbacks(self):
        """Nothing to do if no feedback."""
        request = mock.Mock()
        request.db = self.db
        request.errors = Errors()
        request.validated = {'update': models.Update.query.first()}

        validators.validate_testcase_feedback(request)

        self.assertEqual(
            request.errors,
            [])

    def test_update_not_found(self):
        """It should 404 if the update is not found."""
        request = mock.Mock()
        request.errors = Errors()
        request.validated = {'testcase_feedback': [{'testcase_name': 'invalid'}], 'update': None}

        validators.validate_testcase_feedback(request)

        self.assertEqual(
            request.errors,
            [{'location': 'url', 'name': 'id',
              'description': 'Invalid update'}])
        self.assertEqual(request.errors.status, exceptions.HTTPNotFound.code)
