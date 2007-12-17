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

import sys
import time
import cPickle as pickle

from os.path import isfile
from sqlobject import SQLObjectNotFound
from turbogears.database import PackageHub
from turbogears import update_config
from bodhi.exceptions import (DuplicateEntryError, SQLiteIntegrityError, 
                              PostgresIntegrityError)
from bodhi.model import (PackageUpdate, Release, Comment, Bugzilla, CVE,
                         Package, PackageBuild)

hub = __connection__ = PackageHub("bodhi")

def load_config():
    configfile = 'prod.cfg'
    if not isfile(configfile):
        configfile = 'bodhi.cfg'
    update_config(configfile=configfile, modulename='bodhi.config')

def save_db():
    load_config()
    updates = []

    for update in PackageUpdate.select():
        print update.title
        data = {}
        data['title'] = update.title
        data['builds'] = [(build.package.name, build.nvr) for build in update.builds]
        data['date_submitted'] = update.date_submitted
        data['date_pushed'] = update.date_pushed
        data['release'] = [update.release.name, update.release.long_name,
                           update.release.id_prefix, update.release.dist_tag]
        data['submitter'] = update.submitter
        data['update_id'] = update.update_id
        data['type'] = update.type
        data['karma'] = update.karma
        data['cves'] = [cve.cve_id for cve in update.cves]
        data['bugs'] = []
        for bug in update.bugs:
            data['bugs'].append([bug.bz_id, bug.title, bug.security, bug.parent])
            if hasattr(bug, 'parent'):
                data['bugs'][-1].append(bug.parent)
        data['status'] = update.status
        data['pushed'] = update.pushed
        data['notes'] = update.notes
        data['request'] = update.request
        data['comments'] = [(c.timestamp, c.author, c.text, c.karma) for c in update.comments]
        updates.append(data)

    dump = file('bodhi-pickledb-%s' % time.strftime("%y%m%d.%H%M"), 'w')
    pickle.dump(updates, dump)
    dump.close()

def load_db():
    print "Loading pickled database %s" % sys.argv[2]
    load_config()
    db = file(sys.argv[2], 'r')
    data = pickle.load(db)
    for u in data:
        try:
            release = Release.byName(u['release'][0])
        except SQLObjectNotFound:
            release = Release(name=u['release'][0], long_name=u['release'][1],
                              id_prefix=u['release'][2], dist_tag=u['release'][3])
        request = u['request']
        if u['request'] == 'move':
            request = 'stable'
        elif u['request'] == 'push':
            request = 'testing'
        elif u['request'] == 'unpush':
            request = 'obsolete'

        update = PackageUpdate(title=u['title'],
                               date_submitted=u['date_submitted'],
                               date_pushed=u['date_pushed'],
                               release=release,
                               submitter=u['submitter'],
                               update_id=u['update_id'],
                               type=u['type'],
                               status=u['status'],
                               pushed=u['pushed'],
                               notes=u['notes'],
                               karma=u['karma'],
                               request=request)

        for pkg, nvr in u['builds']:
            try:
                package = Package.byName(pkg)
            except SQLObjectNotFound:
                package = Package(name=pkg)
            build = PackageBuild(nvr=nvr, package=package)
            update.addPackageBuild(build)

        for bug_num, bug_title, security, parent in u['bugs']:
            try:
                bug = Bugzilla(bz_id=bug_num, security=security, parent=parent)
                bug.title = bug_title
            except (DuplicateEntryError, SQLiteIntegrityError,
                    PostgresIntegrityError):
                bug = Bugzilla.byBz_id(bug_num)
            update.addBugzilla(bug)

        for cve_id in u['cves']:
            try:
                cve = CVE(cve_id=cve_id)
            except (DuplicateEntryError, SQLiteIntegrityError,
                    PostgresIntegrityError):
                cve = CVE.byCve_id(cve_id)
            update.addCVE(cve)
        for timestamp, author, text, karma in u['comments']:
            comment = Comment(timestamp=timestamp, author=author, text=text,
                              karma=karma, update=update)

        print update
        print

def usage():
    print "Usage: ./pickledb.py [ save | load <file> ]"
    sys.exit(-1)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        usage()
    elif sys.argv[1] == 'save':
        print "Pickling database..."
        save_db()
    elif sys.argv[1] == 'load' and len(sys.argv) == 3:
        print "Loading db"
        load_db()
    else:
        usage()
