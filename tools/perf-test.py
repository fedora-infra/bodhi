""" perf-test.py

Perform HTTP GET requests on a bunch of local bodhi URLs and report how long
each one took to respond/load.
"""

import collections
import requests
import time

items = collections.OrderedDict([
    ('frontpage', 'http://0.0.0.0:6543/'),
    ('update_list', 'http://0.0.0.0:6543/updates/'),
    ('update_list_gnome', 'http://0.0.0.0:6543/updates/?packages=gnome-2048'),
    ('update_view', ('http://0.0.0.0:6543/updates/'
                     'FEDORA-2015-13946')),
    ('update_view_gnome', ('http://0.0.0.0:6543/updates/'
                     'FEDORA-2015-16555')),
    ('release_list', 'http://0.0.0.0:6543/releases/'),
    ('release_view', 'http://0.0.0.0:6543/releases/f22'),
    ('comment_list', 'http://0.0.0.0:6543/comments/'),
    ('comment_view', 'http://0.0.0.0:6543/comments/2'),
    ('user_list', 'http://0.0.0.0:6543/users/'),
    ('user_view', 'http://0.0.0.0:6543/users/adamwill'),
    ('f-e-k-query', 'http://0.0.0.0:6543/updates/?status=testing&release=F22&limit=100')
])

results = collections.OrderedDict()


def clock_it(url):
    start = time.time()
    requests.get(url)
    return time.time() - start

for name, url in items.items():
    print 'Crunching', name, url
    duration = clock_it(url)
    results[name] = duration

print "-" * 7
print "Results"
print "-" * 7
for name, duration in results.items():
    print name.rjust(20), duration, "seconds"
