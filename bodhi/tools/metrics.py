#!/usr/bin/env -tt
"""
A tool for generating statistics for each release.

.. moduleauthor:: Luke Macken <lmacken@redhat.com>
"""

__requires__ = 'bodhi'

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
    proventesters = set()

    for release in Release.select():
        print header(release.long_name)
        updates = PackageUpdate.select(PackageUpdate.q.releaseID==release.id)
        stats[release.name] = {
                'num_updates': updates.count(),
                'num_tested': 0,
                'num_tested_without_karma': 0,
                'num_feedback': 0,
                'num_anon_feedback': 0,
                'num_critpath': 0,
                'num_critpath_approved': 0,
                'num_critpath_unapproved': 0,
                'critpath_without_karma': set(),
                'stable_with_negative_karma': PackageUpdate.select(
                    AND(PackageUpdate.q.releaseID==release.id,
                        PackageUpdate.q.status=='stable',
                        PackageUpdate.q.karma < 0)).count(),
                'bugs': set(),
                'karma': {},
                'deltas': [],
                'occurrences': {},
                'accumulative': timedelta(),
                'packages': defaultdict(int),
                'proventesters': set(),
                'proventesters_1': 0,
                'proventesters_0': 0,
                'proventesters_-1': 0,
                # for tracking number of types of karma
                '1': 0,
                '0': 0,
                '-1': 0,
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

                # Track the # of +1's, -1's, and +0's.
                if comment.author_name != 'bodhi':
                    data[str(comment.karma)] += 1

                if comment.author_group == 'proventesters':
                    data['proventesters'].add(comment.author_name)
                    data['proventesters_%d' % comment.karma] += 1

                # For figuring out if an update has received feedback or not
                if not feedback_done:
                    if (not comment.author.startswith('bodhi')
                        and comment.karma != 0
                        and not comment.anonymous):
                        data['num_feedback'] += 1 # per-release tracking of feedback
                        feedback += 1 # total number of updates that have received feedback
                        feedback_done = True # so we don't run this for each comment

                # Tracking per-author karma & anonymous feedback
                if not comment.author.startswith('bodhi'):
                    if comment.anonymous:
                        # @@: should we track anon +0 comments as "feedback"?
                        if comment.karma != 0:
                            data['num_anon_feedback'] += 1
                    else:
                        # strip the group name from the author names
                        author = comment.author.split('(')[0].strip()
                        if author not in data['karma']:
                            data['karma'][author] = 0
                            karma[author] = 0
                        data['karma'][author] += 1
                        karma[author] += 1

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
                if update.critpath_approved or update.status == 'stable':
                    data['num_critpath_approved'] += 1
                else:
                    if status in ('testing', 'pending'):
                        data['num_critpath_unapproved'] += 1
                data['num_critpath'] += 1
                #if not feedback_done:
                if update.status == 'stable' and update.karma == 0:
                    data['critpath_without_karma'].add(update)
            if testingtime_done:
                data['num_tested'] += 1
                if not feedback_done:
                    data['num_tested_without_karma'] += 1

        data['deltas'].sort()

        print " * %d updates" % data['num_updates']
        print " * %d packages updated" % (len(data['packages']))
        for status in statuses:
            print " * %d %s updates" % (data['num_%s' % status], status)
        for type in types:
            print " * %d %s updates (%0.2f%%)" % (data['num_%s' % type], type,
                    float(data['num_%s' % type]) / data['num_updates'] * 100)
        print " * %d bugs resolved" % len(data['bugs'])
        print " * %d critical path updates (%0.2f%%)" % (data['num_critpath'],
                float(data['num_critpath']) / data['num_updates'] * 100)
        print " * %d approved critical path updates" % (
                data['num_critpath_approved'])
        print " * %d unapproved critical path updates" % (
                data['num_critpath_unapproved'])
        print " * %d updates received feedback (%0.2f%%)" % (
                data['num_feedback'], (float(data['num_feedback']) /
                 data['num_updates'] * 100))
        print " * %d +0 comments" % data['0']
        print " * %d +1 comments" % data['1']
        print " * %d -1 comments" % data['-1']
        print " * %d unique authenticated karma submitters" % (
                len(data['karma']))
        print " * %d proventesters" % len(data['proventesters'])
        print "   * %d +1's from proventesters" % data['proventesters_1']
        print "   * %d -1's from proventesters" % data['proventesters_-1']
        print " * %d anonymous users gave feedback (%0.2f%%)" % (
                data['num_anon_feedback'], float(data['num_anon_feedback']) /
                (data['num_anon_feedback'] + sum(data['karma'].values())) * 100)
        print " * %d out of %d stable updates went through testing (%0.2f%%)" %(
                data['num_tested'], data['num_stable'],
                float(data['num_tested']) / data['num_stable'] * 100)
        print " * %d went from testing to stable *without* karma (%0.2f%%)" %(
                data['num_tested_without_karma'],
                float(data['num_tested_without_karma']) /
                data['num_tested'] * 100)
        print " * %d updates were pushed to stable with negative karma (%0.2f%%)" % (
                data['stable_with_negative_karma'], float(data['stable_with_negative_karma']) / data['num_stable'] * 100)
        # TODO: pushed with negative karma
        print " * %d critical path updates pushed to stable *without* karma" % (
                len(data['critpath_without_karma']))
        #for update in data['critpath_without_karma']:
        #    print "   * %s submitted by %s" % (update.title, update.submitter)
        print " * Time spent in testing:"
        print "   * mean = %d days" % (data['accumulative'].days /
                len(data['deltas']))
        print "   * median = %d days" % (
                data['deltas'][len(data['deltas']) / 2].days)
        print "   * mode = %d days" % (
                sorted(data['occurrences'].items(), key=itemgetter(1))[-1][0])
        #for package in sorted(data['packages'].items(), key=itemgetter(1), reverse=True):
        #    print "    * %s: %d" % (package[0].name, package[1])
        print

    print
    print "Out of %d total updates, %d received feedback (%0.2f%%)" % (
            num_updates, feedback, (float(feedback) / num_updates * 100))
    print "Out of %d total unique karma submitters, the top 50 are:" % (
            len(karma))
    for submitter in sorted(karma.iteritems(), key=itemgetter(1), reverse=True)[:50]:
        print " * %s (%d)" % (submitter[0], submitter[1])


if __name__ == '__main__':
    main()
