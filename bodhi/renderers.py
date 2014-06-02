import operator

from pyramid.exceptions import HTTPNotFound
import webhelpers.feedgenerator


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
        else:
            raise HTTPNotFound("RSS not implemented for this service")

        feed = webhelpers.feedgenerator.Rss201rev2Feed(
            title=key,
            link=request.url,
            description=key,
            language=u"en",
        )

        def linker(route, param, key):
            return lambda obj: request.route_url(route, **{param: obj[key]})

        getters = {
            'updates': {
                'title': operator.itemgetter('title'),
                'link': linker('update', 'id', 'title'),
                'description': operator.itemgetter('notes'),
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
            },
        }

        for value in data[key]:
            feed.add_item(**dict([
                (name, getter(value)) for name, getter in getters[key].items()
            ]))

        return feed.writeString('utf-8')

    return render

