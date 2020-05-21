# Copyright © 2011-2017 Red Hat, Inc. and others.
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
"""Define utilities for handling errors in the service modules."""

import logging
import re

import mako.exceptions
import mako.lookup
import pyramid.httpexceptions
import pyramid.response

from bodhi.server.config import config
from bodhi.server.util import get_absolute_path

try:  # pragma: no cover
    from cornice.util import json_error
    json_handler = json_error
    jsonp_handler = json_error
except ImportError:  # pragma: no cover
    from cornice.renderer import CorniceRenderer
    renderer = CorniceRenderer()
    json_handler = renderer.render_errors
    jsonp_handler = renderer.render_errors


log = logging.getLogger('bodhi')


def camel2space(camel):
    """
    Convert CamelCaseText to Space Separated Text.

    Args:
        camel (str): Camel cased text you wish to convert to space separated text.
    Returns:
        str: A space separated version of the given camel cased text.
    """
    regexp = r'([A-Z][a-z0-9]+|[a-z0-9]+|[A-Z0-9]+)'
    return ' '.join(re.findall(regexp, camel))


def status2summary(status):
    """
    Convert numerical HTTP status codes to human readable error strings.

    For example, this converts 404 to "Not Found".

    Args:
        status (int): The status you wish to have a human readable string for.
    Returns:
        str: A human readable error message.
    """
    cls = pyramid.httpexceptions.status_map[status]
    camel = cls.__name__[4:]
    return camel2space(camel)


class html_handler(pyramid.httpexceptions.HTTPError):
    """An HTML formatting handler for all our errors."""

    def __init__(self, request):
        """
        Initialize the HTML error handler to render an error message for human readers.

        This method sets the Response body to rendered HTML version of the given errors, and the
        status code to the code specified by errors.

        Args:
            request (pyramid.request.Request): The current Request.
        """
        location = config.get('mako.directories')
        directory = get_absolute_path(location)

        lookup = mako.lookup.TemplateLookup(
            directories=[directory],
            output_encoding='utf-8',
            input_encoding='utf-8',
        )
        template = lookup.get_template('errors.html')
        errors = request.errors

        try:
            body = template.render(
                errors=errors,
                status=errors.status,
                request=request,
                summary=status2summary(errors.status),
            )
        except Exception:
            log.error(mako.exceptions.text_error_template().render())
            raise

        # This thing inherits from both Exception *and* Response, so.. take the
        # Response path in the diamond inheritance chain and ignore the
        # exception side.
        # That turns this thing into a "real boy" like pinnochio.
        pyramid.response.Response.__init__(self, body)

        self.status = errors.status
        self.content_type = 'text/html'
