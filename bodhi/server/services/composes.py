# Copyright © 2017-2018 Red Hat, Inc.
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
"""Defines service endpoints pertaining to Composes."""

from cornice.resource import resource, view
from pyramid import httpexceptions
from pyramid.security import Allow, Everyone
from sqlalchemy.orm import exc

from bodhi.server import models, security
from bodhi.server.services import errors


@resource(collection_path='/composes/', path='/composes/{release_name}/{request}',
          description='Compose service')
class Composes(object):
    """
    Defines resources for interacting with Compose objects.

    Operations acting on the collection are served at ``/composes/`` and operations acting on a
    single compose are served at ``/composes/<release_name>/<request>``.
    """

    def __init__(self, request, context=None):
        """
        Initialize the Compose resource.

        Args:
            request (pyramid.request.Request): The current web request.
            context (None): Unused.
        """
        self.request = request

    def __acl__(self):
        """
        Define ACLs for the Compose resource.

        Returns:
            list: A list of ACLs for this Resource.
        """
        return [(Allow, Everyone, 'view_composes')]

    @view(
        accept=('application/json', 'text/json'), renderer='json',
        cors_origins=security.cors_origins_ro, error_handler=errors.json_handler,
        permission='view_composes')
    @view(accept=('text/html',), renderer='composes.html', cors_origins=security.cors_origins_ro,
          permission='view_composes', error_handler=errors.html_handler)
    def collection_get(self):
        """
        List composes.

        This method responds to the ``/composes/`` endpoint.

        Returns:
            dict: A dictionary mapping the key 'composes' to an iterable of all Compose objects.
        """
        return {'composes': sorted(models.Compose.query.all())}

    @view(accept=('application/json', 'text/json'), renderer='json',
          cors_origins=security.cors_origins_ro, error_handler=errors.json_handler,
          permission='view_composes')
    @view(accept=('text/html',), renderer='compose.html', cors_origins=security.cors_origins_ro,
          permission='view_composes', error_handler=errors.html_handler)
    def get(self):
        """
        Retrieve and render a single compose.

        This API responses to the ``/composes/<release_name>/<request>`` endpoint.

        Returns:
            dict: A dictionary mapping the key 'compose' to a single Compose object.
        """
        try:
            release = models.Release.query.filter_by(
                name=self.request.matchdict['release_name']).one()
            compose = models.Compose.query.filter_by(
                release_id=release.id,
                request=models.UpdateRequest.from_string(self.request.matchdict['request'])).one()
        except (exc.NoResultFound, ValueError):
            # NoResultFound means that either the Release or the Compose does not exist. ValueError
            # can happen if the request component of the URL does not match one of the enums.
            raise httpexceptions.HTTPNotFound()

        return {'compose': compose}
