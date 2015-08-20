""" perf-test.py

Perform HTTP GET requests on a bunch of local bodhi URLs and report how long
each one took to respond/load.
"""

import collections
import requests
import time

items = collections.OrderedDict([
    ('frontpage', 'http://0.0.0.0:6543/'),
    ('update_list', 'http://0.0.0.0:6543/updates'),
    ('update_view', ('http://0.0.0.0:6543/updates/'
                     'abrt-2.1.6-2.fc19%2Cgnome-abrt'
                     '-0.3.0-3.fc19%2Clibreport-2.1.6-2.fc19')),
    ('release_list', 'http://0.0.0.0:6543/releases'),
    ('release_view', 'http://0.0.0.0:6543/releases/f19'),
    ('comment_list', 'http://0.0.0.0:6543/comments'),
    ('comment_view', 'http://0.0.0.0:6543/comments/2'),
    ('user_list', 'http://0.0.0.0:6543/users/'),
    ('user_view', 'http://0.0.0.0:6543/users/adamwill'),
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
