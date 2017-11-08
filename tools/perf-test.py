""" perf-test.py

Perform HTTP GET requests on a bunch of local bodhi URLs and report how long
each one took to respond/load.
"""

import collections
import commands
import time
import sys

import requests
from six.moves import input


reflength = 10

items = collections.OrderedDict([
    ('frontpage', 'http://0.0.0.0:6543/'),
    ('update_list', 'http://0.0.0.0:6543/updates/'),
    ('update_list_gnome', 'http://0.0.0.0:6543/updates/?packages=gnome-2048'),
    ('update_view', ('http://0.0.0.0:6543/updates/'
                     'FEDORA-2015-13946')),
    ('update_view_gnome', ('http://0.0.0.0:6543/updates/FEDORA-2015-16555')),
    ('release_list', 'http://0.0.0.0:6543/releases/'),
    ('release_view', 'http://0.0.0.0:6543/releases/f22'),
    ('comment_list', 'http://0.0.0.0:6543/comments/'),
    ('comment_view', 'http://0.0.0.0:6543/comments/328597'),
    ('user_list', 'http://0.0.0.0:6543/users/'),
    ('user_view', 'http://0.0.0.0:6543/users/adamwill'),
    ('f-e-k-query', 'http://0.0.0.0:6543/updates/?status=testing&release=F22&limit=100')
])


def clock_url(url, tries=4):
    """ Return the average time taken to query a URL.
    Throw out the max and min values to avoid startup skew.
    """
    values = []
    for i in range(tries):
        start = time.time()
        response = requests.get(url)
        if not bool(response):
            raise IOError("pserve failure: %r" % response.status_code)
        values.append(time.time() - start)
    values.remove(max(values))
    values.remove(min(values))
    return sum(values) / len(values)


def do_scan():
    results = collections.OrderedDict()
    for name, url in items.items():
        print('Crunching', name, url)
        duration = clock_url(url)
        results[name] = duration
    return results


def loop_over_refs(refs):
    print("Checking %r" % refs)
    response = input("Is that okay? ")
    if response != 'y':
        sys.exit(0)
    for ref in refs:
        time.sleep(3)
        ref = ref[:reflength]
        commands.getstatus('git checkout %s' % ref)
        print("Running on", ref)
        results[ref] = do_scan()
    return results


def print_table(table):
    width = max([len(key) for key in items.keys()])
    headers = [' ' * width] + [ref.ljust(reflength) for ref in table.keys()]

    rows = [headers] + [["-" * width] + ["-" * reflength] * len(table)]
    for item in items:
        rows.append(
            [item.ljust(width)] +
            [("%0.2fs" % table[ref][item]).ljust(reflength) for ref in table]
        )

    for row in rows:
        print("|" + "|".join(row) + "|")


if __name__ == '__main__':
    results = collections.OrderedDict()
    head = commands.getoutput('git rev-parse --abbrev-ref HEAD')
    reflength = max([reflength, len(head)])

    refs = sys.argv[1:]
    if not refs:
        refs = [head]

    try:
        results = loop_over_refs(refs)
    finally:
        print("Returning you to %s" % head)
        commands.getstatus('git checkout %s' % head)

    print_table(results)
