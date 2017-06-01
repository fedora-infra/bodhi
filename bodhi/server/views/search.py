# Copyright 2014-2017 Red Hat, Inc. and others
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
"""Contains a view that allows API users to search packages."""

from pyramid.view import view_config

from bodhi.server import log, buildsys


def get_all_packages():
    """
    Return a list of all packages in Koji.

    Returns:
        list: The list of package_names from the koji.listPackages() call.
    """
    log.debug('Fetching list of all packages...')
    koji = buildsys.get_session()
    return [pkg['package_name'] for pkg in koji.listPackages()]


@view_config(route_name='search_packages', renderer='json',
             request_method='GET')
def search_packages(request):
    """
    Search for packages that match the given term GET query parameter.

    Deprecated: This view is unused by the web UI and the CLI and might be a good candidate for
    removal in a future major release.

    Args:
        request (pyramid.request): The current web request.
    Returns:
        list: A list of dictionaries with keys 'id', 'label', and 'value' all indexing koji
            listPackages() results that match the search term.
    """
    packages = get_all_packages()
    return [{'id': p, 'label': p, 'value': p} for p in packages
            if request.GET['term'] in p]
