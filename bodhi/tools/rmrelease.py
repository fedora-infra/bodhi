#!/usr/bin/python -tt

"""
Verify that all builds that are tagged as updates in koji have the
correct status within bodhi
"""

import sys

from sqlobject import SQLObjectNotFound
from turbogears.database import PackageHub

from bodhi.util import load_config
from bodhi.model import Release, PackageUpdate, PackageBuild
from bodhi.buildsys import get_session

def main():
    load_config()
    __connection__ = hub = PackageHub("bodhi")
    if len(sys.argv) != 2:
        print "Usage: %s <release>" % sys.argv[0]
        sys.exit(1)
    try:
        release = Release.byName(sys.argv[1].upper())
    except SQLObjectNotFound:
        print "Cannot find Release '%s'" % sys.argv[1]
        sys.exit(1)

    for update in PackageUpdate.select(PackageUpdate.q.releaseID == release.id):
        print "Destroying %s" % update.title
        for comment in update.comments:
            comment.destroySelf()
        for build in update.builds:
            build.destroySelf()
        for bug in update.bugs:
            if len(bug.updates) == 1:
                bug.destroySelf()
        update.destroySelf()

    release.destroySelf()
    hub.commit()

if __name__ == '__main__':
    main()
