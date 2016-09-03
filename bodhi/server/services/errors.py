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

import logging
import os
import re

import cornice.util

import mako.exceptions
import mako.lookup

import pyramid.httpexceptions
import pyramid.response

from bodhi.server.config import config

log = logging.getLogger('bodhi')


# First, just re-use cornice's default json handler for our own.  It is fine.
json_handler = cornice.util.json_error

# TODO -- make this do the right thing.  Not a big deal for now.
jsonp_handler = cornice.util.json_error


def camel2space(camel):
    """ Convert CamelCaseText to Space Separated Text. """
    regexp = r'([A-Z][a-z0-9]+|[a-z0-9]+|[A-Z0-9]+)'
    return ' '.join(re.findall(regexp, camel))


def status2summary(status):
    """ Convert 404 the int to "Not Found" the str. """
    cls = pyramid.httpexceptions.status_map[status]
    camel = cls.__name__[4:]
    return camel2space(camel)


class html_handler(pyramid.httpexceptions.HTTPError):
    """ An HTML formatting handler for all our errors. """
    def __init__(self, errors):

        location = config.get('mako.directories')
        module, final = location.split(':')
        base = os.path.dirname(__import__(module).__file__)
        directory = base + "/" + final

        lookup = mako.lookup.TemplateLookup(
            directories=[directory],
            output_encoding='utf-8',
            input_encoding='utf-8',
        )
        template = lookup.get_template('errors.html')

        try:
            body = template.render(
                errors=errors,
                status=errors.status,
                request=errors.request,
                summary=status2summary(errors.status),
            )
        except:
            log.error(mako.exceptions.text_error_template().render())
            raise

        # This thing inherits from both Exception *and* Response, so.. take the
        # Response path in the diamond inheritance chain and ignore the
        # exception side.
        # That turns this thing into a "real boy" like pinnochio.
        pyramid.response.Response.__init__(self, body)

        self.status = errors.status
        self.content_type = 'text/html'
