# A script to find builds tagged with f21 *and* f21-updates

__requires__ = 'bodhi'
import pkg_resources

import sys

from bodhi.util import load_config
from bodhi.model import Release
from bodhi.buildsys import get_session


def list_tagged(tag):
    koji = get_session()
    builds = koji.listTagged(tag)
    nvrs = [build['nvr'] for build in builds]
    print "Fetched %d builds tagged with %s" % (
        len(builds), tag)
    return nvrs


def clean_stable_builds(release):
    dist_builds = list_tagged(release.dist_tag)
    stable_builds = list_tagged(release.stable_tag)
    for stable_build in stable_builds:
        if stable_build in dist_builds:
            print(stable_build)


if __name__ == '__main__':
    load_config()
    release = Release.byName('F21')
    clean_stable_builds(release)
