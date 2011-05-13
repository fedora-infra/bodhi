import os
import time
import logging
import bugzilla
import xmlrpclib
import transaction

from textwrap import wrap
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy import Unicode, UnicodeText, PickleType, Integer, Boolean
from sqlalchemy import DateTime
from sqlalchemy import Table, Column, ForeignKey
from sqlalchemy import and_, or_
from sqlalchemy.orm import scoped_session, sessionmaker, relation, relationship
from sqlalchemy.ext.declarative import declarative_base, synonym_for
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound

from bodhi import buildsys, mail
from bodhi.util import header, build_evr, authorized_user, rpm_fileheader, get_nvr, flash_log, get_age
from bodhi.util import get_age_in_days # TODO: move these methods into the model
from bodhi.models.enum import DeclEnum
from bodhi.exceptions import InvalidRequest, RPMNotFound

log = logging.getLogger(__name__)

config = {} # FIXME!
from bunch import Bunch
identity = Bunch(current=Bunch(user_name=u'Bob'))

class BodhiBase(object):
    """ Our custom model base class """
    __exclude_columns___ = None # List of columns to exclude from JSON

    def __init__(self, **kw):
        """ Automatically mapping attributes """
        for key, value in kw.iteritems():
            setattr(self, key, value)

    def __json__(self):
        items = []
        exclude = getattr(self, '__exclude_columns__', [])
        for col in self.__table__.columns:
            if col.name in exclude:
                continue
            prop = getattr(self, col.name)
            if isinstance(prop, list):
                prop = [child.__json__() for child in prop]
            elif hasattr(prop, '__json__'):
                prop = prop.__json__()
            elif isinstance(prop, datetime):
                prop = prop.strftime('%Y-%m-%d %H:%M:%S')
            items.append((col.name, prop))
        return dict(items)

Base = declarative_base(cls=BodhiBase)
metadata = Base.metadata
DBSession = scoped_session(sessionmaker())

##
## Enumerated type declarations
## Note: We're using single-letter names at the moment for compatiblity with
## sqlite dbs
##

class UpdateStatus(DeclEnum):
    pending = 'P', 'pending'
    testing = 'T', 'testing'
    stable = 'S', 'stable'
    unpushed = 'U', 'unpushed'
    obsolete = 'O', 'obsolete'

class UpdateType(DeclEnum):
    bugfix = 'B', 'bugfix'
    security = 'S', 'security'
    newpackage = 'N', 'new package'
    enhancement = 'E', 'enhancement'

class UpdateRequest(DeclEnum):
    testing = 'T', 'testing'
    stable = 'S', 'stable'
    obsolete = 'O', 'obsolete'
    unpush = 'U', 'unpush'

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


class Release(Base):
    __tablename__ = 'releases'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode(10), unique=True, nullable=False)
    long_name = Column(Unicode(25), unique=True, nullable=False)
    version = Column(Integer)
    id_prefix = Column(Unicode(25), nullable=False)
    dist_tag = Column(Unicode(20), nullable=False)
    stable_tag = Column(UnicodeText)
    testing_tag = Column(UnicodeText)
    candidate_tag = Column(UnicodeText)
    locked = Column(Boolean, default=False)
    metrics = Column(PickleType, default=None)


class Package(Base):
    __tablename__ = 'packages'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode(50), unique=True, nullable=False)
    committers = Column(PickleType, default=None)
    stable_karma = Column(Integer, default=3)
    unstable_karma = Column(Integer, default=-3)

    builds = relation('Build', backref='package')

    def __str__(self):
        x = header(self.name)
        states = { 'pending' : [], 'testing' : [], 'stable' : [] }
        if len(self.builds):
            for build in self.builds:
                if build.update and build.update.status.description in states:
                    states[build.update.status.description].append(build.update)
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

    id = Column(Integer, primary_key=True)
    nvr = Column(Unicode(100), unique=True, nullable=False)
    inherited = Column(Boolean, default=False)
    package_id = Column(Integer, ForeignKey('packages.id'))
    release_id = Column(Integer, ForeignKey('releases.id'))
    update_id = Column(Integer, ForeignKey('updates.id'))

    release = relation('Release', backref='builds', lazy=False)

    def get_latest(self):
        """ Return the path to the last released srpm of this package """
        latest_srpm = None
        koji_session = buildsys.get_session()

        # Grab a list of builds tagged with ``Release.stable_tag`` release tags, and find
        # the most recent update for this package, other than this one.  If
        # nothing is tagged for -updates, then grab the first thing in
        # ``Release.dist_tag``.  We aren't checking ``Release.candidate_tag`` first,
        # because there could potentially be packages that never make their way over
        # stable, so we don't want to generate ChangeLogs against those.
        evr = build_evr(koji_session.getBuild(self.nvr))
        latest = None
        for tag in [self.release.stable_tag, self.release.dist_tag]:
            builds = koji_session.getLatestBuilds(tag, package=self.package.name)

            # Find the first build that is older than us
            for build in builds:
                new_evr = build_evr(build)
                if rpm.labelCompare(evr, new_evr) < 0:
                    latest = get_nvr(build['nvr'])
                    break
            if latest:
                break
        if latest:
            return '-'.join(latest)

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
        if not descrip: return ""

        who = rpm_header[rpm.RPMTAG_CHANGELOGNAME]
        when = rpm_header[rpm.RPMTAG_CHANGELOGTIME]

        num = len(descrip)
        if num == 1: when = [when]

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
        srpm = os.path.join(src_path, "src", "%s.src.rpm" % ('-'.join(path[-3:])))
        if not os.path.isfile(srpm):
            log.debug("Cannot find SRPM: %s" % srpm)
            raise RPMNotFound
        return srpm

    def get_source_path(self):
        """ Return the path of this built update """
        return os.path.join(config.get('build_dir'), *get_nvr(self.nvr))


class Update(Base):
    __tablename__ = 'updates'

    id = Column(Integer, primary_key=True)
    _title = Column('title', UnicodeText)
    submitter = Column(Unicode(32), nullable=False)
    karma = Column(Integer, default=0)
    notes = Column(UnicodeText)

    # Enumerated types
    type = Column(UpdateType.db_type(), nullable=False)
    status = Column(UpdateStatus.db_type(),
                    default=UpdateStatus.pending,
                    nullable=False)
    request = Column(UpdateRequest.db_type())

    # Flags
    pushed = Column(Boolean, default=False)
    locked = Column(Boolean, default=False)

    # Bug settings
    close_bugs = Column(Boolean, default=True)

    # Team approvals
    security_approved = Column(Boolean, default=False)
    releng_approved = Column(Boolean, default=False)
    qa_approved = Column(Boolean, default=False)

    # Timestamps
    date_submitted = Column(DateTime, default=datetime.now)
    date_modified = Column(DateTime, onupdate=datetime.now)
    date_approved = Column(DateTime)
    date_pushed = Column(DateTime)
    security_approval_date = Column(DateTime)
    qa_approval_date = Column(DateTime)
    releng_approval_date = Column(DateTime)

    # eg: FEDORA-EPEL-2009-12345
    alias = Column(Unicode(32), default=None, unique=True)

    # One-to-one relationships
    release_id = Column(Integer, ForeignKey('releases.id'))
    release = relation('Release')

    # One-to-many relationships
    comments = relation('Comment', backref='update', lazy=False)
    builds = relation('Build', backref='update', lazy=False)

    # Many-to-many relationships
    bugs = relationship('Bug', secondary=update_bug_table,
                        backref='updates', lazy=False)
    cves = relation('CVE', secondary=update_cve_table,
                    backref='updates', lazy=False)

    # We may or may not need this, since we can determine the releases from the
    # builds
    #releases = relation('Release', secondary=update_release_table,
    #                    backref='updates', lazy=False)

    @synonym_for('_title')
    @property
    def title(self, show_nvrs=True, delim=' '):
        title = ', '.join([build.nvr for build in self.builds])
        return title + ' %s update' % self.type.description

    def get_title(self, delim=' '):
        return delim.join([build.nvr for build in self.builds])

    @property
    def stable_karma(self):
        return self.builds[0].package.stable_karma

    @property
    def unstable_karma(self):
        return self.builds[0].package.unstable_karma

    def get_bugstring(self, show_titles=False):
        """Return a space-delimited string of bug numbers for this update """
        val = u''
        if show_titles:
            i = 0
            for bug in self.bugs:
                bugstr = u'%s%s - %s\n' % (i and ' ' * 11 + ': ' or '',
                                          bug.bug_id, bug.title)
                val += u'\n'.join(wrap(bugstr, width=67,
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
            if int(year) != time.localtime()[0]: # new year
                id = 0
            id = int(id) + 1

        self.alias = u'%s-%s-%0.4d' % (self.release.id_prefix,
                                       time.localtime()[0], id)
        log.debug("Setting alias for %s to %s" % (self.title, self.alias))

        # FIXME: don't do this here:
        self.date_pushed = datetime.utcnow()

        DBSession.flush()

    def set_request(self, action):
        """ Attempt to request an action for this update.

        This method either sets the given request on this update, or raises
        an InvalidRequest exception.

        At the moment, this method cannot be called outside of a request.
        """
        if not authorized_user(self, identity):
            raise InvalidRequest("Unauthorized to perform action on %s" %
                                 self.title)
        action = UpdateRequest.from_string(action)
        if action is self.status:
            raise InvalidRequest("%s already %s" % (self.title,
                                                    action.description))
        if action is self.request:
            raise InvalidRequest("%s has already been submitted to %s" % (
                                 self.title, self.request.description))
        if action is UpdateRequest.unpush:
            self.unpush()
            self.comment(u'This update has been unpushed',
                         author=identity.current.user_name)
            flash_log("%s has been unpushed" % self.title)
            return
        elif action is UpdateRequest.obsolete:
            self.obsolete()
            flash_log("%s has been obsoleted" % self.title)
            return
        # TODO:
        # Make it so that we can optionally configure bodhi to require mandatory
        # signoff from a specific group before an update can hit stable:
        #       eg: Security Team (for security updates) 
        #                or
        #           AutoQA (for all updates)
        #elif self.type is UpdateType.security and not self.date_approved:
        #    flash_log("%s is awaiting approval of the Security Team" %
        #              self.title)
        #    self.request = action
        #    return
        self.request = action
        self.pushed = False
        self.date_pushed = None
        flash_log("%s has been submitted for %s" % (
            self.title, action.description))
        self.comment(u'This update has been submitted for %s' %
                action.description, author=identity.current.user_name)
        mail.send_admin(action.description, self)

    def request_complete(self):
        """
        Perform post-request actions.
        """
        if self.request is UpdateRequest.testing:
            self.status = UpdateStatus.testing
        elif self.request is UpdateRequest.stable:
            self.status = UpdateStatus.stable
        self.request = None
        self.pushed = True
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
                    bz = Bug.get_bz()
                    for bug in self.bugs:
                        if bug.parent:
                            parent = bz.getbug(bug.bug_id)
                            if parent.bug_status == "NEW":
                                log.debug("Parent bug %d is still NEW; not "
                                          "closing.." % bug.bug_id)
                                continue
                            depsclosed = True
                            for dep in parent.dependson:
                                try:
                                    tracker = bz.getbug(dep)
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
            self.title.replace(',', ', '), width=80, initial_indent=' '*5,
            subsequent_indent=' '*5)), '=' * 80)
        if self.alias:
            val += u"  Update ID: %s\n" % self.alias
        val += u"""    Release: %s
     Status: %s
       Type: %s
      Karma: %d""" % (self.release.long_name, self.status.description, 
                      self.type.description, self.karma)
        if self.request != None:
            val += u"\n    Request: %s" % self.request.description
        if len(self.bugs):
            bugs = self.get_bugstring(show_titles=True)
            val += u"\n       Bugs: %s" % bugs
        if len(self.cves):
            val += u"\n       CVEs: %s" % self.get_cvestring()
        if self.notes:
            notes = wrap(self.notes, width=67, subsequent_indent=' ' * 11 +': ')
            val += u"\n      Notes: %s" % '\n'.join(notes)
        val += u"""
  Submitter: %s
  Submitted: %s\n""" % (self.submitter, self.date_submitted)
        if len(self.comments):
            val += u"   Comments: "
            comments = []
            for comment in self.comments:
                if comment.anonymous:
                    anonymous = " (unauthenticated)"
                else:
                    anonymous = ""
                comments.append(u"%s%s%s - %s (karma %s)" % (' ' * 13,
                                comment.author, anonymous, comment.timestamp,
                                comment.karma))
                if comment.text:
                    text = wrap(comment.text, initial_indent=' ' * 13,
                                subsequent_indent=' ' * 13, width=67)
                    comments.append(u'\n'.join(text))
            val += u'\n'.join(comments).lstrip() + u'\n'
        val += u"\n  %s\n" % (config.get('base_address') + url(self.get_url()))
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
        Create any new bugs, and remove any missing ones.  Destroy removed bugs
        that are no longer referenced anymore
        """
        fetchdetails = True
        Session = DBSession()
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
                    Session.delete(bug)
            Session.flush()
        for bug in bugs:
            bz = Session.query(Bug).filter_by(bug_id=bug).first()
            if not bz:
                if fetchdetails:
                    bugzilla = Bug.get_bz()
                    newbug = bugzilla.getbug(bug)
                    bz = Bug(bug_id=newbug.bug_id)
                    bz.fetch_details(newbug)
                else:
                    bz = Bug(bug_id=int(bug))
            if bz not in self.bugs:
                Session.add(bz)
                self.bugs.append(bz)
        Session.commit()

    def update_cves(self, cves):
        """
        Create any new CVES, and remove any missing ones.  Destroy removed CVES 
        that are no longer referenced anymore.
        """
        Session = DBSession()
        for cve in self.cves:
            if cve.cve_id not in cves and len(cve.updates) == 0:
                log.debug("Destroying stray CVE #%s" % cve.cve_id)
                Session.delete(cve)
        for cve_id in cves:
            try:
                cve = CVE.query.filter_by(cve_id=cve_id).one()
                if cve not in self.cves:
                    self.cves.append(cve)
            except: # TODO: catch sqlalchemy's not found exception!
                log.debug("Creating new CVE: %s" % cve_id)
                cve = CVE(cve_id=cve_id)
                ession.save(cve)
                self.cves.append(cve)
        Session.commit()

    def get_pushed_age(self):
        return get_age(self.date_pushed)

    def get_submitted_age(self):
        return get_age(self.date_submitted)

    def get_pushed_color(self):
        age = get_age_in_days(self.date_pushed)
        if age == 0 or self.karma < 0:
            color = '#ff0000' # red
        elif age < 4:
            color = '#ff6600' # orange
        elif age < 7:
            color = '#ffff00' # yellow
        else:
            color = '#00ff00' # green
        return color

    def comment(self, text, karma=0, author=None, anonymous=False):
        """ Add a comment to this update, adjusting the karma appropriately.

        Each user has the ability to comment as much as they want, but only
        their last karma adjustment will be counted.  If the karma reaches
        the 'stable_karma' value, then request that this update be marked
        as stable.  If it reaches the 'unstable_karma', it is unpushed.
        """
        if not author:
            author = identity.current.user_name
        if not anonymous and karma != 0 and \
           not filter(lambda c: c.author == author and c.karma == karma,
                      self.comments):
            mycomments = [c.karma for c in self.comments if c.author == author]
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
                self.pushed = False
                self.date_pushed = None
                mail.send(self.get_maintainers(), 'stablekarma', self)
                mail.send_admin('stablekarma', self)
            if self.status is UpdateStatus.testing \
                    and self.unstable_karma != 0 \
                    and self.karma == self.unstable_karma:
                log.info("Automatically unpushing %s" % self.title)
                self.obsolete()
                mail.send(self.get_maintainers(), 'unstable', self)

        comment = Comment(text=text, karma=karma,author=author,
                          anonymous=anonymous)

        DBSession.add(comment)
        self.comments.append(comment)
        DBSession.flush()

        # Send a notification to everyone that has commented on this update
        people = set()
        for person in self.get_maintainers():
            people.add(person)
        for comment in self.comments:
            if comment.anonymous or comment.author == 'bodhi':
                continue
            people.add(comment.author)
        mail.send(people, 'comment', self)

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
                log.debug("Moving %s from %s to %s" % (build.nvr, curtag, newtag))
                koji.moveBuild(curtag, newtag, build.nvr, force=True)
        self.pushed = False
        self.status = UpdateStatus.unpushed
        mail.send_admin('unpushed', self)
        #DBSession.flush()

    def untag(self):
        """ Untag all of the builds in this update """
        log.info("Untagging %s" % self.title)
        koji = buildsys.get_session()
        tag = self.get_build_tag()
        for build in self.builds:
            koji.untagBuild(tag, build.nvr, force=True)
        self.pushed = False
        DBSession.flush()

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
        DBSession.flush()

    def get_maintainers(self):
        """
        Return a list of people that have commit access to all of the packages
        that are contained within this update.
        """
        people = set()
        for build in self.builds:
            if build.package.committers:
                for committer in build.package.committers:
                    people.add(committer)
        return list(people)

    def get_comments(self):
        sorted = []
        sorted.extend(self.comments)
        sorted.sort(lambda x, y: cmp(x.timestamp, y.timestamp))
        return sorted


class Comment(Base):
    __tablename__ = 'comments'

    id = Column(Integer, primary_key=True)
    author = Column(Unicode(50), nullable=False)
    karma = Column(Integer, default=0)
    text = Column(UnicodeText)
    anonymous = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    update_id = Column('update_id', Integer, ForeignKey('updates.id'))

    def __str__(self):
        karma = '0'
        if self.karma != 0:
            karma = '%+d' % (self.karma,)
        if self.anonymous:
            anonymous = " (unauthenticated)"
        else:
            anonymous = ""
        return "%s%s - %s (karma: %s)\n%s" % (self.author, anonymous,
                                              self.timestamp, karma, self.text)


class CVE(Base):
    __tablename__ = 'cves'

    id = Column(Integer, primary_key=True)
    cve_id = Column(Unicode(13), unique=True, nullable=False)

    @property
    def url(self):
        return "http://www.cve.mitre.org/cgi-bin/cvename.cgi?name=%s" % self.cve_id


class Bug(Base):
    __tablename__ = 'bugs'

    id = Column(Integer, primary_key=True)

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
    cves = relation(CVE, secondary=bug_cve_table, backref='bugs')

    # Foreign Keys used by other relations
    #update_id = Column(Integer, ForeignKey('updates.id'))

    #_bz_server = config.get("bz_server")

    # TODO: put this in the config?
    default_msg = "%s has been pushed to the %s repository.  If problems " + \
                  "still persist, please make note of it in this bug report."

    @staticmethod
    def get_bz():
        me = config.get('bodhi_email')
        password = config.get('bodhi_password', None)
        if me and password:
            bz = bugzilla.Bugzilla(url=config.get("bz_server"), user=me,
                                   password=password)
        else:
            bz = bugzilla.Bugzilla(url=config.get("bz_server"))
        return bz

    def fetch_details(self, bug=None):
        if not bug:
            bz = Bug.get_bz()
            try:
                bug = bz.getbug(self.bug_id)
            except xmlrpclib.Fault, f:
                self.title = 'Invalid bug number'
                log.warning("Got fault from Bugzilla: %s" % str(f))
                return
        if bug.product == 'Security Response':
            self.parent = True
        self.title = str(bug.short_desc)
        if 'security' in bug.keywords.lower():
            self.security = True
        DBSession.flush()

    def _default_message(self, update):
        message = self.default_msg % (update.get_title(delim=', '), "%s %s" % 
                                   (update.release.long_name,
                                    update.status.description))
        if update.status is UpdateStatus.testing:
            message += ("\n If you want to test the update, you can install " +
                       "it with \n su -c 'yum --enablerepo=updates-testing " +
                       "update %s'.  You can provide feedback for this " +
                       "update here: %s") % (' '.join([build.package.name for 
                           build in update.builds]),
                           config.get('base_address') + url(update.get_url()))

        return message

    def add_comment(self, update, comment=None):
        if not config.get('bodhi_email'):
            log.warning("No bodhi_email defined; skipping bug comment")
            return
        bz = Bug.get_bz()
        if not comment:
            comment = self._default_message(update)
        log.debug("Adding comment to Bug #%d: %s" % (self.bug_id, comment))
        try:
            bug = bz.getbug(self.bug_id)
            bug.addcomment(comment)
        except Exception, e:
            log.error("Unable to add comment to bug #%d\n%s" % (self.bug_id,
                                                                str(e)))

    def testing(self, update):
        """
        Change the status of this bug to ON_QA, and comment on the bug with
        some details on how to test and provide feedback for this update.
        """
        bz = Bug.get_bz()
        comment = self._default_message(update)
        log.debug("Setting Bug #%d to ON_QA" % self.bug_id)
        try:
            bug = bz.getbug(self.bug_id)
            bug.setstatus('ON_QA', comment=comment)
        except Exception, e:
            log.error("Unable to alter bug #%d\n%s" % (self.bug_id, str(e)))

    def close_bug(self, update):
        bz = Bug.get_bz()
        try:
            ver = '-'.join(get_nvr(update.builds[0].nvr)[-2:])
            bug = bz.getbug(self.bug_id)
            bug.close('NEXTRELEASE', fixedin=ver)
        except xmlrpclib.Fault, f:
            log.error("Unable to close bug #%d: %s" % (self.bug_id, str(f)))

    def get_url(self):
        return "%s/show_bug.cgi?id=%s" % (config.get('bz_baseurl'), self.bug_id)


#class Stack(Base):
#    """
#    A Stack in bodhi represents a group of packages that are commonly pushed
#    together as a group.
#    """
#    # name
#    # packages =  Many to many?
#    # updates


def populate():
    session = DBSession()
    release = Release(name=u'F15', long_name=u'Fedora 15', id_prefix=u'FEDORA', dist_tag=u'dist-f15')
    session.add(release)
    pkg = Package(name=u'bodhi')
    session.add(pkg)
    build = Build(nvr=u'bodhi-2.0-1.fc15', release=release)
    session.add(build)
    update = Update(builds=[build], submitter=u'bodhi')
    update.type = UpdateType.bugfix
    session.add(update)
    session.commit()
    #session.flush()
    #transaction.commit()

def initialize_sql(engine):
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine
    Base.metadata.create_all(engine)
    try:
        populate()
    except IntegrityError:
        DBSession.rollback()
