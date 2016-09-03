#!/usr/bin/env python
import __main__
__requires__ = __main__.__requires__ = 'WebOb>=1.4.1'
import pkg_resources

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""
This script pickles all updates/bugs/cves/comments and writes it out to disk
in the format of bodhi-pickledb-YYYYMMDD.HHMM
"""

__requires__ = 'bodhi'

import sys

import cPickle as pickle

from progressbar import ProgressBar, SimpleProgress, Percentage, Bar
from pyramid.paster import setup_logging
setup_logging('/etc/bodhi/production.ini')

from sqlalchemy.orm import scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension

from bodhi.server.util import get_critpath_pkgs
import bodhi


def load_sqlalchemy_db():
    print "\nLoading pickled database %s" % sys.argv[2]
    db = file(sys.argv[2], 'r')
    data = pickle.load(db)

    import transaction
    from bodhi.server.models import Base
    from bodhi.server.models import Release, Update, Build, Comment, User, Bug, CVE
    from bodhi.server.models import Package, Group
    from bodhi.server.models import UpdateType, UpdateStatus, UpdateRequest
    from sqlalchemy import create_engine
    from sqlalchemy.orm.exc import NoResultFound

    # Caches for quick lookup
    releases = {}
    packages = {}
    users = {}
    critpath = {}

    aliases = []

    engine = bodhi.server.config['sqlalchemy.url']
    Session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
    Session.configure(bind=engine)
    db = Session()

    # Allow filtering of releases to load
    whitelist = []
    if '--release' in sys.argv:
        for r in sys.argv[sys.argv.index('--release') + 1].split(','):
            whitelist.append(r)
        print('whitelist = %r' % whitelist)

    # Legacy format was just a list of update dictionaries
    # Now we'll pull things out into an organized dictionary:
    # {'updates': [], 'releases': []}
    if isinstance(data, dict):
        for release in data['releases']:
            try:
                db.query(Release).filter_by(name=release['name']).one()
            except NoResultFound:
                del(release['metrics'])
                del(release['locked'])
                r = Release(**release)
                r.stable_tag = "%s-updates" % r.dist_tag
                r.testing_tag = "%s-testing" % r.stable_tag
                r.candidate_tag = "%s-candidate" % r.stable_tag
                r.pending_testing_tag = "%s-pending" % r.testing_tag
                r.pending_stable_tag = "%s-pending" % r.stable_tag
                r.override_tag = "%s-override" % r.dist_tag
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
            if whitelist:
                if release.name in whitelist:
                    critpath[release.name] = get_critpath_pkgs(release.name.lower())
                    print('%s critpath packages for %s' % (len(critpath[release.name]),
                                                           release.name))
            else:
                critpath[release.name] = get_critpath_pkgs(release.name.lower())
                print('%s critpath packages for %s' % (len(critpath[release.name]),
                                                       release.name))

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
            u['alias'] = u['update_id']

            if u['alias']:
                split = u['alias'].split('-')
                year, id = split[-2:]
                aliases.append((int(year), int(id)))

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
                            alias=u['updateid'],
                            pushed=u['pushed'],
                            notes=u['notes'],
                            karma=u['karma'],
                            type=u['type'],
                            status=u['status'],
                            request=u['request'],
                            )
                            #approved=u['approved'])
            db.add(update)
            db.flush()

            try:
                user = users[u['submitter']]
            except KeyError:
                try:
                    user = db.query(User).filter_by(name=u['submitter']).one()
                except NoResultFound:
                    user = User(name=u['submitter'])
                    db.add(user)
                    db.flush()
                users[u['submitter']] = user
            user.updates.append(update)

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
            if package.name in critpath[update.release.name]:
                update.critpath = True
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

    # Hack to get the Bodhi2 alias generator working with bodhi1 data.
    # The new generator assumes that the alias is assigned at submission time, as opposed to push time.
    year, id = max(aliases)
    print('Highest alias = %r %r' % (year, id))
    up = db.query(Update).filter_by(alias=u'FEDORA-%s-%s' % (year, id)).one()
    print(up.title)
    up.date_submitted = up.date_pushed
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
    print "Usage: ./pickledb.py [ load <file> ] [--release <r1,r2>]"
    sys.exit(-1)


def main():
    if len(sys.argv) < 2:
        usage()
    elif sys.argv[1] == 'load' and len(sys.argv) == 3:
        load_sqlalchemy_db()
    elif sys.argv[1] == 'migrate' and len(sys.argv) >= 3:
        load_sqlalchemy_db()
    else:
        usage()

if __name__ == '__main__':
    main()
