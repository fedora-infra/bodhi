# -*- coding: utf-8 -*-
# Copyright © 2014-2017 Red Hat, Inc. and others
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
"""Define the admin view."""

from cornice import Service

from bodhi.server import log
from bodhi.server import security


admin_service = Service(name='admin', path='/admin/',
                        description='Administrator view',
                        factory=security.AdminACLFactory)


@admin_service.get(permission='admin')
def admin(request):
    """
    Return a dictionary with keys "user" and "principals".

    "user" indexes the current user's name, and "principals" indexes the user's effective
    principals.

    Args:
        request (pyramid.request): The current request.
    Returns:
        dict: A dictionary as described above.
    """
    user = request.user
    log.info('%s logged into admin panel' % user.name)
    principals = request.effective_principals
    return {'user': user.name, 'principals': principals}
