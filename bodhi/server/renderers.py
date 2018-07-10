# -*- coding: utf-8 -*-
# Copyright © 2014-2017 Red Hat, Inc.
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
"""Define special view renderers, such as RSS and jpeg."""
import io
import operator

from pytz import utc
from feedgen.feed import FeedGenerator


def rss(info):
    """
    Return a RSS renderer.

    Args:
        info (pyramid.renderers.RendererHelper): Unused.
    Returns:
        function: A function that can be used to render a RSS view.
    """
    def render(data, system):
        """
        Render the given data as an RSS view.

        If the request's content type is set to the default, this function will change it to
        application/rss+xml.

        Args:
            data (dict): A dictionary describing the information to be rendered. The information can
                be different types of objects, such as updates, users, comments, or overrides.
            system (pyramid.events.BeforeRender): Used to get the current request.
        Returns:
            basestring: An RSS document representing the given data.
        """
        request = system.get('request')
        if request is not None:
            response = request.response
            ct = response.content_type
            if ct == response.default_content_type:
                response.content_type = 'application/rss+xml'

        if 'updates' in data:
            key = 'updates'
            feed_title = 'Released updates'
        elif 'users' in data:
            key = 'users'
            feed_title = 'Bodhi users'
        elif 'comments' in data:
            key = 'comments'
            feed_title = 'User comments'
        elif 'overrides' in data:
            key = 'overrides'
            feed_title = 'Update overrides'

        feed_description_list = []
        for k in request.GET.keys():
            feed_description_list.append('%s(%s)' % (k, request.GET[k]))
        if feed_description_list:
            feed_description = 'Filtered on: ' + ', '.join(feed_description_list)
        else:
            feed_description = "All %s" % (key)

        feed = FeedGenerator()
        feed.title(feed_title)
        feed.link(href=request.url, rel='self')
        feed.description(feed_description)
        feed.language(u'en')

        def linker(route, param, key):
            def link_dict(obj):
                return dict(href=request.route_url(route, **{param: obj[key]}))
            return link_dict

        getters = {
            'updates': {
                'title': operator.itemgetter('title'),
                'link': linker('update', 'id', 'title'),
                'description': operator.itemgetter('notes'),
                'pubdate': lambda obj: utc.localize(obj['date_submitted']),
            },
            'users': {
                'title': operator.itemgetter('name'),
                'link': linker('user', 'name', 'name'),
                'description': operator.itemgetter('name'),
            },
            'comments': {
                'title': operator.itemgetter('rss_title'),
                'link': linker('comment', 'id', 'id'),
                'description': operator.itemgetter('text'),
                'pubdate': lambda obj: utc.localize(obj['timestamp']),
            },
            'overrides': {
                'title': operator.itemgetter('nvr'),
                'link': linker('override', 'nvr', 'nvr'),
                'description': operator.itemgetter('notes'),
                'pubdate': lambda obj: utc.localize(obj['submission_date']),
            },
        }

        for value in data[key]:
            feed_item = feed.add_item()
            for name, getter in getters[key].items():
                # Because we have to use methods to fill feed entry attributes,
                # it's done by getting methods by name and calling them
                # on the same line.
                getattr(feed_item, name)(getter(value))

        return feed.rss_str()

    return render


def jpeg(info):
    """
    Return a JPEG renderer.

    Args:
        info (pyramid.renderers.RendererHelper): Unused.
    Returns:
        function: A function that can be used to render a jpeg view.
    """
    def render(data, system):
        """
        Render the given image as a request response.

        This function will also set the content type to image/jpeg if it is the default type.

        Args:
            data (PIL.Image.Image): The jpeg that should be sent back as a response.
            system (pyramid.events.BeforeRender): Used to get the current request.
        Returns:
            str: The raw jpeg bytes of the given image.
        """
        request = system.get('request')
        if request is not None:
            response = request.response
            ct = response.content_type
            if ct == response.default_content_type:
                response.content_type = 'image/jpeg'

        b = io.BytesIO()
        data.save(b, 'jpeg')
        return b.getvalue()
    return render
