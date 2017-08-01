# -*- coding: utf-8 -*-
# Copyright © 2014-2017 Red Hat, Inc. and others.
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
"""Define an API endpoint to process text through Bodhi's markdown system."""

from cornice import Service

import bodhi.server.util
import bodhi.server.security
import bodhi.server.services.errors


markdown = Service(name='markdowner', path='/markdown',
                   description='Markdown service',
                   cors_origins=bodhi.server.security.cors_origins_ro)


@markdown.get(accept=('application/json', 'text/json'), renderer='json',
              error_handler=bodhi.server.services.errors.json_handler)
@markdown.get(accept=('application/javascript'), renderer='jsonp',
              error_handler=bodhi.server.services.errors.jsonp_handler)
def markdowner(request):
    """
    Given some text, return the markdownified html version.

    We use this for "previews" of comments and update notes.

    Args:
        request (pyramid.request): The current request. It's "text" parameter is used to specify the
            text to be processed.
    Returns:
        basestring: A JSON object with a single key, html, that indexes the processed text.
    """
    text = request.params.get('text')
    return dict(html=bodhi.server.util.markup(request.context, text))
