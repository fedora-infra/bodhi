# Copyright 2019 Red Hat, Inc. and others.
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
"""This module contains tests for bodhi.server.services.schemas."""

from pyramid import testing

from bodhi.messages.schemas.update import UpdateCommentV1
from bodhi.server.services import schemas

from .. import base


try:
    # Pyramid >= 2.0
    from pyramid.authorization import Allow, Everyone
except ImportError:
    # Pyramid < 2.0
    from pyramid.security import Allow, Everyone


class TestMessageSchemasV1__init__(base.BasePyTestCase):
    """This class contains tests for the MessageSchemasV1.__init__() method."""
    def test___init__(self):
        """Assert the request is stored properly."""
        request = testing.DummyRequest()

        schemas_resource = schemas.MessageSchemasV1(request)

        assert schemas_resource.request is request


class TestMessageSchemasV1__acl__(base.BasePyTestCase):
    """This class contains tests for the MessageSchemasV1.__acl__() method."""
    def test___acl__(self):
        """Assert the permissions are correct."""
        request = testing.DummyRequest()
        schemas_resource = schemas.MessageSchemasV1(request)

        acls = schemas_resource.__acl__()

        assert acls == [(Allow, Everyone, 'view_schemas')]


class TestMessageSchemasV1CollectionGet(base.BasePyTestCase):
    """This class contains tests for the MessageSchemasV1.collection_get() method."""
    def test_get(self):
        """Test with a GET request."""
        response = self.app.get('/message-schemas/v1/', status=200, headers={'Accept': 'text/json'})

        assert set(response.json) == set([
            'bodhi.buildroot_override.tag', 'bodhi.buildroot_override.untag',
            'bodhi.compose.complete', 'bodhi.compose.composing', 'bodhi.compose.start',
            'bodhi.compose.sync.done', 'bodhi.compose.sync.wait',
            'bodhi.errata.publish', 'bodhi.repo.done', 'bodhi.update.comment',
            'bodhi.update.complete.stable', 'bodhi.update.complete.testing',
            'bodhi.update.status.testing.koji-build-group.build.complete',
            'bodhi.update.karma.threshold.reach', 'bodhi.update.edit', 'bodhi.update.eject',
            'bodhi.update.request.obsolete', 'bodhi.update.request.revoke',
            'bodhi.update.request.stable', 'bodhi.update.request.testing',
            'bodhi.update.request.unpush', 'bodhi.update.requirements_met.stable'
        ])


class TestMessageSchemasV1Get(base.BasePyTestCase):
    """This class contains tests for the MessageSchemasV1.get() method."""
    def test_404(self):
        """Assert a 404 error code when there isn't a message topic matching the URL."""
        self.app.get('/message-schemas/v1/does-not-exist', status=404,
                     headers={'Accept': 'text/json'})

    def test_200(self):
        """Assert correct behavior when an existing topic is requested."""
        response = self.app.get(
            '/message-schemas/v1/bodhi.update.comment',
            status=200, headers={'Accept': 'text/json'})

        assert response.json == UpdateCommentV1.body_schema
