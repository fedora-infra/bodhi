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
from bodhi.server.graphql_schemas import Release, ReleaseModel


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
    getRelease = graphene.Field(
        lambda: graphene.List(Release), name=graphene.String(),
        id_prefix=graphene.String(), composed_by_bodhi=graphene.Boolean(),
        state=graphene.String())

    def resolve_allReleases(self, info):
        """Answer Queries by fetching data from the Schema."""
        query = Release.get_query(info)  # SQLAlchemy query
        return query.all()

    def resolve_getRelease(self, info, **args):
        """Answer Release queries with a given argument."""
        query = Release.get_query(info)

        id_prefix = args.get("id_prefix")
        if id_prefix is not None:
            query = query.filter(ReleaseModel.id_prefix == id_prefix)

        name = args.get("name")
        if name is not None:
            query = query.filter(ReleaseModel.name == name)

        composed_by_bodhi = args.get("composed_by_bodhi")
        if composed_by_bodhi is not None:
            query = query.filter(ReleaseModel.composed_by_bodhi == composed_by_bodhi)

        state = args.get("state")
        if state is not None:
            query = query.filter(ReleaseModel.state == state)

        return query.all()


schema = graphene.Schema(query=Query)
