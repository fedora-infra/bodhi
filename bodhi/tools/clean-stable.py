res__ = 'bodhi'

import pkg_resources

import os
import sys
import rpm
import turbomail
import turbogears

from sqlobject import SQLObjectNotFound, AND
from turbogears.database import PackageHub

from bodhi.util import load_config, build_evr
from bodhi.model import Release, PackageBuild, PackageUpdate
from bodhi.buildsys import get_session

def compare_builds(testing_build, stable_build, untag, tag):
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
                    if update.status != 'stable':
                        print "%s not stable in bodhi!" % update.title
                        raise SQLObjectNotFound
                    else:
                        pass # TODO: do the untagging?
            except SQLObjectNotFound:
                if untag:
                    print "Untagging via koji"
                    koji = get_session()
                    koji.untagBuild(tag, testing_build['nvr'], force=True)
                else:
                    print "Need to untag koji build %s" % testing_build['nvr']


def clean_stable_builds(untag=False):
    koji = get_session()
    for release in Release.select():
        latest_stable_builds = koji.listTagged(release.stable_tag, latest=True)
        latest_stable_nvrs = [build['nvr'] for build in latest_stable_builds]
        print "Fetched %d latest stable builds tagged with %s" % (
                len(latest_stable_builds), release.stable_tag)
        stable_builds = koji.listTagged(release.stable_tag)
        stable_nvrs = [build['nvr'] for build in stable_builds]
        print "Fetched %d stable builds tagged with %s" % (
                len(stable_builds), release.stable_tag)
        for latest_build in latest_stable_builds:
            for build in stable_builds:
                if build['nvr'] == latest_build['nvr']:
                    continue
                compare_builds(latest_build, build, untag, release.stable_tag)



if __name__ == '__main__':
    load_config()
    #turbomail.start_extension()
    clean_stable_builds('--untag' in sys.argv)
