# Copyright © 2007-2017 Red Hat, Inc. and others.
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
"""Define the /csrf services."""

from pyramid.view import view_config


@view_config(route_name='csrf',request_method='GET',accept='text/html',renderer='string')
def get_csrf_token_html(request):
    """
    Return a plain string CSRF token.

    Returns:
        str: A CSRF token.
    """
    return request.session.get_csrf_token()


@view_config(route_name='csrf',request_method='GET',accept=('application/json', 'text/json'),renderer='json')
def get_csrf_token_json(request):
    """
    Return a JSON string containing a CSRF token, in a key called csrf_token.

    Returns:
        str: A JSON string with a key csrf_token that references a CSRF token.
    """
    return dict(csrf_token=request.session.get_csrf_token())
