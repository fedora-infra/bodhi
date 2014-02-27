#!/usr/bin/python -tt
# $Id: $
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

"""
This script pickles all updates/bugs/cves/comments and writes it out to disk
in the format of bodhi-pickledb-YYYYMMDD.HHMM
"""

__requires__ = 'bodhi'

import sys
import time
import cPickle as pickle

from os.path import isfile
from sqlobject import SQLObjectNotFound
from turbogears.database import PackageHub

from bodhi.util import ProgressBar, load_config
from bodhi.exceptions import (DuplicateEntryError, SQLiteIntegrityError,
                              PostgresIntegrityError)
from bodhi.model import (PackageUpdate, Release, Comment, Bugzilla, CVE,
                         Package, PackageBuild, BuildRootOverride)

hub = __connection__ = PackageHub("bodhi")

def save_db():
    ## Save each release and it's metrics
    releases = []
    for release in Release.select():
        rel = {}
        for attr in ('name', 'long_name', 'id_prefix', 'dist_tag',
                     'locked', 'metrics'):
            rel[attr] = getattr(release, attr)
        releases.append(rel)

    updates = []
    all_updates = PackageUpdate.select()
    progress = ProgressBar(maxValue=all_updates.count())

    for update in all_updates:
        data = {}
        data['title'] = update.title
        data['builds'] = [(build.package.name, build.nvr) for build in update.builds]
        data['date_submitted'] = update.date_submitted
        data['date_pushed'] = update.date_pushed
        data['date_modified'] = update.date_modified
        data['release'] = [update.release.name, update.release.long_name,
                           update.release.id_prefix, update.release.dist_tag]
        data['submitter'] = update.submitter
        data['update_id'] = hasattr(update, 'update_id') and update.update_id or update.updateid
        data['type'] = update.type
        data['karma'] = update.karma
        data['cves'] = [cve.cve_id for cve in update.cves]
        data['bugs'] = []
        for bug in update.bugs:
            data['bugs'].append([bug.bz_id, bug.title, bug.security])
            if hasattr(bug, 'parent'):
                data['bugs'][-1].append(bug.parent)
            else:
                data['bugs'][-1].append(False)
        data['status'] = update.status
        data['pushed'] = update.pushed
        data['notes'] = update.notes
        data['request'] = update.request
        data['comments'] = [(c.timestamp, c.author, c.text, c.karma, c.anonymous) for c in update.comments]
        if hasattr(update, 'approved'):
            data['approved'] = update.approved
        else:
            data['approved'] = None

        updates.append(data)
        progress()

    # Save all buildroot overrides
    overrides = []
    for override in BuildRootOverride.select():
        try:
            overrides.append(override.__json__())
        except:
            print("Removing stray override: %s" % override)
            override.destroySelf()

    dump = file('bodhi-pickledb-%s' % time.strftime("%y%m%d.%H%M"), 'w')
    pickle.dump({'updates': updates, 'releases': releases, 'overrides': overrides}, dump)
    dump.close()

def load_db():
    print "\nLoading pickled database %s" % sys.argv[2]
    db = file(sys.argv[2], 'r')
    data = pickle.load(db)

    # Load up all of the overrides
    for override in data.get('overrides', []):
        try:
            BuildRootOverride.byBuild(override['build'])
        except SQLObjectNotFound:
            BuildRootOverride(**override)

    # Legacy format was just a list of update dictionaries
    # Now we'll pull things out into an organized dictionary:
    # {'updates': [], 'releases': []}
    if isinstance(data, dict):
        for release in data['releases']:
            try:
                Release.byName(release['name'])
            except SQLObjectNotFound:
                Release(**release)
        data = data['updates']

    progress = ProgressBar(maxValue=len(data))

    for u in data:
        try:
            release = Release.byName(u['release'][0])
        except SQLObjectNotFound:
            release = Release(name=u['release'][0], long_name=u['release'][1],
                              id_prefix=u['release'][2], dist_tag=u['release'][3])

        ## Backwards compatbility
        request = u['request']
        if u['request'] == 'move':
            request = 'stable'
        elif u['request'] == 'push':
            request = 'testing'
        elif u['request'] == 'unpush':
            request = 'obsolete'
        if u['approved'] in (True, False):
            u['approved'] = None
        if u.has_key('update_id'):
            u['updateid'] = u['update_id']
        if not u.has_key('date_modified'):
            u['date_modified'] = None

        try:
            update = PackageUpdate.byTitle(u['title'])
        except SQLObjectNotFound:
            update = PackageUpdate(title=u['title'],
                                   date_submitted=u['date_submitted'],
                                   date_pushed=u['date_pushed'],
                                   date_modified=u['date_modified'],
                                   release=release,
                                   submitter=u['submitter'],
                                   updateid=u['updateid'],
                                   type=u['type'],
                                   status=u['status'],
                                   pushed=u['pushed'],
                                   notes=u['notes'],
                                   karma=u['karma'],
                                   request=request,
                                   approved=u['approved'])

        ## Create Package and PackageBuild objects
        for pkg, nvr in u['builds']:
            try:
                package = Package.byName(pkg)
            except SQLObjectNotFound:
                package = Package(name=pkg)
            try:
                build = PackageBuild.byNvr(nvr)
            except SQLObjectNotFound:
                build = PackageBuild(nvr=nvr, package=package)
            update.addPackageBuild(build)

        ## Create all Bugzilla objects for this update
        for bug_num, bug_title, security, parent in u['bugs']:
            try:
                bug = Bugzilla.byBz_id(bug_num)
            except SQLObjectNotFound:
                bug = Bugzilla(bz_id=bug_num, security=security, parent=parent)
                bug.title = bug_title
            update.addBugzilla(bug)

        ## Create all CVE objects for this update
        for cve_id in u['cves']:
            try:
                cve = CVE.byCve_id(cve_id)
            except SQLObjectNotFound:
                cve = CVE(cve_id=cve_id)
            update.addCVE(cve)
        for timestamp, author, text, karma, anonymous in u['comments']:
            comment = Comment(timestamp=timestamp, author=author, text=text,
                              karma=karma, update=update, anonymous=anonymous)

        progress()

def usage():
    print "Usage: ./pickledb.py [ save | load <file> ]"
    sys.exit(-1)

def main():
    load_config()
    if len(sys.argv) < 2:
        usage()
    elif sys.argv[1] == 'save':
        print "Pickling database..."
        save_db()
    elif sys.argv[1] == 'load' and len(sys.argv) == 3:
        try:
            hub.begin()
            load_db()
        finally:
            hub.commit()
    else:
        usage()

if __name__ == '__main__':
    main()
