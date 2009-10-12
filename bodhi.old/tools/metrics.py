#!/usr/bin/python -tt

"""
A tool for spitting out basic update and bug metrics for each release
"""

from sqlobject import AND
from turbogears.database import PackageHub

from bodhi.util import load_config
from bodhi.model import PackageUpdate, Release

def main():
    load_config()
    for release in Release.select():
        print release.long_name
        updates = PackageUpdate.select(
                AND(PackageUpdate.q.releaseID == release.id,
                    PackageUpdate.q.status == 'stable'))
        num_updates = updates.count()
        print " * %d stable updates" % num_updates
        bugs = set()
        for update in updates:
            for bug in update.bugs:
                bugs.add(bug)
        print " * %d bugs" % len(bugs)


if __name__ == '__main__':
    main()
