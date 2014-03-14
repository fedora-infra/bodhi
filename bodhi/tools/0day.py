#!/usr/bin/python -tt
# A script to calculate F11 0day update metrics

import time
from datetime import datetime
from pprint import pprint
from turbogears.database import PackageHub
from bodhi.util import load_config
from bodhi.model import PackageUpdate, Release

def main():
    load_config()
    print "Calculating F11 0day update metrics..."
    updates = {'bugfix': [], 'security': [], 'enhancement': [], 'newpackage': []}
    date = datetime(*time.strptime('06-09-2009', '%m-%d-%Y')[:-2])
    f11 = Release.byName('F11')
    for update in PackageUpdate.select(PackageUpdate.q.releaseID==f11.id):
        for comment in update.comments:
            if comment.author == 'bodhi' and comment.timestamp < date and \
               comment.text.startswith('This update has been pushed to stable'):
                updates[update.type].append(update.title)
                break

    pprint(updates)
    print '=' * 80
    print 'F11 0day stats'
    print ' * %d security' % len(updates['security'])
    print ' * %d bugfixes' % len(updates['bugfix'])
    print ' * %d enhancements' % len(updates['enhancement'])
    print ' * %d newpackage' % len(updates['newpackage'])

if __name__ == '__main__':
    main()
