# -*- coding: utf-8 -*-
# Copyright © 2015-2017 Red Hat, Inc.
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
"""
Handle general redirect stuff.

This module name gets a 'zz_' tacked on the front so that it comes last.
We need to catch /updates/{id}/request and /updates/{id}/edit first and those
get defined in the other service modules.
"""

from cornice import Service
from pyramid.httpexceptions import HTTPFound

import bodhi.server.security


zz_bodhi1_update_redirect = Service(
    name='bodhi1_update_redirect', path='/updates/{id}/{title}',
    description='Redirect to old updates/ALIAS/TITLE urls',
    cors_origins=bodhi.server.security.cors_origins_rw)


@zz_bodhi1_update_redirect.get()
def zz_get_bodhi1_update_redirect(request):
    """
    Redirect users from the Bodhi 1 update URL to the new path.

    Args:
        request (pyramid.request): The current web request.
    Returns:
        pyramid.httpexceptions.HTTPFound: A redirect to the same update in Bodhi's current URL
            heirarchy.
    """
    return HTTPFound("/updates/{0}".format(request.matchdict['id']))
