# Copyright © 2017-2019 Red Hat, Inc.
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
from unittest import mock
import datetime
import unittest

from cornice.errors import Errors
from fedora_messaging import api, testing as fml_testing
import koji
from pyramid import exceptions
import pytest

from bodhi.tests.server.base import BasePyTestCase, BaseTestCase
from bodhi.server import buildsys, models, validators
from bodhi.server.exceptions import BodhiException


class TestValidateCSRFToken(BaseTestCase):
    """Test the validate_csrf_token() function."""
    def test_invalid_token(self):
        update = models.Update.query.one()
        """colander.Invalid should be raised if the CSRF token doesn't match."""
        comment = {'update': update.title, 'text': 'invalid CSRF', 'karma': 0,
                   'csrf_token': 'wrong_token'}

        r = self.app.post_json('/comments/', comment, status=400)

        expected_response = {
            'status': 'error',
            'errors': [
                {'description':
                 ('CSRF tokens do not match.  This happens if you have the page open for a long '
                  'time. Please reload the page and try to submit your data again. Make sure to '
                  'save your input somewhere before reloading. '),
                 'location': 'body', 'name': 'csrf_token'}]}
        self.assertEqual(r.json, expected_response)

    def test_valid_token(self):
        """No exception should be raised with a valid token."""
        update = models.Update.query.one()
        """colander.Invalid should be raised if the CSRF token doesn't match."""
        comment = {'update': update.alias, 'text': 'invalid CSRF', 'karma': 0,
                   'csrf_token': self.get_csrf_token()}

        # This should not cause any error.
        with fml_testing.mock_sends(api.Message):
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
    {'pagure_url': 'http://domain.local', 'admin_packager_groups': ['provenpackager'],
     'mandatory_packager_groups': ['packager']})
class TestValidateAcls(BaseTestCase):
    """ Test the validate_acls() function.
    """
    def get_mock_request(self):
        """
        A helper function that creates a mock request.
        :return: a Mock object representing a request
        """
        update = self.db.query(models.Build).filter_by(
            nvr='bodhi-2.0-1.fc17').one().update
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
        self.assertEqual(len(mock_request.errors), 0)
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
            name='provenpackager').one()
        user.groups.pop(0)
        user.groups.append(group)
        self.db.flush()
        mock_request = self.get_mock_request()
        validators.validate_acls(mock_request)
        self.assertEqual(len(mock_request.errors), 0)
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
        self.assertEqual(mock_request.errors, error)
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
        self.assertEqual(mock_request.errors, error)
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
        self.assertEqual(len(mock_request.errors), 1)
        expected_error = [{
            'location': 'body',
            'name': 'builds',
            'description': 'some error'
        }]
        self.assertEqual(mock_request.errors, expected_error)
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
        self.assertEqual(len(mock_request.errors), 1)
        expected_error = [{
            'location': 'body',
            'name': 'builds',
            'description': ('Unable to access Pagure to check ACLs. Please '
                            'try again later.')
        }]
        self.assertEqual(mock_request.errors, expected_error)
        mock_gpcfp.assert_called_once()

    @mock.patch.dict('bodhi.server.validators.config', {'acl_system': 'dummy'})
    def test_validate_acls_dummy(self):
        """ Test validate_acls when the acl system is dummy.
        """
        mock_request = self.get_mock_request()
        validators.validate_acls(mock_request)
        self.assertEqual(len(mock_request.errors), 0)

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
        self.assertEqual(len(mock_request.errors), 0)

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
        self.assertEqual(mock_request.errors, error)


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
        """If a build does not have a candidate or testing tag, the validator should complain."""
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

    def test_release_with_no_override_tag(self):
        """If the request has a build associated to a release with no override tag,
        it should add an error to the request."""

        build = self.db.query(models.Build).filter_by(
            nvr='bodhi-2.0-1.fc17').first()

        build.release.override_tag = ""
        self.db.commit()

        request = mock.Mock()
        request.db = self.db
        request.errors = Errors()
        request.validated = {'nvr': 'bodhi-2.0-1.fc17', 'edited': False}

        validators.validate_override_builds(request)

        self.assertEqual(
            request.errors,
            [{'location': 'body', 'name': 'nvr',
              'description': 'Cannot create a buildroot override because the'
                             ' release associated with the build does not support it.'}])
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


class TestValidateBuildsOrFromTagExist(BasePyTestCase):
    """Test the validate_builds_or_from_tag_exist() function."""

    def setup_method(self, method):
        """Sets up the environment for each test method call."""
        super().setup_method(method)

        self.request = mock.Mock()
        self.request.db = self.db
        self.request.errors = Errors()
        self.request.validated = {}

    def test_valid_builds(self):
        """A request with valid builds should pass without errors."""
        self.request.validated['builds'] = ['foo-1-1.fc30']

        validators.validate_builds_or_from_tag_exist(self.request)

        assert len(self.request.errors) == 0

    def test_invalid_builds(self):
        """A request with wrongly typed builds should add an error."""
        self.request.validated['builds'] = 'foo-1-1.fc30'

        validators.validate_builds_or_from_tag_exist(self.request)

        assert self.request.errors == [
            {'location': 'body', 'name': 'builds',
             'description': 'The builds parameter must be a list.'}
        ]

    def test_valid_from_tag(self):
        """A request with valid from_tag should pass without errors."""
        self.request.validated['from_tag'] = 'f30-something-side-tag'

        validators.validate_builds_or_from_tag_exist(self.request)

        assert len(self.request.errors) == 0

    def test_invalid_from_tag(self):
        """A request with wrongly typed from_tag should add an error."""
        self.request.validated['from_tag'] = ['f30-something-side-tag']

        validators.validate_builds_or_from_tag_exist(self.request)

        assert self.request.errors == [
            {'location': 'body', 'name': 'from_tag',
             'description': 'The from_tag parameter must be a string.'}
        ]

    def test_missing(self):
        """A request without `builds` or `from_tag` should add an error."""
        validators.validate_builds_or_from_tag_exist(self.request)

        assert self.request.errors == [
            {'location': 'body', 'name': 'builds,from_tag',
             'description': "You must specify either builds or from_tag."}
        ]

    def test_empty_builds(self):
        """An empty list of builds should add an error to the request."""
        self.request.validated['builds'] = []

        validators.validate_builds_or_from_tag_exist(self.request)

        assert self.request.errors == [
            {'location': 'body', 'name': 'builds',
             'description': "You may not specify an empty list of builds."}
        ]

    def test_empty_from_tag(self):
        """An empty from_tag should add an error to the request."""
        self.request.validated['from_tag'] = ""

        validators.validate_builds_or_from_tag_exist(self.request)

        assert self.request.errors == [
            {'location': 'body', 'name': 'from_tag',
             'description': "You may not specify an empty from_tag."}
        ]


class TestValidateFromTag(BasePyTestCase):
    """Test the validate_from_tag() function."""

    class UnknownTagDevBuildsys(buildsys.DevBuildsys):

        def listTagged(self, tag, *args, **kwargs):
            raise koji.GenericError(f"Invalid tagInfo: {tag!r}")

        def getTag(self, tag, **kwargs):
            return None

    class NoBuildsDevBuildsys(buildsys.DevBuildsys):

        def listTagged(self, tag, *args, **kwargs):
            return []

    class UnknownKojiGenericError(buildsys.DevBuildsys):

        def listTagged(self, tag, *args, **kwargs):
            raise koji.GenericError("foo")

    @classmethod
    def mock_get_session_for_class(cls, buildsys_cls):
        def mock_get_session():
            return buildsys_cls()
        return mock_get_session

    def setup_method(self, method):
        """Sets up the environment for each test method call."""
        super().setup_method(method)

        self.request = mock.Mock()
        self.request.db = self.db
        self.request.errors = Errors()
        self.request.validated = {'from_tag': 'f17-updates-candidate'}

    # Successful validations

    def test_known_with_builds(self):
        """Test with known from_tag and with builds set in request.validated.

        This test expects that builds_from_tag is set to False after calling
        the validator."""
        self.request.validated['builds'] = ['foo-1-1']

        validators.validate_from_tag(self.request)

        assert self.request.validated['builds_from_tag'] == False
        assert not self.request.errors

    def test_known_without_builds(self):
        """Test with known from_tag but without builds in request.validated.

        This test expects that builds_from_tag is set to True, and builds are
        filled after calling the validator."""
        validators.validate_from_tag(self.request)

        assert self.request.validated['builds_from_tag'] == True
        assert len(self.request.validated['builds'])
        assert not self.request.errors

    def test_without_from_tag(self):
        """Test without from_tag supplied.

        This makes the validator a no-op."""
        del self.request.validated['from_tag']

        validators.validate_from_tag(self.request)

    # Error conditions

    def test_known_with_empty_builds(self):
        """Test with known from_tag but with empty builds in request.validated.

        This test expects an appropriate error to be added."""
        with mock.patch('bodhi.server.validators.buildsys.get_session',
                        self.mock_get_session_for_class(self.NoBuildsDevBuildsys)):
            validators.validate_from_tag(self.request)

        assert self.request.errors == [
            {'location': 'body', 'name': 'from_tag',
             'description': "The supplied from_tag doesn't contain any builds."}
        ]

    def test_unknown_with_builds(self):
        """An unknown from_tag should add an error to the request.

        This test runs with a list of fills in request.validated."""
        self.request.validated['builds'] = ['foo-1-1']

        with mock.patch('bodhi.server.validators.buildsys.get_session',
                        self.mock_get_session_for_class(self.UnknownTagDevBuildsys)):
            validators.validate_from_tag(self.request)

        assert self.request.errors == [
            {'location': 'body', 'name': 'from_tag',
             'description': "The supplied from_tag doesn't exist."}
        ]

    def test_unknown_without_builds(self):
        """An unknown from_tag should add an error to the request.

        This test runs without a list of fills in request.validated."""
        with mock.patch('bodhi.server.validators.buildsys.get_session',
                        self.mock_get_session_for_class(self.UnknownTagDevBuildsys)):
            validators.validate_from_tag(self.request)

        assert self.request.errors == [
            {'location': 'body', 'name': 'from_tag',
             'description': "The supplied from_tag doesn't exist."}
        ]

    def test_unknown_koji_genericerror(self):
        """An unknown koji.GenericError should be wrapped."""
        with pytest.raises(BodhiException) as excinfo:
            with mock.patch('bodhi.server.validators.buildsys.get_session',
                            self.mock_get_session_for_class(self.UnknownKojiGenericError)):
                validators.validate_from_tag(self.request)

        assert (str(excinfo.value)
                == "Encountered error while requesting tagged builds from Koji: 'foo'")

        # check type of wrapped exception
        assert isinstance(excinfo.value.__cause__, koji.GenericError)
