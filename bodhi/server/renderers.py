import io
import operator

from pytz import utc
from feedgen.feed import FeedGenerator


def rss(info):
    def render(data, system):
        request = system.get('request')
        if request is not None:
            response = request.response
            ct = response.content_type
            if ct == response.default_content_type:
                response.content_type = 'application/rss+xml'

        if 'updates' in data:
            key = 'updates'
        elif 'users' in data:
            key = 'users'
        elif 'comments' in data:
            key = 'comments'
        elif 'overrides' in data:
            key = 'overrides'

        feed = FeedGenerator()
        feed.title(key)
        feed.link(href=request.url, rel='self')
        feed.description(key)
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
                'title': operator.itemgetter('text'),
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
                # on the same line
                getattr(feed_item, name)(getter(value))

        return feed.rss_str()

    return render


def jpeg(info):
    def render(data, system):
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
