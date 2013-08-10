#!/usr/bin/env python
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

from progressbar import ProgressBar, SimpleProgress, Percentage, Bar

from bodhi.util import get_db_from_config


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
    progress = ProgressBar(maxval=all_updates.count())

    for update in progress(all_updates):
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

    dump = file('bodhi-pickledb-%s' % time.strftime("%y%m%d.%H%M"), 'w')
    pickle.dump({'updates': updates, 'releases': releases}, dump)
    dump.close()

def load_db():
    print "\nLoading pickled database %s" % sys.argv[2]
    db = file(sys.argv[2], 'r')
    data = pickle.load(db)

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

    progress = ProgressBar()

    for u in progress(data):
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


def load_sqlalchemy_db():
    print "\nLoading pickled database %s" % sys.argv[2]
    db = file(sys.argv[2], 'r')
    data = pickle.load(db)

    import transaction
    from bodhi.models import DBSession, Base
    from bodhi.models import Release, Update, Build, Comment, User, Bug, CVE
    from bodhi.models import Package, Group
    from bodhi.models import UpdateType, UpdateStatus, UpdateRequest
    from sqlalchemy import create_engine
    from sqlalchemy.orm.exc import NoResultFound

    # Caches for quick lookup
    releases = {}
    packages = {}
    users = {}

    db = get_db_from_config()

    # Allow filtering of releases to load
    whitelist = []
    if '--release' in sys.argv:
        for r in sys.argv[sys.argv.index('--release') + 1].split(','):
            whitelist.append(r)

    # Legacy format was just a list of update dictionaries
    # Now we'll pull things out into an organized dictionary:
    # {'updates': [], 'releases': []}
    if isinstance(data, dict):
        for release in data['releases']:
            try:
                db.query(Release).filter_by(name=release['name']).one()
            except NoResultFound:
                r = Release(**release)
                db.add(r)
        data = data['updates']

    progress = ProgressBar(widgets=[SimpleProgress(), Percentage(), Bar()])

    for u in progress(data):
        try:
            release = releases[u['release'][0]]
        except KeyError:
            try:
                release = db.query(Release).filter_by(name=u['release'][0]).one()
            except NoResultFound:
                release = Release(name=u['release'][0], long_name=u['release'][1],
                                  id_prefix=u['release'][2],
                                  dist_tag=u['release'][3])
                db.add(release)
            releases[u['release'][0]] = release

        if whitelist and release.name not in whitelist:
            continue

        ## Backwards compatbility
        request = u['request']
        if u['request'] == 'move':
            u['request'] = 'stable'
        elif u['request'] == 'push':
            u['request'] = 'testing'
        elif u['request'] == 'unpush':
            u['request'] = 'obsolete'
        if u['approved'] not in (True, False):
            u['approved'] = None
        if u.has_key('update_id'):
            u['updateid'] = u['update_id']
        if not u.has_key('date_modified'):
            u['date_modified'] = None

        # Port to new enum types
        if u['request']:
            if u['request'] == 'stable':
                u['request'] = UpdateRequest.stable
            elif u['request'] == 'testing':
                u['request'] = UpdateRequest.testing
            else:
                raise Exception("Unknown request: %s" % u['request'])

        if u['type'] == 'bugfix':
            u['type'] = UpdateType.bugfix
        elif u['type'] == 'newpackage':
            u['type'] = UpdateType.newpackage
        elif u['type'] == 'enhancement':
            u['type'] = UpdateType.enhancement
        elif u['type'] == 'security':
            u['type'] = UpdateType.security
        else:
            raise Exception("Unknown type: %r" % u['type'])

        if u['status'] == 'pending':
            u['status'] = UpdateStatus.pending
        elif u['status'] == 'testing':
            u['status'] = UpdateStatus.testing
        elif u['status'] == 'obsolete':
            u['status'] = UpdateStatus.obsolete
        elif u['status'] == 'stable':
            u['status'] = UpdateStatus.stable
        elif u['status'] == 'unpushed':
            u['status'] = UpdateStatus.unpushed
        else:
            raise Exception("Unknown status: %r" % u['status'])

        try:
            update = db.query(Update).filter_by(title=u['title']).one()
            continue
        except NoResultFound:
            update = Update(title=u['title'],
                            date_submitted=u['date_submitted'],
                            date_pushed=u['date_pushed'],
                            date_modified=u['date_modified'],
                            release=release,
                            old_updateid=u['updateid'],
                            pushed=u['pushed'],
                            notes=u['notes'],
                            karma=u['karma'],
                            type=u['type'],
                            status=u['status'],
                            request=u['request'],
                            )
                            #approved=u['approved'])
            db.add(update)

            try:
                user = users[u['submitter']]
            except KeyError:
                try:
                    user = db.query(User).filter_by(name=u['submitter']).one()
                except NoResultFound:
                    user = User(name=u['submitter'])
                    db.add(user)
                    user.updates.append(update)
                users[u['submitter']] = user

        ## Create Package and Build objects
        for pkg, nvr in u['builds']:
            try:
                package = packages[pkg]
            except KeyError:
                try:
                    package = db.query(Package).filter_by(name=pkg).one()
                except NoResultFound:
                    package = Package(name=pkg)
                    db.add(package)
                packages[pkg] = package

            try:
                build = db.query(Build).filter_by(nvr=nvr).one()
            except NoResultFound:
                build = Build(nvr=nvr, package=package)
                db.add(build)
                update.builds.append(build)

        ## Create all Bugzilla objects for this update
        for bug_num, bug_title, security, parent in u['bugs']:
            try:
                bug = db.query(Bug).filter_by(bug_id=bug_num).one()
            except NoResultFound:
                bug = Bug(bug_id=bug_num, security=security, parent=parent,
                          title=bug_title)
                db.add(bug)
            update.bugs.append(bug)

        ## Create all CVE objects for this update
        for cve_id in u['cves']:
            try:
                cve = db.query(CVE).filter_by(cve_id=cve_id).one()
            except NoResultFound:
                cve = CVE(cve_id=cve_id)
                db.add(cve)
            update.cves.append(cve)

        ## Create all Comments for this update
        for c in u['comments']:
            try:
                timestamp, author, text, karma, anonymous = c
            except ValueError:
                timestamp, author, text, karma = c
                anonymous = '@' in author

            comment = Comment(timestamp=timestamp, text=text,
                              karma=karma, anonymous=anonymous)
            db.add(comment)
            db.flush()
            update.comments.append(comment)
            if anonymous:
                name = u'anonymous'
            else:
                name = author
            group = None
            if not anonymous and ' (' in name:
                split = name.split(' (')
                name = split[0]
                group = split[1][:-1]
                assert group, name
            try:
                user = users[name]
            except KeyError:
                try:
                    user = db.query(User).filter_by(name=name).one()
                except NoResultFound:
                    user = User(name=name)
                    db.add(user)
                    db.flush()
                    user.updates.append(update)
                users[name] = user

            comment.user = user

            if group:
                try:
                    group = db.query(Group).filter_by(name=group).one()
                except NoResultFound:
                    group = Group(name=group)
                    db.add(group)
                    db.flush()
                user.groups.append(group)

        db.flush()

    transaction.commit()

    print("\nDatabase migration complete!")
    print(" * %d updates" % db.query(Update).count())
    print(" * %d builds" % db.query(Build).count())
    print(" * %d comments" % db.query(Comment).count())
    print(" * %d users" % db.query(User).count())
    print(" * %d bugs" % db.query(Bug).count())
    print(" * %d CVEs" % db.query(CVE).count())

def usage():
    print "Usage: ./pickledb.py [ save | load <file> ] [--release <r1,r2>]"
    sys.exit(-1)

def main():
    #load_config()
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
    elif sys.argv[1] == 'migrate' and len(sys.argv) >= 3:
        load_sqlalchemy_db()
    else:
        usage()

if __name__ == '__main__':
    main()
