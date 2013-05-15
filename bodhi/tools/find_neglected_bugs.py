# Bugzilla damage control.
# A script to scan updates after a certain date for bugs that were never
# properly closed.
#
# $ make shell
# >>> execfile('find_neglected_bugs.py')
# >>> # do things with neglected.pickle if you want
# >>> execfile('close_neglected_bugs.py')

import pickle
from itertools import chain, islice
from datetime import datetime
from collections import defaultdict

# The date bodhi stopped closing bugs
date = datetime(2013, 5, 6)


def ichunked(seq, chunksize):
    """Yields items from an iterator in iterable chunks."""
    it = iter(seq)
    while True:
        yield chain([it.next()], islice(it, chunksize-1))


def chunked(seq, chunksize):
    """Yields items from an iterator in list chunks."""
    for chunk in ichunked(seq, chunksize):
        yield list(chunk)


def collect_bugs():
    bugs = set()
    for up in PackageUpdate.select(
        AND(PackageUpdate.q.date_submitted >= date,
            PackageUpdate.q.close_bugs == True,
            PackageUpdate.q.status == 'stable')):
        for bug in up.bugs:
            bugs.add(bug.bz_id)
    return bugs


def find_neglected_bugs(bugs):
    neglected = defaultdict(set)
    bz = Bugzilla.get_bz()
    for chunk in chunked(bugs, 200):
        print("Querying bugzilla for %d bugs" % len(chunk))
        buglist = bz.getbugs(chunk)
        for bug in buglist:
            if not bug:
                print(bug)
                continue
            if bug.product not in ('Fedora', 'Fedora EPEL'):
                print("Skipping %s bug %s" % (bug.product, bug.id))
                continue
            if bug.status != 'CLOSED':
                print('%d %s->%s' % (bug.id, bug.status, bug.resolution))
                neglected[bug.status].add(bug.id)
    return neglected


def main():
    bugs = collect_bugs()
    print('%d bugs found' % len(bugs))
    neglected = find_neglected_bugs(bugs)
    out = file('neglected.pickle', 'w')
    pickle.dump(neglected, out)
    out.close()
    print('neglected.pickle written!')


main()
