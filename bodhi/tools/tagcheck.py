#!/usr/bin/python -tt

"""
Verify that all builds that are tagged as updates in koji have the
correct status within bodhi
"""

from sqlobject import SQLObjectNotFound
from turbogears.database import PackageHub

from bodhi.util import load_config
from bodhi.model import PackageBuild, PackageUpdate
from bodhi.buildsys import get_session

def main():
    load_config()
    __connection__ = hub = PackageHub("bodhi")
    koji = get_session()

    # Check for testing updates that aren't tagged properly
    for update in PackageUpdate.select(PackageUpdate.q.status=='testing'):
        for build in update.builds:
            tags = [tag['name'] for tag in koji.listTags(build=build.nvr)]
            if '%s-updates-testing' % update.release.dist_tag not in tags:
                print "%s marked as testing, but tagged with %s" % (build.nvr,
                                                                    tags)

    # Check all candidate updates to see if they are in a different bodhi state
    for tag in ('dist-f9-updates-candidate', 'dist-f8-updates-candidate'):
        tagged = [build['nvr'] for build in koji.listTagged(tag)]
        for nvr in tagged:
            try:
                build = PackageBuild.byNvr(nvr)
                for update in build.updates:
                    if update.status in ('testing', 'stable'):
                        print "%s %s but tagged as %s" % (nvr,
                                                          update.status,
                                                          tag)
            except SQLObjectNotFound:
                pass

    # Make sure that all builds in koji tagged as an update exist
    # in bodhi, and are in the expect state.
    for tag in ('dist-f9-updates-testing', 'dist-f9-updates',
                'dist-f8-updates-testing', 'dist-f8-updates'):
        tagged = [build['nvr'] for build in koji.listTagged(tag)]
        for nvr in tagged:
            try:
                build = PackageBuild.byNvr(nvr)
            except SQLObjectNotFound:
                print "PackageUpdate(%s) not found!" % nvr
                continue
            if not len(build.updates):
                print "PackageBuild(%s) has no updates" % (build.nvr)
            status = 'testing' in tag and 'testing' or 'stable'
            for update in build.updates:
                if update.status != status:
                    print "%s is %s in bodhi but tagged as %s in koji" % (
                            update.title, update.status, tag)


if __name__ == '__main__':
    main()

# vim: ts=4 sw=4 expandtab
