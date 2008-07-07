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
    for tag in ('dist-fc7-updates-testing', 'dist-fc7-updates',
                'dist-f8-updates-testing', 'dist-f8-updates'):
        tagged = [build['nvr'] for build in koji.listTagged(tag)]
        for nvr in tagged:
            try:
                build = PackageBuild.byNvr(nvr)
            except SQLObjectNotFound:
                print "PackageUpdate(%s) not found!" % nvr
                continue
            if not build.update:
                print "PackageBuild(%s) has no update" % (build.nvr)
            status = 'testing' in tag and 'testing' or 'stable'
            if build.update.status != status:
                print "%s is not tagged as %s in koji" % (build.nvr, status)

if __name__ == '__main__':
    main()
