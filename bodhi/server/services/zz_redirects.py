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
""" Handle general redirect stuff.

This module name gets a 'zz_' tacked on the front so that it comes last.
We need to catch /updates/{id}/request and /updates/{id}/edit first and those
get defined in the other service modules.
"""

from cornice import Service
from pyramid.httpexceptions import HTTPFound

from bodhi.server.services.comments import comments
from bodhi.server.services.overrides import overrides
from bodhi.server.services.updates import updates
from bodhi.server.services.user import users
import bodhi.server.security


def redirect_maker(target):
    def redirector(request):
        url = request.route_url('updates_rss')
        if request.query_string:
            url = url + '?' + request.query_string
        raise HTTPFound(url)
    return redirector


@comments.get(accept=('application/atom+xml',))
def comments_rss_redirect(request):
    return redirect_maker('comments_rss')(request)


@overrides.get(accept=('application/atom+xml',))
def overrides_rss_redirect(request):
    return redirect_maker('overrides_rss')(request)


@updates.get(accept=('application/atom+xml',))
def updates_rss_redirect(request):
    return redirect_maker('updates_rss')(request)


@users.get(accept=('application/atom+xml',))
def users_rss_redirect(request):
    return redirect_maker('users_rss')(request)


zz_bodhi1_update_redirect = Service(
    name='bodhi1_update_redirect', path='/updates/{id}/{title}',
    description='Redirect to old updates/ALIAS/TITLE urls',
    cors_origins=bodhi.server.security.cors_origins_rw)


@zz_bodhi1_update_redirect.get()
def zz_get_bodhi1_update_redirect(request):
    return HTTPFound("/updates/{0}".format(request.matchdict['id']))
