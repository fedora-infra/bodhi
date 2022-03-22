# Copyright © 2019 Red Hat, Inc.
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
"""Defines service endpoints for our message schemas."""

import typing

from cornice.resource import resource, view
from pyramid import httpexceptions
from pyramid.authorization import Allow, Everyone
import pkg_resources

from bodhi.server import security
from bodhi.server.services import errors


if typing.TYPE_CHECKING:  # pragma: no cover
    import pyramid.request.Request  # noqa: 401


READ_ACL = 'view_schemas'


@resource(collection_path='/message-schemas/v1/', path='/message-schemas/v1/{topic}',
          description='Message schemas')
class MessageSchemasV1:
    """
    Defines resources for serving Bodhi's message schemas.

    Operations acting on the collection are served at ``/message-schemas/v1/`` and operations acting
    on a single schema are served at ``/message-schemas/v1/<topic>``.
    """

    def __init__(self, request: 'pyramid.request.Request', context: None = None):
        """
        Initialize the MessageSchemas resource.

        Args:
            request: The current web request.
            context: Unused.
        """
        self.request = request

    @staticmethod
    def __acl__() -> typing.Iterable[typing.Tuple[str, str, str]]:
        """
        Define ACLs for the MessageSchemas resource.

        Returns:
            A list of ACLs for this Resource.
        """
        return [(Allow, Everyone, READ_ACL)]

    @view(
        accept=('application/json', 'text/json'), renderer='json',
        cors_origins=security.cors_origins_ro, error_handler=errors.json_handler,
        permission=READ_ACL)
    def collection_get(self) -> typing.Iterable[str]:
        """
        List schemas.

        This method responds to the ``/message-schemas/v1/`` endpoint.

        Returns:
            A list of message topics that Bodhi supports.
        """
        return [m.load().topic for m in pkg_resources.iter_entry_points('fedora.messages')
                if m.module_name.startswith('bodhi.')]

    @view(accept=('application/json', 'text/json'), renderer='json',
          cors_origins=security.cors_origins_ro, error_handler=errors.json_handler,
          permission=READ_ACL)
    def get(self) -> dict:
        """
        Retrieve and render a single message schema.

        This API responses to the ``/message_schemas/v1/<topic>`` endpoint.

        Returns:
            The requested message schema.
        """
        try:
            return pkg_resources.load_entry_point(
                'bodhi-messages', 'fedora.messages',
                f"{self.request.matchdict['topic']}.v1").body_schema
        except ImportError:
            # The user has requested a topic that does not exist
            raise httpexceptions.HTTPNotFound()
