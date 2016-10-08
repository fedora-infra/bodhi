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

from pyramid.security import effective_principals
from cornice import Service

from bodhi.server import log
from bodhi.server.security import admin_only_acl

admin_service = Service(name='admin', path='/admin/',
                        description='Administrator view',
                        acl=admin_only_acl)


@admin_service.get(permission='admin')
def admin(request):
    user = request.user
    log.info('%s logged into admin panel' % user.name)
    principals = effective_principals(request)
    return {'user': user.name, 'principals': principals}
