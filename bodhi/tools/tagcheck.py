#!/usr/bin/python -tt

"""
Verify that all builds that are tagged as updates in koji have the
correct status within bodhi
"""

from sqlobject import SQLObjectNotFound
from turbogears.database import PackageHub

from bodhi.util import load_config
from bodhi.model import PackageBuild
from bodhi.buildsys import get_session

def main():
    load_config()
    __connection__ = hub = PackageHub("bodhi")
    koji = get_session()
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
                    print "%s is %s in bodhi but tagged as %s in koji" % (update.title,
                                                                          update.status,
                                                                          tag)

if __name__ == '__main__':
    main()
