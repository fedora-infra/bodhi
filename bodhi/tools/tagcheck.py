#!/usr/bin/python -tt
"""
Verify that all builds that are tagged as updates in koji have the
correct status within bodhi
"""
__requires__ = 'bodhi'
import pkg_resources

import sys

from sqlobject import SQLObjectNotFound
from turbogears.database import PackageHub

from bodhi.util import load_config
from bodhi.model import PackageBuild, PackageUpdate, Release
from bodhi.buildsys import get_session, wait_for_tasks

def main():
    load_config()
    __connection__ = hub = PackageHub("bodhi")
    koji = get_session()
    tasks = []
    broke = set()

    # Clean up any stray pending tags
    for release in Release.select():
        print "Finding all pending-testing builds..."
        if release.name.startswith('EL'):
            continue

        tag = release.pending_testing_tag
        tagged = [build['nvr'] for build in koji.listTagged(tag)]
        for nvr in tagged:
            try:
                build = PackageBuild.byNvr(nvr)
                for update in build.updates:
                    if update.status in ('testing', 'stable', 'obsolete'):
                        print "%s %s" % (nvr, update.status)
                        if '--fix' in sys.argv:
                            print "Untagging %s" % nvr
                            koji.untagBuild(tag, nvr, force=True)
            except SQLObjectNotFound:
                print "Can't find build for %s" % nvr
                if '--fix' in sys.argv:
                    print "Untagging %s" % nvr
                    koji.untagBuild(tag, nvr, force=True)

        tag = release.pending_stable_tag
        tagged = [build['nvr'] for build in koji.listTagged(tag)]
        for nvr in tagged:
            try:
                build = PackageBuild.byNvr(nvr)
                for update in build.updates:
                    if update.status in ('pending', 'obsolete', 'stable'):
                        print "%s %s" % (nvr, update.status)
                        if '--fix' in sys.argv:
                            print "Untagging %s" % nvr
                            koji.untagBuild(tag, nvr, force=True)
            except SQLObjectNotFound:
                print "Can't find build for %s" % nvr
                if '--fix' in sys.argv:
                    print "Untagging %s" % nvr
                    koji.untagBuild(tag, nvr, force=True)

    # Check for testing updates that aren't tagged properly
    for update in PackageUpdate.select(PackageUpdate.q.status=='testing'):
        dest_tag = update.release.testing_tag
        for build in update.builds:
            tags = [tag['name'] for tag in koji.listTags(build=build.nvr)]
            if dest_tag not in tags:
                print "%s marked as testing, but tagged with %s" % (build.nvr,
                                                                    tags)
                if '--fix' in sys.argv:
                    broke.add((tags[0], dest_tag, build.nvr))

    # Check all candidate updates to see if they are in a different bodhi state
    for release in Release.select():
        tag = release.candidate_tag
        tagged = [build['nvr'] for build in koji.listTagged(tag, latest=True)]
        for nvr in tagged:
            try:
                build = PackageBuild.byNvr(nvr)
                for update in build.updates:
                    if update.status in ('testing', 'stable'):
                        print "%s %s but tagged as %s" % (nvr,
                                                          update.status,
                                                          tag)
                        if '--fix' in sys.argv:
                            dest = release.testing_tag
                            if update.status == 'stable':
                                dest = release.stable_tag
                            elif update.status == 'obsolete':
                                dest = release.candidate_tag
                            broke.add((tag, dest, nvr))
            except SQLObjectNotFound:
                pass

    # Make sure that all builds in koji tagged as an update exist
    # in bodhi, and are in the expect state.
    for release in Release.select():
        for tag in (release.testing_tag, release.stable_tag):
            tagged = [build['nvr'] for build in koji.listTagged(tag, latest=True)]
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
                        if '--fix' in sys.argv:
                            dest = release.testing_tag
                            if update.status == 'stable':
                                dest = release.stable_tag
                            elif update.status == 'obsolete':
                                dest = release.candidate_tag
                            for b in update.builds:
                                broke.add((tag, dest, b.nvr))

    if broke:
        print " ** Fixing broken tags! **"
        koji.multicall = True
        for tag, dest, build in broke:
            print "Moving %s from %s to %s" % (build, tag, dest)
            koji.moveBuild(tag, dest, build, force=True)
        print "Running koji.multiCall()"
        results = koji.multiCall()
        success = False
        print "Waiting for tasks"
        bad_tasks = wait_for_tasks([task[0] for task in results])
        if bad_tasks == 0:
            success = True
        if success:
            print "Tags successfully moved!"
        else:
            print "Error moving tags!"
            print "bad_tasks = %r" % bad_tasks


if __name__ == '__main__':
    main()

# vim: ts=4 sw=4 expandtab
