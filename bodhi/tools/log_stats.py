#!/usr/bin/env python
"""
A script that scrapes bodhi's mod_wsgi logs to calculate autokarma statistics.

In bodhi v2.0, we'll do better tracking of these transitions in the database,
and will not have to scrape logs.
"""

import subprocess

from datetime import timedelta
from operator import itemgetter
from sqlobject import SQLObjectNotFound
from collections import defaultdict
from turbogears.database import PackageHub

from bodhi.util import load_config, header
from bodhi.model import PackageUpdate, Release, PackageBuild

def parse_output(out):
    updates = defaultdict(set)
    num_critpath = defaultdict(int)
    debug = file('bodhi.debug', 'a')
    deltas = []
    occurrences = {}
    accumulative = timedelta()

    for line in out.split('\n'):
        line = line.strip()
        if '}' in line:
            continue
        if line:
            debug.write(line + '\n')
            title = line.split()[-1]
            update = None
            for build in title.split(','):
                try:
                    update = PackageBuild.byNvr(build).updates[0]
                    break
                except SQLObjectNotFound:
                    pass
                    #print "Cannot find update for %s" % build
            if update:
                if update.title not in updates[update.release.name]:
                    updates[update.release.name].add(update.title)
                    if update.critpath:
                        num_critpath[update.release.name] += 1
                    for comment in update.comments:
                        if comment.text == 'This update has been pushed to testing':
                            for othercomment in update.comments:
                                if othercomment.text == 'This update has been pushed to stable':
                                    delta = othercomment.timestamp - comment.timestamp
                                    deltas.append(delta)
                                    occurrences[delta.days] = occurrences.setdefault(delta.days, 0) + 1
                                    accumulative += delta
                                    break
                            break
    debug.close()
    deltas.sort()
    return updates, num_critpath, deltas, accumulative, occurrences


def main():
    unstable = subprocess.Popen('grep "\[Fedora Update\] \[unstable\]" bodhi.logs',
                                stdout=subprocess.PIPE, shell=True)
    out, err = unstable.communicate()
    (unstable_updates, unstable_critpath, unstable_deltas,
     unstable_accum, unstable_occur) = parse_output(out)

    stable = subprocess.Popen('grep "\[Fedora Update\] \[stablekarma\]" bodhi.logs',
                              stdout=subprocess.PIPE, shell=True)
    out, err = stable.communicate()
    (stable_updates, stable_critpath, stable_deltas,
     stable_accum, stable_occur) = parse_output(out)

    for release in Release.select():
        print '\n' + header(release.long_name)
        num_updates = PackageUpdate.select(
                PackageUpdate.q.releaseID==release.id).count()
        num_stable = len(stable_updates[release.name])
        num_unstable = len(unstable_updates[release.name])
        num_testing = len(unstable_deltas) + len(stable_deltas)
        print " * %d updates automatically unpushed due to karma (%0.2f%%)" % (
                num_unstable, float(num_unstable) / num_updates * 100)
        print "   * %d of which were critical path updates" % (
                unstable_critpath[release.name])
        print " * %d updates automatically pushed due to karma (%0.2f%%)" % (
                num_stable, float(num_stable) / num_updates * 100)
        print "   * %d of which were critical path updates" % (
                stable_critpath[release.name])

        print " * Time spent in testing of updates that were pushed by karma:"
        print "   * mean = %d days" % (stable_accum.days / len(stable_deltas))
        print "   * median = %d days" % stable_deltas[len(stable_deltas)/2].days
        print "   * mode = %d days" % sorted(stable_occur.items(),
                                             key=itemgetter(1))[-1][0]

        print " * Time spent in testing of updates that were unpushed by karma:"
        print "   * mean = %d days" % (unstable_accum.days / len(unstable_deltas))
        print "   * median = %d days" % unstable_deltas[len(unstable_deltas)/2].days
        print "   * mode = %d days" % sorted(unstable_occur.items(),
                                             key=itemgetter(1))[-1][0]




if __name__ == '__main__':
    load_config()
    main()
