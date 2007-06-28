from turbogears.feed import FeedController
from turbogears import expose

class Feed(FeedController):

    def get_feed_data(self, *args, **kw):
        print "*args =", args
        print "**kw =", kw
        return dict(entries=[{'foo': 'bar'}])
