import os
import re
import time
import logging
import xmlrpclib

from textwrap import wrap
from datetime import datetime
from collections import defaultdict

from sqlalchemy import Unicode, UnicodeText, PickleType, Integer, Boolean
from sqlalchemy import DateTime
from sqlalchemy import Table, Column, ForeignKey
from sqlalchemy import and_, or_
from sqlalchemy.orm import scoped_session, sessionmaker, relationship, backref
from sqlalchemy.orm import class_mapper
from sqlalchemy.orm.properties import RelationshipProperty
from sqlalchemy.ext.declarative import declarative_base, synonym_for
from sqlalchemy.orm.exc import NoResultFound
from zope.sqlalchemy import ZopeTransactionExtension
from pyramid.settings import asbool

from bodhi import buildsys, mail
from bodhi.util import (
    header, build_evr, rpm_fileheader, get_nvr, flash_log,
    get_age, get_critpath_pkgs,
)

from bodhi.util import get_age_in_days
from bodhi.models.enum import DeclEnum, EnumSymbol
from bodhi.exceptions import RPMNotFound
from bodhi.config import config
from bodhi.bugs import bugtracker

log = logging.getLogger(__name__)

try:
    import rpm
except ImportError:
    log.warning("Could not import 'rpm'")


class BodhiBase(object):
    """ Our custom model base class """
    __exclude_columns__ = ('id',)  # List of columns to exclude from JSON
    __get_by__ = ()  # Columns that get() will query

    id = Column(Integer, primary_key=True)

    @classmethod
    def get(cls, id, db):
        return db.query(cls).filter(or_(
            getattr(cls, col) == id for col in cls.__get_by__
        )).first()

    def __getitem__(self, key):
        return getattr(self, key)

    def __repr__(self):
        return '<{} {}>'.format(self.__class__.__name__, self.__json__())

    def __json__(self, request=None):
        return self._to_json(self, request=request)

    def _to_json(self, obj, seen=None, request=None):
        if not seen:
            seen = []
        if not obj:
            return

        exclude = getattr(obj, '__exclude_columns__', [])
        properties = list(class_mapper(type(obj)).iterate_properties)
        rels = [p.key for p in properties if type(p) is RelationshipProperty]
        attrs = [p.key for p in properties if p.key not in rels]
        d = dict([(attr, getattr(obj, attr)) for attr in attrs
                  if attr not in exclude and not attr.startswith('_')])

        for attr in rels:
            if attr in exclude:
                continue
            d[attr] = self._expand(obj, getattr(obj, attr), seen)
        for key, value in d.iteritems():
            if isinstance(value, datetime):
                d[key] = value.strftime('%Y-%m-%d %H:%M:%S')
            if isinstance(value, EnumSymbol):
                d[key] = unicode(value)

        return d

    def _expand(self, obj, relation, seen):
        """ Return the to_json or id of a sqlalchemy relationship. """
        if hasattr(relation, 'all'):
            relation = relation.all()
        if hasattr(relation, '__iter__'):
            return [self._expand(obj, item, seen) for item in relation]
        if type(relation) not in seen:
            return self._to_json(relation, seen=seen + [type(obj)])
        else:
            return relation.id

    @classmethod
    def grid_columns(cls):
        columns = []
        exclude = getattr(cls, '__exclude_columns__', [])
        for col in cls.__table__.columns:
            if col.name in exclude:
                continue
            columns.append(col.name)
        return columns


Base = declarative_base(cls=BodhiBase)
metadata = Base.metadata
DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))


##
## Enumerated type declarations
##

class UpdateStatus(DeclEnum):
    pending = 'pending', 'pending'
    testing = 'testing', 'testing'
    stable = 'stable', 'stable'
    unpushed = 'unpushed', 'unpushed'
    obsolete = 'obsolete', 'obsolete'
    processing = 'processing', 'processing'


class UpdateType(DeclEnum):
    bugfix = 'bugfix', 'bugfix'
    security = 'security', 'security'
    newpackage = 'newpackage', 'new package'
    enhancement = 'enhancement', 'enhancement'


class UpdateRequest(DeclEnum):
    testing = 'testing', 'testing'
    stable = 'stable', 'stable'
    obsolete = 'obsolete', 'obsolete'
    unpush = 'unpush', 'unpush'


class UpdateSeverity(DeclEnum):
    unspecified = 'unspecified', 'unspecified'
    urgent = 'urgent', 'urgent'
    high = 'high', 'high'
    medium = 'medium', 'medium'
    low = 'low', 'low'


class UpdateSuggestion(DeclEnum):
    unspecified = 'unspecified', 'unspecified'
    reboot = 'reboot', 'reboot'
    logout = 'logout', 'logout'


##
## Association tables
##

#update_release_table = Table('update_release_table', metadata,
#        Column('release_id', Integer, ForeignKey('releases.id')),
#        Column('update_id', Integer, ForeignKey('updates.id')))

#update_build_table = Table('update_build_table', metadata,
#        Column('update_id', Integer, ForeignKey('updates.id')),
#        Column('build_id', Integer, ForeignKey('builds.id')))


##

update_bug_table = Table('update_bug_table', metadata,
        Column('update_id', Integer, ForeignKey('updates.id')),
        Column('bug_id', Integer, ForeignKey('bugs.id')))

update_cve_table = Table('update_cve_table', metadata,
        Column('update_id', Integer, ForeignKey('updates.id')),
        Column('cve_id', Integer, ForeignKey('cves.id')))

bug_cve_table = Table('bug_cve_table', metadata,
        Column('bug_id', Integer, ForeignKey('bugs.id')),
        Column('cve_id', Integer, ForeignKey('cves.id')))

user_package_table = Table('user_package_table', metadata,
        Column('user_id', Integer, ForeignKey('users.id')),
        Column('package_id', Integer, ForeignKey('packages.id')))


class Release(Base):
    __tablename__ = 'releases'
    __exclude_columns__ = ('id', 'metrics', 'builds')
    __get_by__ = ('name', 'long_name', 'dist_tag')

    name = Column(Unicode(10), unique=True, nullable=False)
    long_name = Column(Unicode(25), unique=True, nullable=False)
    version = Column(Unicode(5))
    id_prefix = Column(Unicode(25), nullable=False)
    dist_tag = Column(Unicode(20), nullable=False)
    _stable_tag = Column(UnicodeText)
    _testing_tag = Column(UnicodeText)
    _candidate_tag = Column(UnicodeText)
    # TODO:
    #_pending_tag = Column(UnicodeText)
    locked = Column(Boolean, default=False)
    metrics = Column(PickleType, default=None)

    @property
    def version_int(self):
        regex = re.compile('\D+(\d+)$')
        return int(regex.match(self.name).groups()[0])

    @synonym_for('_stable_tag')
    @property
    def stable_tag(self):
        if self._stable_tag:
            return self._stable_tag
        else:
            if self.name.startswith('EL'):  # EPEL Hack.
                return self.dist_tag
            else:
                return '%s-updates' % self.dist_tag

    @synonym_for('_testing_tag')
    @property
    def testing_tag(self):
        if self._testing_tag:
            return self._testing_tag
        else:
            if self.locked:
                return '%s-updates-testing' % self.stable_tag
            return '%s-testing' % self.stable_tag

    @synonym_for('_candidate_tag')
    @property
    def candidate_tag(self):
        if self._candidate_tag:
            return self._candidate_tag
        else:
            if self.name.startswith('EL'):  # EPEL Hack.
                return '%s-testing-candidate' % self.dist_tag
            else:
                return '%s-updates-candidate' % self.dist_tag

    @property
    def pending_testing_tag(self):
        return self.testing_tag + '-pending'

    @property
    def pending_stable_tag(self):
        if self.locked:
            return '%s-updates-pending' % self.dist_tag
        return self.stable_tag + '-pending'

    @property
    def override_tag(self):
        return '%s-override' % self.dist_tag

    @property
    def mandatory_days_in_testing(self):
        name = self.name.lower().replace('-', '')
        status = config.get('%s.status' % name, None)
        if status:
            days = int(config.get(
                '%s.%s.mandatory_days_in_testing' % (name, status)))
            if days:
                return days
        days = int(config.get('%s.mandatory_days_in_testing' %
                              self.id_prefix.lower().replace('-', '_')))
        if not days:
            log.warn('No mandatory days in testing defined for %s' % self.name)
        return days

    @property
    def collection_name(self):
        """ Return the collection name of this release.  (eg: Fedora EPEL) """
        return ' '.join(self.long_name.split()[:-1])

    @classmethod
    def get_tags(cls):
        if cls._tag_cache:
            return cls._tag_cache
        data = {'candidate': [], 'testing': [], 'stable': [], 'override': [],
                'pending_testing': [], 'pending_stable': []}
        tags = {}  # tag -> release lookup
        for release in DBSession.query(cls).all():
            for key in data:
                tag = getattr(release, '%s_tag' % key)
                data[key].append(tag)
                tags[tag] = release.name
        cls._tag_cache = (data, tags)
        return cls._tag_cache
    _tag_cache = None

    @classmethod
    def from_tags(cls, tags, db):
        tag_types, tag_rels = cls.get_tags()
        for tag in tags:
            release = db.query(cls).filter_by(name=tag_rels[tag]).first()
            if release:
                return release


class TestCase(Base):
    """Test cases from the wiki"""
    __tablename__ = 'testcases'
    __get_by__ = ('name',)

    name = Column(UnicodeText, nullable=False)

    package_id = Column(Integer, ForeignKey('packages.id'))
    # package backref


class Package(Base):
    __tablename__ = 'packages'
    __get_by__ = ('name',)

    name = Column(Unicode(50), unique=True, nullable=False)

    builds = relationship('Build', backref='package')
    test_cases = relationship('TestCase', backref='package')
    committers = relationship('User', secondary=user_package_table,
                              backref='packages')

    def get_pkg_pushers(self, pkgdb, collectionName='Fedora', collectionVersion='devel'):
        """ Pull users who can commit and are watching a package

        Return two two-tuples of lists:
        * The first tuple is for usernames.  The second tuple is for groups.
        * The first list of the tuple is for committers.  The second is for
        watchers.

        An example::
        >>> people, groups = get_pkg_pushers('foo', 'Fedora', 'devel')
        >>> print people
        (['toshio', 'lmacken'], ['wtogami', 'toshio', 'lmacken'])
        >>> print groups
        (['cvsextras'], [])

        Note: The interface to the pkgdb could undergo the following changes:
        FAS2 related:
        * pkg['packageListings'][0]['owneruser'] =>
            pkg['packageListings'][0]['owner']
        * pkg['packageListings'][0]['people'][0..n]['user'] =>
            pkg['packageListings'][0]['people'][0..n]['userid']

        * We may want to create a 'push' acl specifically for bodhi instead of
        reusing 'commit'.
        * ['status']['translations'] may one day contain more than the 'C'
        translation.  The pkgdb will have to figure out how to deal with that
        if so.

        This may raise: fedora.client.AppError if there's an error talking to the
        PackageDB (for instance, no such package)
        """
        # Note if AppError is raised (for no pkgNamme or other server errors) we
        # do not catch the exception here.
        pkg = pkgdb.get_owners(self.name, collectionName, collectionVersion)

        # Owner is allowed to commit and gets notified of pushes
        # This will always be the 0th element as we'll retrieve at most one
        # value for any given Package-Collection-Version
        pNotify = [pkg.packageListings[0]['owner']]
        pAllowed = [pNotify[0]]

        # Find other people in the acl
        for person in pkg['packageListings'][0]['people']:
            if person['aclOrder']['watchcommits'] and \
            pkg['statusMap'][str(person['aclOrder']['watchcommits']['statuscode'])] == 'Approved':
                pNotify.append(person['username'])
            if person['aclOrder']['commit'] and \
            pkg['statusMap'][str(person['aclOrder']['commit']['statuscode'])] == 'Approved':
                pAllowed.append(person['username'])

        # Find groups that can push
        gNotify = []
        gAllowed = []
        for group in pkg['packageListings'][0]['groups']:
            if group['aclOrder']['watchcommits'] and \
            pkg['statusMap'][str(group['aclOrder']['watchcommits']['statuscode'])] == 'Approved':
                gNotify.append(group['groupname'])
            if group['aclOrder']['commit'] and \
            pkg['statusMap'][str(group['aclOrder']['commit']['statuscode'])] == 'Approved':
                gAllowed.append(group['groupname'])

        return ((pAllowed, pNotify), (gAllowed, gNotify))

    def fetch_test_cases(self, db):
        """ Get a list of test cases from the wiki """
        if not asbool(config.get('query_wiki_test_cases')):
            return

        from simplemediawiki import MediaWiki
        wiki = MediaWiki(config.get('wiki_url', 'https://fedoraproject.org/w/api.php'))
        cat_page = 'Category:Package %s test cases' % self.name
        limit = 10

        def list_categorymembers(wiki, cat_page, limit=10):
            # Build query arguments and call wiki
            query = dict(action='query', list='categorymembers', cmtitle=cat_page)
            response = wiki.call(query)
            members = [entry['title'] for entry in
                       response.get('query',{}).get('categorymembers',{})
                       if 'title' in entry]

            # Determine whether we need to recurse
            idx = 0
            while True:
                if idx >= len(members) or limit <= 0:
                    break
                # Recurse?
                if members[idx].startswith('Category:') and limit > 0:
                    members.extend(list_categorymembers(wiki, members[idx], limit-1))
                    members.remove(members[idx]) # remove Category from list
                else:
                    idx += 1

            return members

        for test in list_categorymembers(wiki, cat_page):
            case = db.query(TestCase).filter_by(name=test).first()
            if not case:
                case = TestCase(name=test, package=self)
                db.add(case)
                db.flush()

    def __str__(self):
        x = header(self.name)
        states = {'pending': [], 'testing': [], 'stable': []}
        if len(self.builds):
            for build in self.builds:
                if build.update and build.update.status.description in states:
                    states[build.update.status.description].append(
                        build.update)
        for state in states.keys():
            if len(states[state]):
                x += "\n %s Updates (%d)\n" % (state.title(),
                                               len(states[state]))
                for update in states[state]:
                    x += "    o %s\n" % update.get_title()
        del states
        return x


class Build(Base):
    __tablename__ = 'builds'
    __exclude_columns__ = ('id', 'package', 'package_id', 'release',
                           'release_id', 'update_id', 'update', 'inherited')
    __get_by__ = ('nvr',)

    nvr = Column(Unicode(100), unique=True, nullable=False)
    inherited = Column(Boolean, default=False)
    package_id = Column(Integer, ForeignKey('packages.id'))
    release_id = Column(Integer, ForeignKey('releases.id'))
    update_id = Column(Integer, ForeignKey('updates.id'))

    release = relationship('Release', backref='builds', lazy=False)

    def get_latest(self):
        koji_session = buildsys.get_session()

        # Grab a list of builds tagged with ``Release.stable_tag`` release
        # tags, and find the most recent update for this package, other than
        # this one.  If nothing is tagged for -updates, then grab the first
        # thing in ``Release.dist_tag``.  We aren't checking
        # ``Release.candidate_tag`` first, because there could potentially be
        # packages that never make their way over stable, so we don't want to
        # generate ChangeLogs against those.
        latest = None
        evr = build_evr(koji_session.getBuild(self.nvr))
        for tag in [self.release.stable_tag, self.release.dist_tag]:
            builds = koji_session.getLatestBuilds(
                    tag, package=self.package.name)

            # Find the first build that is older than us
            for build in builds:
                new_evr = build_evr(build)
                if rpm.labelCompare(evr, new_evr) < 0:
                    latest = build['nvr']
                    break
            if latest:
                break
        return latest

    def get_latest_srpm(self):
        latest = get_nvr(self.get_latest())
        latest_srpm = None
        if latest:
            srpm_path = os.path.join(config.get('build_dir'), latest[0],
                             latest[1], latest[2], 'src',
                             '%s.src.rpm' % '-'.join(latest))
            latest_srpm = srpm_path
            if os.path.isfile(srpm_path):
                log.debug("Latest build before %s: %s" % (self.nvr,
                                                          srpm_path))
            else:
                log.warning("Latest build %s not found" % srpm_path)
        return latest_srpm

    def get_url(self):
        """ Return a the url to details about this build """
        return '/' + self.nvr

    def get_rpm_header(self):
        """ Get the rpm header of this build """
        return rpm_fileheader(self.get_srpm_path())

    def get_changelog(self, timelimit=0):
        """
        Retrieve the RPM changelog of this package since it's last update
        """
        rpm_header = self.get_rpm_header()
        descrip = rpm_header[rpm.RPMTAG_CHANGELOGTEXT]
        if not descrip:
            return ""

        who = rpm_header[rpm.RPMTAG_CHANGELOGNAME]
        when = rpm_header[rpm.RPMTAG_CHANGELOGTIME]

        num = len(descrip)
        if num == 1:
            when = [when]

        str = ""
        i = 0
        while (i < num) and (when[i] > timelimit):
            str += '* %s %s\n%s\n' % (time.strftime("%a %b %e %Y",
                                      time.localtime(when[i])), who[i],
                                      descrip[i])
            i += 1
        del rpm_header
        return str

    def get_srpm_path(self):
        """ Return the path to the SRPM for this update """
        src_path = self.get_source_path()
        path = src_path.split('/')
        srpm = os.path.join(
            src_path, "src", "%s.src.rpm" % ('-'.join(path[-3:])))
        if not os.path.isfile(srpm):
            log.debug("Cannot find SRPM: %s" % srpm)
            raise RPMNotFound
        return srpm

    def get_source_path(self):
        """ Return the path of this built update """
        return os.path.join(config.get('build_dir'), *get_nvr(self.nvr))

    def get_tags(self):
        koji = buildsys.get_session()
        return [tag['name'] for tag in koji.listTags(self.nvr)]

    def untag(self, koji):
        """Remove all known tags from this build"""
        tag_types, tag_rels = Release.get_tags()
        for tag in self.get_tags():
            if tag in tag_rels:
                log.info('Removing %s tag from %s' % (tag, self.nvr))
                koji.untagBuild(tag, self.nvr)


class Update(Base):
    __tablename__ = 'updates'
    __exclude_columns__ = ('id', 'user_id', 'release_id')
    __get_by__ = ('title', 'alias')

    title = Column(UnicodeText, default=None)

    # TODO: more flexible karma schema
    karma = Column(Integer, default=0)
    stable_karma = Column(Integer, nullable=True)
    unstable_karma = Column(Integer, nullable=True)

    notes = Column(UnicodeText, nullable=False)  # Mandatory notes

    # Enumerated types
    type = Column(UpdateType.db_type(), nullable=False)
    status = Column(UpdateStatus.db_type(),
                    default=UpdateStatus.pending,
                    nullable=False)
    request = Column(UpdateRequest.db_type())
    severity = Column(UpdateSeverity.db_type(), default=UpdateSeverity.unspecified)
    suggest = Column(UpdateSuggestion.db_type(), default=UpdateSuggestion.unspecified)

    # Flags
    locked = Column(Boolean, default=False)
    pushed = Column(Boolean, default=False)
    critpath = Column(Boolean, default=False)

    # Bug settings
    close_bugs = Column(Boolean, default=True)

    # Team approvals
    security_approved = Column(Boolean, default=False)
    releng_approved = Column(Boolean, default=False)
    qa_approved = Column(Boolean, default=False)

    # Timestamps
    date_submitted = Column(DateTime, default=datetime.utcnow)
    date_modified = Column(DateTime)
    date_approved = Column(DateTime)
    date_pushed = Column(DateTime)
    security_approval_date = Column(DateTime)
    qa_approval_date = Column(DateTime)
    releng_approval_date = Column(DateTime)

    # eg: FEDORA-EPEL-2009-12345
    alias = Column(Unicode(32), default=None, unique=True)

    # deprecated: our legacy update ID
    old_updateid = Column(Unicode(32), default=None)

    # One-to-one relationships
    release_id = Column(Integer, ForeignKey('releases.id'))
    release = relationship('Release', lazy='joined')

    # One-to-many relationships
    comments = relationship('Comment', backref='update', lazy='joined',
                            order_by='Comment.timestamp')
    builds = relationship('Build', backref='update', lazy='joined')

    # Many-to-many relationships
    bugs = relationship('Bug', secondary=update_bug_table,
                        backref='updates', lazy='joined')
    cves = relationship('CVE', secondary=update_cve_table,
                        backref='updates', lazy='joined')

    # We may or may not need this, since we can determine the releases from the
    # builds
    #releases = relationship('Release', secondary=update_release_table,
    #                        backref='updates', lazy=False)

    user_id = Column(Integer, ForeignKey('users.id'))

    @classmethod
    def new(cls, request, data):
        """ Create a new update """
        db = request.db
        buildinfo = request.buildinfo
        user = request.user
        data['user'] = user
        data['title'] = ' '.join(data['builds'])

        releases = set()
        builds = []

        # Create the Package and Build entities
        for build in data['builds']:
            name, version, release = buildinfo[build]['nvr']
            package = db.query(Package).filter_by(name=name).first()
            if not package:
                package = Package(name=name)
                db.add(package)
                db.flush()

            # Fetch test cases from the wiki
            package.fetch_test_cases(db)

            build = Build(nvr=build, package=package)
            builds.append(build)
            releases.add(buildinfo[build.nvr]['release'])

        data['builds'] = builds

        assert len(releases) == 1, "TODO: multi-release updates"
        data['release'] = list(releases)[0]

        critical = False
        critpath_pkgs = get_critpath_pkgs(data['release'].name.lower())
        if critpath_pkgs:
            for build in data['builds']:
                if build.package.name in critpath_pkgs:
                    critical = True
                    break

        data['critpath'] = critical

        # Create the Bug entities
        bugs = []
        for bug_num in data['bugs']:
            bug = db.query(Bug).filter_by(bug_id=bug_num).first()
            if not bug:
                bug = Bug(bug_id=bug_num)
                bug.fetch_details()
                db.add(bug)
                if bug.security:
                    data['type'] = UpdateType.security
            bugs.append(bug)
            bugtracker.comment(bug_num, config['initial_bug_msg'] % (
                       data['title'], data['release'].long_name, bug.url))
        data['bugs'] = bugs

        if not data['autokarma']:
            del(data['stable_karma'])
            del(data['unstable_karma'])
        del(data['autokarma'])

        del(data['edited'])

        # Create the update
        up = Update(**data)
        db.add(up)
        db.flush()

        return up

    @classmethod
    def edit(cls, request, data):
        db = request.db
        buildinfo = request.buildinfo
        user = request.user
        koji = request.koji
        up = db.query(Update).filter_by(title=data['edited']).first()
        del(data['edited'])

        edited_builds = [build.nvr for build in up.builds]

        # Determine which builds have been added
        new_builds = []
        for build in data['builds']:
            if build not in edited_builds:
                new_builds.append(build)
                name, version, release = buildinfo[build]['nvr']
                package = db.query(Package).filter_by(name=name).first()
                if not package:
                    package = Package(name=name)
                    db.add(package)
                b = Build(nvr=build, package=package)
                b.release = up.release
                koji.tagBuild(up.release.pending_testing_tag, build)
                up.builds.append(b)

        # Determine which builds have been removed
        removed_builds = []
        for build in edited_builds:
            if build not in data['builds']:
                removed_builds.append(build)
                b = None
                for b in up.builds:
                    if b.nvr == build:
                        break
                b.untag(koji=request.koji)
                up.builds.remove(b)
                db.delete(b)

        critical = False
        critpath_pkgs = get_critpath_pkgs(up.release.name.lower())
        if critpath_pkgs:
            for build in up.builds:
                if build.package.name in critpath_pkgs:
                    critical = True
                    break

        data['critpath'] = critical

        del(data['builds'])

        # Comment on the update with details of added/removed builds
        comment = '%s edited this update. ' % user.name
        if new_builds:
            comment += 'New build(s): %s. ' % ', '.join(new_builds)
        if removed_builds:
            comment += 'Removed build(s): %s.' % ', '.join(removed_builds)
        up.comment(comment, karma=0, author=u'bodhi')

        data['title'] = ' '.join(sorted([b.nvr for b in up.builds]))

        # Updates with new or removed builds always go back to testing
        data['request'] = UpdateRequest.testing

        new_bugs = up.update_bugs(data['bugs'])
        del(data['bugs'])
        for bug in new_bugs:
            bug.add_comment(up, config['initial_bug_msg'] % (
                data['title'], data['release'].long_name, up.url))

        for key, value in data.items():
            setattr(up, key, value)

        up.date_modified = datetime.utcnow()

        return up

    def obsolete_older_updates(self, request):
        """Obsolete any older pending/testing updates.

        If a build is associated with multiple updates, make sure that
        all updates are safe to obsolete, or else just skip it.
        """
        db = request.db
        buildinfo = request.buildinfo
        for build in self.builds:
            for oldBuild in db.query(Build).join(Update.builds).filter(
                and_(Build.nvr != build.nvr,
                     Update.request == None,
                     Update.release == self.release,
                     or_(Update.status == UpdateStatus.testing,
                         Update.status == UpdateStatus.pending))
            ).all():
                obsoletable = False
                nvr = buildinfo[build.nvr]['nvr']
                if rpm.labelCompare(get_nvr(oldBuild.nvr), nvr) < 0:
                    log.debug("%s is newer than %s" % (nvr, oldBuild.nvr))
                    obsoletable = True

                # Ensure the same number of builds are present
                if len(oldBuild.update.builds) != len(self.builds):
                    obsoletable = False
                    break

                # Ensure that all of the packages in the old update are
                # present in the new one.
                pkgs = [b.package.name for b in self.builds]
                for _build in oldBuild.update.builds:
                    if _build.package.name not in pkgs:
                        obsoletable = False
                        break

                if obsoletable:
                    log.info('%s is obsoletable' % oldBuild.nvr)

                    # Have the newer update inherit the older updates bugs
                    oldbugs = [bug.bug_id for bug in oldBuild.update.bugs]
                    bugs = [bug.bug_id for bug in self.bugs]
                    self.update_bugs(bugs + oldbugs)

                    # Also inherit the older updates notes as well
                    self.notes += '\n' + oldBuild.update.notes
                    oldBuild.update.obsolete(newer=build.nvr)
                    self.comment('This update has obsoleted %s, and has '
                                 'inherited its bugs and notes.' % oldBuild.nvr,
                                 author='bodhi')

    def get_title(self, delim=' '):
        nvrs = [build.nvr for build in self.builds]
        return delim.join(sorted(nvrs))

    def get_bugstring(self, show_titles=False):
        """Return a space-delimited string of bug numbers for this update """
        val = u''
        if show_titles:
            i = 0
            for bug in self.bugs:
                bugstr = u'%s%s - %s\n' % (i and ' ' * 11 + ': ' or '',
                                          bug.bug_id, bug.title)
                val += u'\n'.join(wrap(
                    bugstr, width=67,
                    subsequent_indent=' ' * 11 + ': ')) + '\n'
                i += 1
            val = val[:-1]
        else:
            val = u' '.join([str(bug.bug_id) for bug in self.bugs])
        return val

    def get_cvestring(self):
        """ Return a space-delimited string of CVE ids for this update """
        return u' '.join([cve.cve_id for cve in self.cves])

    def assign_alias(self):
        """Assign an update ID to this update.

        This function finds the next number in the sequence of pushed updates
        for this release, increments it and prefixes it with the id_prefix of
        the release and the year (ie FEDORA-2007-0001).
        """
        if self.alias not in (None, u'None'):
            log.debug("Keeping current update id %s" % self.alias)
            return

        releases = DBSession.query(Release) \
                            .filter_by(id_prefix=self.release.id_prefix) \
                            .all()

        update = DBSession.query(Update) \
                          .filter(
                              and_(Update.date_pushed != None,
                                   Update.alias != None,
                                   or_(*[Update.release == release
                                         for release in releases]))) \
                          .order_by(Update.date_pushed.desc()) \
                          .group_by(Update.date_pushed) \
                          .limit(1) \
                          .first()

        if not update:
            id = 1
        else:
            split = update.alias.split('-')
            year, id = split[-2:]
            prefix = '-'.join(split[:-2])
            if int(year) != time.localtime()[0]:  # new year
                id = 0
            id = int(id) + 1

        self.alias = u'%s-%s-%0.4d' % (self.release.id_prefix,
                                       time.localtime()[0], id)
        log.debug("Setting alias for %s to %s" % (self.title, self.alias))

        # FIXME: don't do this here:
        self.date_pushed = datetime.utcnow()

    def set_request(self, action, request, pathcheck=True):
        """ Attempt to request an action for this update """
        log.debug('Attempting to set request %s' % action)
        notes = []
        if isinstance(action, basestring):
            action = UpdateRequest.from_string(action)
        if action is self.status:
            log.info("%s already %s" % (self.title, action.description))
            return
        if action is self.request:
            log.debug("%s has already been submitted to %s" % (self.title,
                                                               self.request.description))
            return
        if action is UpdateRequest.unpush:
            self.unpush()
            self.comment(u'This update has been unpushed',
                         author=request.user.name)
            flash_log("%s has been unpushed" % self.title)
            return
        elif action is UpdateRequest.obsolete:
            self.obsolete()
            flash_log("%s has been obsoleted" % self.title)
            return

        elif action is UpdateRequest.stable and pathcheck:
            # Make sure we don't break update paths by trying to push out
            # an update that is older than than the latest.
            koji = request.koji
            for build in self.builds:
                mybuild = koji.getBuild(build.nvr)
                kojiBuilds = koji.listTagged(self.release.stable_tag,
                                             package=build.package.name,
                                             latest=True)
                for oldBuild in kojiBuilds:
                    if rpm.labelCompare(build_evr(mybuild),
                                        build_evr(oldBuild)) < 0:
                        request.errors.add('body', 'build',
                                           'Broken update path: %s is already '\
                                           'released, and is newer than %s' %
                                           (oldBuild['nvr'], mybuild['nvr']))
                        return

        # Disable pushing critical path updates for pending releases directly to stable
        if action is UpdateRequest.stable and self.critpath:
            if config.get('critpath.num_admin_approvals') is not None:
                if not self.critpath_approved:
                    notes.append('This critical path update has not '
                                 'yet been approved for pushing to the stable '
                                 'repository.  It must first reach a karma '
                                 'of %s, consisting of %s positive karma from '
                                 'proventesters, along with %d additional '
                                 'karma from the community. Or, it must '
                                 'spend %s days in testing without any '
                                 'negative feedback'
                                 % (config.get('critpath.min_karma'),
                                    config.get('critpath.num_admin_approvals'),
                                    int(config.get('critpath.min_karma')) -
                                            int(config.get('critpath.num_admin_approvals')),
                                    config.get('critpath.stable_after_days_without_negative_karma')))
                    if self.status is UpdateStatus.testing:
                        self.request = None
                        request.error.add('body', 'update', '. '.join(notes))
                        return
                    else:
                        log.info('Forcing critical path update into testing')
                        action = UpdateRequest.testing

        # Ensure this update meets the minimum testing requirements
        flash_notes = ''
        if action is UpdateRequest.stable and not self.critpath:
            # Check if we've met the karma requirements
            if (self.stable_karma not in (None, 0) and self.karma >=
                self.stable_karma) or self.critpath_approved:
                log.debug('%s meets stable karma requirements' % self.title)
                pass
            else:
                # If we haven't met the stable karma requirements, check if it
                # has met the mandatory time-in-testing requirements
                if self.release.mandatory_days_in_testing:
                    if not self.met_testing_requirements and \
                       not self.meets_testing_requirements:
                        flash_notes = config.get('not_yet_tested_msg')
                        if self.status is UpdateStatus.testing:
                            self.request = None
                            request.errors.add('body', 'update', flash_notes)
                            return
                        elif self.request is UpdateRequest.testing:
                            request.errors.add('body', 'update', flash_notes)
                            return
                        else:
                            action = UpdateRequest.testing

        # Add the appropriate 'pending' koji tag to this update, so tools like
        # AutoQA can mash repositories of them for testing.
        if action is UpdateRequest.testing:
            self.add_tag(self.release.pending_testing_tag)
        elif action is UpdateRequest.stable:
            self.add_tag(self.release.pending_stable_tag)

        # If an obsolete/unpushed build is being re-submitted, return
        # it to the pending state, and make sure it's tagged as a candidate
        if self.status in (UpdateStatus.obsolete, UpdateStatus.unpushed):
            self.status = UpdateStatus.pending
            if not self.release.candidate_tag in self.get_tags():
                self.add_tag(self.release.candidate_tag)

        self.request = action
        self.pushed = False

        notes = notes and '. '.join(notes) or ''
        flash_notes = flash_notes and '. %s' % flash_notes
        flash_log("%s has been submitted for %s. %s%s" % (self.title,
            action.description, notes, flash_notes))
        self.comment('This update has been submitted for %s by %s. %s' % (
            action.description, request.user.name, notes), author='bodhi')

        # FIXME: track date pushed to testing & stable in different fields
        self.date_pushed = None

    def add_tag(self, tag):
        """ Add a koji tag to all builds in this update """
        log.debug('Adding tag %s to %s' % (tag, self.title))
        koji = buildsys.get_session()
        koji.multicall = True
        for build in self.builds:
            koji.tagBuild(tag, build.nvr, force=True)
        return koji.multiCall()

    def remove_tag(self, tag, koji=None):
        """ Remove a koji tag from all builds in this update """
        log.debug('Removing tag %s from %s' % (tag, self.title))
        return_multicall = not koji
        if not koji:
            koji = buildsys.get_session()
            koji.multicall = True
        for build in self.builds:
            koji.untagBuild(tag, build.nvr, force=True)
        if return_multicall:
            return koji.multiCall()

    def request_complete(self):
        """
        Perform post-request actions.
        """
        if self.request is UpdateRequest.testing:
            self.status = UpdateStatus.testing
        elif self.request is UpdateRequest.stable:
            self.status = UpdateStatus.stable
        self.request = None
        self.date_pushed = datetime.utcnow()
        self.assign_alias()

    def modify_bugs(self):
        """
        Comment on and close this updates bugs as necessary
        """
        if self.status is UpdateStatus.testing:
            for bug in self.bugs:
                bug.testing(self)
        elif self.status is UpdateStatus.stable:
            for bug in self.bugs:
                bug.add_comment(self)

            if self.close_bugs:
                if self.type is UpdateType.security:
                    # Close all tracking bugs first
                    for bug in self.bugs:
                        if not bug.parent:
                            log.debug("Closing tracker bug %d" % bug.bug_id)
                            bug.close_bug(self)

                    # Now, close our parents bugs as long as nothing else
                    # depends on them, and they are not in a NEW state
                    for bug in self.bugs:
                        if bug.parent:
                            parent = bugtracker.getbug(bug.bug_id)
                            if parent.bug_status == "NEW":
                                log.debug("Parent bug %d is still NEW; not "
                                          "closing.." % bug.bug_id)
                                continue
                            depsclosed = True
                            for dep in parent.dependson:
                                try:
                                    tracker = bugtracker.getbug(dep)
                                except xmlrpclib.Fault, f:
                                    log.error("Can't access bug: %s" % str(f))
                                    depsclosed = False
                                    break
                                if tracker.bug_status != "CLOSED":
                                    log.debug("Tracker %d not yet closed" %
                                              bug.bug_id)
                                    depsclosed = False
                                    break
                            if depsclosed:
                                log.debug("Closing parent bug %d" % bug.bug_id)
                                bug.close_bug(self)
                else:
                    for bug in self.bugs:
                        bug.close_bug(self)

    def status_comment(self):
        """
        Add a comment to this update about a change in status
        """
        if self.status is UpdateStatus.stable:
            self.comment(u'This update has been pushed to stable',
                         author=u'bodhi')
        elif self.status is UpdateStatus.testing:
            self.comment(u'This update has been pushed to testing',
                         author=u'bodhi')
        elif self.status is UpdateStatus.obsolete:
            self.comment(u'This update has been obsoleted', author=u'bodhi')

    def send_update_notice(self):
        log.debug("Sending update notice for %s" % self.title)
        mailinglist = None
        sender = config.get('bodhi_email')
        if not sender:
            log.error("bodhi_email not defined in configuration!  Unable " +
                      "to send update notice")
            return
        if self.status is UpdateStatus.stable:
            mailinglist = config.get('%s_announce_list' %
                              self.release.id_prefix.lower())
        elif self.status is UpdateStatus.testing:
            mailinglist = config.get('%s_test_announce_list' %
                              self.release.id_prefix.lower())
        if mailinglist:
            for subject, body in mail.get_template(self):
                message = turbomail.Message(sender, mailinglist, subject)
                message.plain = body
                try:
                    log.debug("Sending mail: %s" % subject)
                    message.send()
                except turbomail.MailNotEnabledException:
                    log.warning("mail.on is not True!")
        else:
            log.error("Cannot find mailing list address for update notice")

    def get_url(self):
        """ Return the relative URL to this update """
        path = ['/']
        if self.alias:
            path.append(self.release.name)
            path.append(self.alias)
        else:
            path.append(self.get_title())
        return os.path.join(*path)

    def __str__(self):
        """
        Return a string representation of this update.
        """
        val = u"%s\n%s\n%s\n" % ('=' * 80, u'\n'.join(wrap(
            self.title.replace(',', ', '), width=80, initial_indent=' ' * 5,
            subsequent_indent=' ' * 5)), '=' * 80)
        if self.alias:
            val += u"  Update ID: %s\n" % self.alias
        val += u"""    Release: %s
     Status: %s
       Type: %s
      Karma: %d""" % (self.release.long_name, self.status.description,
                      self.type.description, self.karma)
        if self.critpath:
            val += u"\n   Critpath: %s" % self.critpath
        if self.request != None:
            val += u"\n    Request: %s" % self.request.description
        if len(self.bugs):
            bugs = self.get_bugstring(show_titles=True)
            val += u"\n       Bugs: %s" % bugs
        if len(self.cves):
            val += u"\n       CVEs: %s" % self.get_cvestring()
        if self.notes:
            notes = wrap(
                self.notes, width=67, subsequent_indent=' ' * 11 + ': ')
            val += u"\n      Notes: %s" % '\n'.join(notes)
        val += u"""
  Submitter: %s
  Submitted: %s\n""" % (self.user.name, self.date_submitted)
        if len(self.comments):
            val += u"   Comments: "
            comments = []
            for comment in self.comments:
                if comment.anonymous:
                    anonymous = " (unauthenticated)"
                else:
                    anonymous = ""
                comments.append(u"%s%s%s - %s (karma %s)" % (' ' * 13,
                                comment.user.name, anonymous, comment.timestamp,
                                comment.karma))
                if comment.text:
                    text = wrap(comment.text, initial_indent=' ' * 13,
                                subsequent_indent=' ' * 13, width=67)
                    comments.append(u'\n'.join(text))
            val += u'\n'.join(comments).lstrip() + u'\n'
        val += u"\n  %s\n" % (config.get('base_address') + self.get_url())
        return val

    def get_build_tag(self):
        """
        Get the tag that this build is currently tagged with.
        TODO: we should probably get this stuff from koji instead of guessing
        """
        tag = '%s-updates' % self.release.dist_tag
        if self.status in (UpdateStatus.pending, UpdateStatus.obsolete):
            tag += '-candidate'
        elif self.status is UpdateStatus.testing:
            tag += '-testing'
        return tag

    def update_bugs(self, bugs):
        """
        Create any new bugs, and remove any missing ones. Destroy removed bugs
        that are no longer referenced anymore.

        :returns: a list of new Bug instances.
        """
        fetchdetails = True
        new = []
        session = DBSession()
        if not config.get('bodhi_email'):
            log.warning("No bodhi_email defined; not fetching bug details")
            fetchdetails = False
        to_remove = []
        for bug in self.bugs:
            if bug.bug_id not in bugs:
                to_remove.append(bug)
        if to_remove:
            for bug in to_remove:
                self.bugs.remove(bug)
                if len(bug.updates) == 0:
                    log.debug("Destroying stray Bugzilla #%d" % bug.bug_id)
                    session.delete(bug)
            session.flush()
        for bug_id in bugs:
            bug = session.query(Bug).filter_by(bug_id=bug_id).first()
            if not bug:
                if fetchdetails:
                    newbug = bugtracker.getbug(bug_id)
                    bug = Bug(bug_id=newbug.bug_id)
                    bug.fetch_details(newbug)
                    bug.modified()
                else:
                    bug = Bug(bug_id=int(bug_id))
                session.add(bug)
            if bug not in self.bugs:
                self.bugs.append(bug)
                new.append(bug)
            if bug.security and self.type != UpdateType.security:
                self.type = UpdateType.security
        session.flush()
        return new

    def update_cves(self, cves):
        """
        Create any new CVES, and remove any missing ones.  Destroy removed CVES
        that are no longer referenced anymore.
        """
        session = DBSession()
        for cve in self.cves:
            if cve.cve_id not in cves and len(cve.updates) == 0:
                log.debug("Destroying stray CVE #%s" % cve.cve_id)
                session.delete(cve)
        for cve_id in cves:
            cve = CVE.query.filter_by(cve_id=cve_id).one()
            if cve not in self.cves:
                self.cves.append(cve)
                log.debug("Creating new CVE: %s" % cve_id)
                cve = CVE(cve_id=cve_id)
                session.save(cve)
                self.cves.append(cve)
        session.flush()

    def get_pushed_age(self):
        return get_age(self.date_pushed)

    def get_submitted_age(self):
        return get_age(self.date_submitted)

    def get_pushed_color(self):
        age = get_age_in_days(self.date_pushed)
        if age == 0 or self.karma < 0:
            color = '#ff0000'  # red
        elif age < 4:
            color = '#ff6600'  # orange
        elif age < 7:
            color = '#ffff00'  # yellow
        else:
            color = '#00ff00'  # green
        return color

    def comment(self, text, karma=0, author=None, anonymous=False):
        """ Add a comment to this update, adjusting the karma appropriately.

        Each user has the ability to comment as much as they want, but only
        their last karma adjustment will be counted.  If the karma reaches
        the 'stable_karma' value, then request that this update be marked
        as stable.  If it reaches the 'unstable_karma', it is unpushed.
        """
        if not author:
            raise ValueError('You must provide a comment author')
        if not anonymous and karma != 0 and \
           not filter(lambda c: c.user.name == author and c.karma == karma,
                      self.comments):
            mycomments = [
                c.karma for c in self.comments if c.user.name == author]
            if karma == 1 and -1 in mycomments:
                self.karma += 2
            elif karma == -1 and 1 in mycomments:
                self.karma -= 2
            else:
                self.karma += karma
            log.info("Updated %s karma to %d" % (self.title, self.karma))
            if self.stable_karma != 0 and self.stable_karma == self.karma:
                log.info("Automatically marking %s as stable" % self.title)
                self.request = UpdateRequest.stable
                self.date_pushed = None
                mail.send(self.get_maintainers(), 'stablekarma', self)
                mail.send_admin('stablekarma', self)
            if self.status is UpdateStatus.testing \
                    and self.unstable_karma != 0 \
                    and self.karma == self.unstable_karma:
                log.info("Automatically unpushing %s" % self.title)
                self.obsolete()
                mail.send(self.get_maintainers(), 'unstable', self)

        session = DBSession()
        comment = Comment(text=text, karma=karma, anonymous=anonymous)
        session.add(comment)
        session.flush()

        if anonymous:
            author = u'anonymous'
        try:
            user = session.query(User).filter_by(name=author).one()
        except NoResultFound:
            user = User(name=author)
            session.add(user)
            session.flush()

        user.comments.append(comment)
        self.comments.append(comment)
        session.flush()

        # Send a notification to everyone that has commented on this update
        people = set()
        for person in self.get_maintainers():
            people.add(person)
        for comment in self.comments:
            if comment.anonymous or comment.user.name == u'bodhi':
                continue
            people.add(comment.user.name)
        mail.send(people, 'comment', self)
        return comment

    def unpush(self):
        """ Move this update back to its dist-fX-updates-candidate tag """
        log.debug("Unpushing %s" % self.title)
        koji = buildsys.get_session()
        newtag = '%s-updates-candidate' % self.release.dist_tag
        curtag = self.get_build_tag()
        if curtag.endswith('-updates-candidate'):
            log.debug("%s already unpushed" % self.title)
            return
        for build in self.builds:
            if build.inherited:
                log.debug("Removing %s tag from %s" % (curtag, build.nvr))
                koji.untagBuild(curtag, build.nvr, force=True)
            else:
                log.debug("Moving %s from %s to %s" % (
                    build.nvr, curtag, newtag))
                koji.moveBuild(curtag, newtag, build.nvr, force=True)
        self.pushed = False
        self.status = UpdateStatus.unpushed
        mail.send_admin('unpushed', self)

    def untag(self):
        """ Untag all of the builds in this update """
        log.info("Untagging %s" % self.title)
        koji = buildsys.get_session()
        tag = self.get_build_tag()
        for build in self.builds:
            koji.untagBuild(tag, build.nvr, force=True)
        self.pushed = False

    def obsolete(self, newer=None):
        """
        Obsolete this update. Even though unpushing/obsoletion is an "instant"
        action, changes in the repository will not propagate until the next
        mash takes place.
        """
        log.debug("Obsoleting %s" % self.title)
        self.untag()
        self.status = UpdateStatus.obsolete
        self.request = None
        if newer:
            self.comment(u"This update has been obsoleted by %s" % newer,
                         author=u'bodhi')
        else:
            self.comment(u"This update has been obsoleted", author=u'bodhi')

    def get_maintainers(self):
        """
        Return a list of people that have commit access to all of the packages
        that are contained within this update.
        """
        people = set()
        for build in self.builds:
            if build.package.committers:
                for committer in build.package.committers:
                    people.add(committer.name)
        return list(people)

    @property
    def critpath_approved(self):
        """ Return whether or not this critpath update has been approved """
        # https://fedorahosted.org/bodhi/ticket/642
        if self.meets_testing_requirements:
            return True
        release_name = self.release.name.lower().replace('-', '')
        status = config.get('%s.status' % release_name, None)
        if status:
            num_admin_approvals = config.get('%s.%s.critpath.num_admin_approvals' % (
                    release_name, status), None)
            min_karma = config.get('%s.%s.critpath.min_karma' % (
                    release_name, status), None)
            if num_admin_approvals is not None and min_karma:
                return self.num_admin_approvals >= num_admin_approvals and \
                        self.karma >= min_karma
        return self.num_admin_approvals >= config.get(
                'critpath.num_admin_approvals', 2) and \
               self.karma >= config.get('critpath.min_karma', 2)

    @property
    def meets_testing_requirements(self):
        """
        Return whether or not this update meets the testing requirements
        for this specific release.

        If this release does not have a mandatory testing requirement, then
        simply return True.
        """
        if self.critpath:
            # Ensure there is no negative karma. We're looking at the sum of
            # each users karma for this update, which takes into account
            # changed votes.
            feedback = defaultdict(int)
            for comment in self.comments:
                if not comment.anonymous:
                    feedback[comment.user.name] += comment.karma
            for karma in feedback.values():
                if karma < 0:
                    return False
            num_days = config.get('critpath.stable_after_days_without_negative_karma')
            return self.days_in_testing >= num_days
        num_days = self.release.mandatory_days_in_testing
        if not num_days:
            return True
        return self.days_in_testing >= num_days

    @property
    def met_testing_requirements(self):
        """
        Return whether or not this update has already met the testing
        requirements.

        If this release does not have a mandatory testing requirement, then
        simply return True.
        """
        min_num_days = self.release.mandatory_days_in_testing
        num_days = self.days_in_testing
        if min_num_days:
            if num_days < min_num_days:
                return False
        else:
            return True
        for comment in self.comments:
            if comment.user.name == 'bodhi' and \
               comment.text.startswith('This update has reached') and \
               comment.text.endswith('days in testing and can be pushed to'
                                     ' stable now if the maintainer wishes'):
                return True
        return False

    @property
    def days_in_testing(self):
        """ Return the number of days that this update has been in testing """
        timestamp = None
        for comment in self.comments[::-1]:
            if comment.text == 'This update has been pushed to testing' and \
                    comment.user.name == 'bodhi':
                timestamp = comment.timestamp
                if self.status == UpdateStatus.testing:
                    return (datetime.utcnow() - timestamp).days
                else:
                    break
        if not timestamp:
            return
        for comment in self.comments:
            if comment.text == 'This update has been pushed to stable' and \
                    comment.user.name == 'bodhi':
                return (comment.timestamp - timestamp).days
        return (datetime.utcnow() - timestamp).days

    @property
    def num_admin_approvals(self):
        """ Return the number of Releng/QA approvals of this update """
        approvals = 0
        for comment in self.comments:
            if comment.karma != 1:
                continue
            admin_groups = config.get('admin_groups').split()
            for group in comment.user.groups:
                if group.name in admin_groups:
                    approvals += 1
                    break
        return approvals

    @property
    def test_cases(self):
        tests = set()
        for build in self.builds:
            for test in build.package.test_cases:
                tests.add(test.name)
        return list(tests)


class Comment(Base):
    __tablename__ = 'comments'

    karma = Column(Integer, default=0)
    text = Column(UnicodeText)
    anonymous = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    update_id = Column(Integer, ForeignKey('updates.id'))
    user_id = Column(Integer, ForeignKey('users.id'))

    def __str__(self):
        karma = '0'
        if self.karma != 0:
            karma = '%+d' % (self.karma,)
        if self.anonymous:
            anonymous = " (unauthenticated)"
        else:
            anonymous = ""
        return "%s%s - %s (karma: %s)\n%s" % (self.user.name, anonymous,
                                              self.timestamp, karma, self.text)


class CVE(Base):
    __tablename__ = 'cves'
    __exclude_columns__ = ('id', 'updates', 'bugs')
    __get_by__ = ('cve_id',)

    cve_id = Column(Unicode(13), unique=True, nullable=False)

    @property
    def url(self):
        return "http://www.cve.mitre.org/cgi-bin/cvename.cgi?name=%s" % \
                self.cve_id


class Bug(Base):
    __tablename__ = 'bugs'
    __exclude_columns__ = ('id', 'cves', 'updates')
    __get_by__ = ('bug_id',)

    # Bug number. If None, assume ``url`` points to an external bug tracker
    bug_id = Column(Integer, unique=True)

    # The title of the bug
    title = Column(Unicode(255))

    # If we're dealing with a security bug
    security = Column(Boolean, default=False)

    # Bug URL.  If None, then assume it's in Red Hat Bugzilla
    url = Column('url', UnicodeText)

    # If this bug is a parent tracker bug for release-specific bugs
    parent = Column(Boolean, default=False)

    # List of Mitre CVE's associated with this bug
    cves = relationship(CVE, secondary=bug_cve_table, backref='bugs')

    @property
    def url(self):
        return config['buglink'] % self.bug_id

    def fetch_details(self, bug=None):
        bugtracker.update_details(bug, self)

    def default_message(self, update):
        message = config['stable_bug_msg'] % (
            update.get_title(delim=', '), "%s %s" % (
                update.release.long_name, update.status.description))
        if update.status is UpdateStatus.testing:
            message += config['testing_bug_msg'] % (
                ' '.join([build.package.name for build in update.builds]),
                config.get('base_address') + update.get_url())
        return message

    def add_comment(self, update, comment=None):
        if not comment:
            comment = self.default_message(update)
        log.debug("Adding comment to Bug #%d: %s" % (self.bug_id, comment))
        bugtracker.comment(self.bug_id, comment)

    def testing(self, update):
        """
        Change the status of this bug to ON_QA, and comment on the bug with
        some details on how to test and provide feedback for this update.
        """
        comment = self.default_message(update)
        bugtracker.on_qa(self.bug_id, comment)

    def close_bug(self, update):
        ver = '-'.join(get_nvr(update.builds[0].nvr)[-2:])
        bugtracker.close(self.bug_id, fixedin=ver)

    def modified(self):
        """ Change the status of this bug to MODIFIED """
        bugtracker.modified(self.bug_id)


user_group_table = Table('user_group_table', Base.metadata,
                         Column('user_id', Integer, ForeignKey('users.id')),
                         Column('group_id', Integer, ForeignKey('groups.id')))


class User(Base):
    __tablename__ = 'users'
    __exclude_columns__ = ('id', 'comments', 'updates', 'groups', 'packages')
    __get_by__ = ('name',)

    name = Column(Unicode(64), unique=True, nullable=False)

    # One-to-many relationships
    comments = relationship(Comment, backref=backref('user', lazy='joined'))
    updates = relationship(Update, backref=backref('user', lazy='joined'))

    # Many-to-many relationships
    groups = relationship("Group", secondary=user_group_table, backref='users')


class Group(Base):
    __tablename__ = 'groups'
    __get_by__ = ('name',)

    name = Column(Unicode(64), unique=True, nullable=False)

    # users backref


#class Stack(Base):
#    """
#    A Stack in bodhi represents a group of packages that are commonly pushed
#    together as a group.
#    """
#    # name
#    # packages =  Many to many?
#    # updates
