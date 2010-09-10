#!/usr/bin/python -tt

"""
A tool that untags testing builds that have a newer build tagged as stable.
"""

import os
import sys
import rpm
import turbomail
import turbogears

from sqlobject import SQLObjectNotFound, AND
from turbogears.database import PackageHub

from bodhi.util import load_config
from bodhi.model import Release, PackageBuild, PackageUpdate
from bodhi.buildsys import get_session

def compare_builds(testing_build, stable_build, untag):
    if stable_build['package_name'] == testing_build['package_name']:
        if rpm.labelCompare((str(testing_build['epoch']),
                             testing_build['version'],
                             testing_build['release']),
                            (str(stable_build['epoch']),
                             stable_build['version'],
                             stable_build['release'])) < 0:
            print "%s is older than %s" % (testing_build['nvr'],
                                           stable_build['nvr'])
            try:
                build = PackageBuild.byNvr(testing_build['nvr'])
                for update in build.updates:
                    if update.status != 'testing':
                        print "%s not testing in bodhi!" % update.title
                        raise SQLObjectNotFound
                    else:
                        if untag:
                            print "Obsoleting via bodhi"
                            update.obsolete(newer=stable_build['nvr'])
                        else:
                             print "Need to obsolete via bodhi"
            except SQLObjectNotFound:
                if untag:
                    print "Untagging via koji"
                    koji.untagBuild(release.testing_tag,
                                    testing_build['nvr'],
                                    force=True)
                else:
                    print "Need to untag koji build %s" % testing_build['nvr']


def clean_testing_builds(untag=False):
    koji = get_session()
    for release in Release.select():
        stable_builds = koji.listTagged(release.stable_tag, latest=True)
        stable_nvrs = [build['nvr'] for build in stable_builds]
        print "Fetched %d builds tagged with %s" % (
                len(stable_builds), release.stable_tag)
        testing_builds = koji.listTagged(release.testing_tag, latest=True)
        print "Fetched %d builds tagged with %s" % (
                len(testing_builds), release.testing_tag)
        testing_nvrs = [build['nvr'] for build in testing_builds]
        for testing_build in testing_builds:
            for build in testing_builds:
                compare_builds(testing_build, build, untag)
            for build in stable_builds:
                compare_builds(testing_build, build, untag)

        # Find testing updates that aren't in the list of latest builds
        for update in PackageUpdate.select(AND(PackageUpdate.q.releaseID==release.id,
                                               PackageUpdate.q.status=='testing',
                                               PackageUpdate.q.request==None)):
            for build in update.builds:
                if build.nvr not in testing_nvrs:
                    latest_testing = None
                    latest_stable = None
                    for testing in testing_nvrs:
                        if testing.startswith(build.package.name + '-'):
                            latest_testing = testing
                            break
                    for stable in stable_nvrs:
                        if stable.startswith(build.package.name + '-'):
                            latest_stable = stable
                            break
                    print "%s in testing, latest_testing = %s, latest_stable = %s" % (
                            update.title, latest_testing, latest_stable)
                    if untag:
                        print "Obsoleting %s" % update.title
                        assert latest_testing
                        update.obsolete(newer=latest_testing)


if __name__ == '__main__':
    load_config()
    turbomail.start_extension()
    clean_testing_builds('--untag' in sys.argv)
