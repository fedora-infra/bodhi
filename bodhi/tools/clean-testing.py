#!/usr/bin/python -tt

"""
A tool that untags testing builds that have a newer build tagged as stable.
"""

import sys
import rpm

from bodhi.util import load_config
from bodhi.model import Release
from bodhi.buildsys import get_session

def clean_testing_builds(untag=False):
    koji = get_session()
    for release in Release.select():
        stable_builds = koji.listTagged('%s-updates' % release.dist_tag, latest=True)
        print "Fetched %d builds tagged with %s-updates" % (len(stable_builds),
                '%s-updates' % release.dist_tag)
        testing_builds = koji.listTagged('%s-updates-testing' % release.dist_tag,
                                         latest=True)
        print "Fetched %d builds tagged with %s-updates-testing" % (
                len(testing_builds), release.dist_tag)
        for testing_build in testing_builds:
            for stable_build in stable_builds:
                if stable_build['package_name'] == testing_build['package_name']:
                    if rpm.labelCompare((str(testing_build['epoch']),
                                         testing_build['version'],
                                         testing_build['release']),
                                        (str(stable_build['epoch']),
                                         stable_build['version'],
                                         stable_build['release'])) < 0:
                        print "%s is older than %s" % (testing_build['nvr'],
                                                       stable_build['nvr'])
                        if untag:
                            print "Untagging koji build %s" % testing_build['nvr']
                            koji.untagBuild('%s-updates-testing',
                                            testing_build['nvr'])

        print

if __name__ == '__main__':
    load_config()
    clean_testing_builds('--untag' in sys.argv)
