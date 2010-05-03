#!/usr/bin/env -tt
"""
A tool for generating statistics for each release.

.. moduleauthor:: Luke Macken <lmacken@redhat.com>
"""

from operator import itemgetter
from sqlobject import AND
from datetime import timedelta
from collections import defaultdict
from turbogears.database import PackageHub

from bodhi.util import load_config, header
from bodhi.model import PackageUpdate, Release

statuses = ('stable', 'testing', 'pending', 'obsolete')
types = ('bugfix', 'enhancement', 'security', 'newpackage')

def main():
    load_config()
    stats = {} # {release: {'stat': ...}}
    feedback = 0 # total number of updates that received feedback
    karma = {} # {username: # of karma submissions}
    num_updates = PackageUpdate.select().count()

    for release in Release.select():
        print header(release.long_name)
        updates = PackageUpdate.select(PackageUpdate.q.releaseID==release.id)
        stats[release.name] = {
                'num_updates': updates.count(),
                'num_testing': 0,
                'num_testing_without_karma': 0,
                'num_feedback': 0,
                'num_anon_feedback': 0,
                'num_critpath': 0,
                'critpath_without_karma': set(),
                'bugs': set(),
                'karma': {},
                'deltas': [],
                'occurrences': {},
                'accumulative': timedelta(),
                'packages': defaultdict(int),
                }
        data = stats[release.name]

        for status in statuses:
            data['num_%s' % status] = PackageUpdate.select(AND(
                PackageUpdate.q.releaseID==release.id,
                PackageUpdate.q.status==status)).count()

        for type in types:
            data['num_%s' % type] = PackageUpdate.select(AND(
                PackageUpdate.q.releaseID==release.id,
                PackageUpdate.q.type==type)).count()

        for update in release.updates:
            for build in update.builds:
                data['packages'][build.package] += 1
            for bug in update.bugs:
                data['bugs'].add(bug.bz_id)

            feedback_done = False
            testingtime_done = False

            for comment in update.comments:
                if not feedback_done and (not comment.author.startswith('bodhi')
                    and comment.karma != 0 and '@' not in comment.author):
                    data['num_feedback'] += 1
                    feedback += 1
                    feedback_done = True
                if not comment.author.startswith('bodhi'):
                    if comment.anonymous or '@' in comment.author:
                        if comment.karma != 0:
                            data['num_anon_feedback'] += 1
                    else:
                        if comment.author not in data['karma']:
                            data['karma'][comment.author] = 0
                            karma[comment.author] = 0
                        data['karma'][comment.author] += 1
                        karma[comment.author] += 1
                if (not testingtime_done and
                    comment.text == 'This update has been pushed to testing'):
                    for othercomment in update.comments:
                        if othercomment.text == 'This update has been pushed to stable':
                            delta = othercomment.timestamp - comment.timestamp
                            data['deltas'].append(delta)
                            data['occurrences'][delta.days] = \
                                data['occurrences'].setdefault(
                                        delta.days, 0) + 1
                            data['accumulative'] += delta
                            testingtime_done = True
                            break

            if update.critpath:
                data['num_critpath'] += 1
                if not feedback_done:
                    data['critpath_without_karma'].add(update)
            if testingtime_done:
                data['num_testing'] += 1
                if not feedback_done:
                    data['num_testing_without_karma'] += 1

        data['deltas'].sort()

        print " * %d updates" % data['num_updates']
        for status in statuses:
            print " * %d %s updates" % (data['num_%s' % status], status)
        for type in types:
            print " * %d %s updates (%0.2f%%)" % (data['num_%s' % type], type,
                    float(data['num_%s' % type]) / data['num_updates'] * 100)
        print " * %d critical path updates (%0.2f%%)" % (data['num_critpath'],
                float(data['num_critpath']) / data['num_updates'] * 100)
        print " * %d updates received feedback (%0.2f%%)" % (
                data['num_feedback'], (float(data['num_feedback']) /
                 data['num_updates'] * 100))
        print " * %d unique authenticated karma submitters" % (
                len(data['karma']))
        print " * %d anonymous users gave feedback (%0.2f%%)" % (
                data['num_anon_feedback'], float(data['num_anon_feedback']) /
                (data['num_anon_feedback'] + sum(data['karma'].values())) * 100)
        print " * %d out of %d updates went through testing (%0.2f%%)" % (
                data['num_testing'], data['num_updates'],
                float(data['num_testing']) / data['num_updates'] * 100)
        print " * %d testing updates were pushed *without* karma (%0.2f%%)" %(
                data['num_testing_without_karma'],
                float(data['num_testing_without_karma']) /
                data['num_testing'] * 100)
        print " * %d critical path updates pushed *without* karma" % (
                len(data['critpath_without_karma']))
        for update in data['critpath_without_karma']:
            print "   * %s submitted by %s" % (update.title, update.submitter)
        print " * Time spent in testing:"
        print "   * mean = %d days" % (data['accumulative'].days /
                len(data['deltas']))
        print "   * median = %d days" % (
                data['deltas'][len(data['deltas']) / 2].days)
        print "   * mode = %d days" % (
                sorted(data['occurrences'].items(), key=itemgetter(1))[-1][0])
        print " * %d packages updated" % (len(data['packages']))
        for package in sorted(data['packages'].items(), key=itemgetter(1), reverse=True):
            print "    * %s: %d" % (package[0].name, package[1])
        print

    print
    print "Out of %d total updates, %d received feedback (%0.2f%%)" % (
            num_updates, feedback, (float(feedback) / num_updates * 100))
    print "Out of %d total unique karma submitters, the top 30 are:" % (
            len(karma))
    for submitter in sorted(karma.iteritems(), key=itemgetter(1), reverse=True)[:30]:
        print " * %s (%d)" % (submitter[0], submitter[1])

if __name__ == '__main__':
    main()
