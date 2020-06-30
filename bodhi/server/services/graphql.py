# Copyright © 2020 Red Hat Inc., and others.
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
"""Defines API endpoints related to GraphQL objects."""
import graphene
from cornice import Service
from webob_graphql import serve_graphql_request

from bodhi.server.config import config
from bodhi.server.graphql_schemas import Release


graphql = Service(name='graphql', path='/graphql', description='graphql service')


@graphql.get()
@graphql.post()
def graphql_get(request):
    """
    Perform a GET request.

    Args:
        request (pyramid.Request): The current request.
    Returns:
        The GraphQL response to the request.
    """
    context = {'session': request.session}
    return serve_graphql_request(
        request, schema, graphiql_enabled=config.get('graphiql_enabled'),
        context_value=context)


class Query(graphene.ObjectType):
    """Allow querying objects."""

    allReleases = graphene.List(Release)

    def resolve_allReleases(self, info):
        """Answer Queries by fetching data from the Schema."""
        query = Release.get_query(info)  # SQLAlchemy query
        return query.all()


schema = graphene.Schema(query=Query)
