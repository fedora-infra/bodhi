# $Id: model.py,v 1.9 2007/01/08 06:07:07 lmacken Exp $
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

import os
import rpm
import time
import logging
import xmlrpclib
import turbogears

from sqlobject import *
from datetime import datetime

from turbogears import config, flash
from turbogears.database import PackageHub

from os.path import isfile, join
from textwrap import wrap

from bodhi import buildsys, mail
from bodhi.util import get_nvr, rpm_fileheader, header, get_age, get_age_in_days
from bodhi.exceptions import RPMNotFound
from bodhi.identity.tables import *

log = logging.getLogger(__name__)
hub = PackageHub("bodhi")
__connection__ = hub

soClasses=('Release', 'Package', 'PackageBuild', 'PackageUpdate', 'CVE',
           'Bugzilla', 'Comment', 'User', 'Group', 'Visit')

class Release(SQLObject):
    """ Table of releases that we will be pushing updates for """
    name        = UnicodeCol(alternateID=True, notNone=True)
    long_name   = UnicodeCol(notNone=True)
    updates     = MultipleJoin('PackageUpdate', joinColumn='release_id')
    id_prefix   = UnicodeCol(notNone=True)
    dist_tag    = UnicodeCol(notNone=True) # ie dist-fc7

class Package(SQLObject):
    name           = UnicodeCol(alternateID=True, notNone=True)
    builds         = MultipleJoin('PackageBuild', joinColumn='package_id')
    suggest_reboot = BoolCol(default=False)

    def updates(self):
        for build in self.builds:
            for update in build.updates:
                yield update

    def num_updates(self):
        i = 0
        for build in self.builds:
            i += len(build.updates)
        return i

    def __str__(self):
        x = header(self.name)
        states = { 'pending' : [], 'testing' : [], 'stable' : [] }
        if len(self.builds):
            for build in self.builds:
                for state in states.keys():
                    states[state] += filter(lambda u: u.status == state,
                                            build.updates)
        for state in states.keys():
            if len(states[state]):
                x += "\n %s Updates (%d)\n" % (state.title(),
                                               len(states[state]))
                for update in states[state]:
                    x += "    o %s\n" % update.title
        return x

class PackageBuild(SQLObject):
    nvr             = UnicodeCol(notNone=True, alternateID=True)
    package         = ForeignKey('Package')
    updates         = RelatedJoin("PackageUpdate")

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
        return str

    def get_srpm_path(self):
        """ Return the path to the SRPM for this update """
        src_path = self.get_source_path()
        path = src_path.split('/')
        srpm = join(src_path, "src", "%s.src.rpm" % ('-'.join(path[-3:])))
        if not isfile(srpm):
            log.debug("Cannot find SRPM: %s" % srpm)
            raise RPMNotFound
        return srpm

    def get_source_path(self):
        """ Return the path of this built update """
        return join(config.get('build_dir'), *get_nvr(self.nvr))

    def get_latest(self):
        """ Return the path to the last released srpm of this package """
        latest_srpm = None
        koji_session = buildsys.get_session()

        # Grab a list of builds tagged with dist-$RELEASE-updates, and find
        # the most recent update for this package, other than this one.  If
        # nothing is tagged for -updates, then grab the first thing in
        # dist-$RELEASE.  We aren't checking -updates-candidate first, because
        # there could potentially be packages that never make their way over
        # -updates, so we don't want to generate ChangeLogs against those.
        nvr = get_nvr(self.nvr)
        for tag in ['%s-updates', '%s']:
            tag %= self.updates[0].release.dist_tag
            builds = koji_session.getLatestBuilds(tag, None, self.package.name)
            latest = None

            # Find the first build that is older than us
            for build in builds:
                if rpm.labelCompare(nvr, get_nvr(build['nvr'])) > 0:
                    latest = get_nvr(build['nvr'])
                    break

            if latest:
                srpm_path = join(config.get('build_dir'), latest[0],
                                 latest[1], latest[2], 'src',
                                 '%s.src.rpm' % '-'.join(latest))
                if isfile(srpm_path):
                    log.debug("Latest build before %s: %s" % (self.nvr,
                                                              srpm_path))
                    latest_srpm = srpm_path
                else:
                    log.warning("Latest build %s not found" % srpm_path)
                break

        return latest_srpm

class PackageUpdate(SQLObject):
    """ This class defines an update in our system. """
    title            = UnicodeCol(notNone=True, alternateID=True, unique=True)
    builds           = RelatedJoin("PackageBuild")
    date_submitted   = DateTimeCol(default=datetime.utcnow, notNone=True)
    date_modified    = DateTimeCol(default=None)
    date_pushed      = DateTimeCol(default=None)
    submitter        = UnicodeCol(notNone=True)
    update_id        = UnicodeCol(default=None)
    type             = EnumCol(enumValues=['security', 'bugfix', 'enhancement'])
    cves             = RelatedJoin("CVE")
    bugs             = RelatedJoin("Bugzilla")
    release          = ForeignKey('Release')
    status           = EnumCol(enumValues=['pending', 'testing', 'stable',
                                           'obsolete'], default='pending')
    pushed           = BoolCol(default=False)
    notes            = UnicodeCol()
    request          = EnumCol(enumValues=['testing', 'stable', 'obsolete',
                                           None], default=None)
    comments         = MultipleJoin('Comment', joinColumn='update_id')
    karma            = IntCol(default=0)
    close_bugs       = BoolCol(default=True)
    nagged           = PickleCol(default={}) # { nagmail_name : datetime, ... }

    def get_title(self, delim=' '):
        return delim.join([build.nvr for build in self.builds])

    def get_bugstring(self, show_titles=False):
        """ Return a space-delimited string of bug numbers for this update """
        val = ''
        if show_titles:
            i = 0
            for bug in self.bugs:
                bugstr = '%s%s - %s\n' % (i and ' ' * 11 + ': ' or '',
                                          bug.bz_id, bug.title)
                val += '\n'.join(wrap(bugstr, width=67,
                                      subsequent_indent=' ' * 11 + ': ')) + '\n'
                i += 1
            val = val[:-1]
        else:
            val = ' '.join([str(bug.bz_id) for bug in self.bugs])
        return val

    def get_cvestring(self):
        """ Return a space-delimited string of CVE ids for this update """
        return ' '.join([cve.cve_id for cve in self.cves])

    def assign_id(self):
        """
        Assign an update ID to this update.  This function finds the next number
        in the sequence of pushed updates for this release, increments it and
        prefixes it with the id_prefix of the release and the year
        (ie FEDORA-2007-0001)
        """
        if self.update_id != None and self.update_id != u'None':
            log.debug("Keeping current update id %s" % self.update_id)
            return
        update = PackageUpdate.select(PackageUpdate.q.update_id != 'None',
                                      orderBy=PackageUpdate.q.update_id)
        try:
            id = int(update[-1].update_id.split('-')[-1]) + 1
        except (AttributeError, IndexError):
            id = 1
        self.update_id = u'%s-%s-%0.4d' % (self.release.id_prefix,
                                           time.localtime()[0],id)
        log.debug("Setting update_id for %s to %s" % (self.title,
                                                      self.update_id))
        hub.commit()

    def request_complete(self):
        """
        Perform post-request actions.
        """
        if self.request == 'testing':
            self.pushed = True
            self.date_pushed = datetime.utcnow()
            self.status = 'testing'
            self.assign_id()
            self.send_update_notice()
            map(lambda bug: bug.add_comment(self), self.bugs)
            self.comment('This update has been pushed to testing',
                         author='bodhi')
        elif self.request == 'obsolete':
            self.comment('This update has been obsoleted', author='bodhi')
            self.pushed = False
            self.status = 'obsolete'
        elif self.request == 'stable':
            self.pushed = True
            self.date_pushed = datetime.utcnow()
            self.status = 'stable'
            self.assign_id()
            self.comment('This update has been pushed to stable',
                         author='bodhi')
            self.send_update_notice()
            map(lambda bug: bug.add_comment(self), self.bugs)
            if self.close_bugs:
                map(lambda bug: bug.close_bug(self), self.bugs)

        log.info("%s request on %s complete!" % (self.request, self.title))
        self.request = None
        hub.commit()

    def send_update_notice(self):
        import turbomail
        log.debug("Sending update notice for %s" % self.title)
        mailinglist = None
        sender = config.get('bodhi_email')
        if not sender:
            log.error("bodhi_email not defined in configuration!  Unable " +
                      "to send update notice")
            return
        if self.status == 'stable':
            mailinglist = config.get('%s_announce_list' %
                              self.release.id_prefix.lower())
        elif self.status == 'testing':
            mailinglist = config.get('%s_test_announce_list' %
                              self.release.id_prefix.lower())
        if mailinglist:
            for subject, body in mail.get_template(self):
                message = turbomail.Message(sender, mailinglist, subject)
                message.plain = body
                try:
                    turbomail.enqueue(message)
                    log.debug("Sending mail: %s" % message.plain)
                except turbomail.MailNotEnabledException:
                    log.warning("mail.on is not True!")
        else:
            log.error("Cannot find mailing list address for update notice")

    def get_url(self):
        """ Return the relative URL to this update """
        status = self.status == 'testing' and 'testing/' or ''
        if not self.pushed: status = 'pending/'
        return '/%s%s/%s' % (status, self.release.name, self.title)

    def __str__(self):
        """
        Return a string representation of this update.
        """
        val = header(self.title.replace(',', ', '))
        if self.update_id:
            val += "  Update ID: %s\n" % self.update_id
        val += """    Release: %s
     Status: %s
       Type: %s
      Karma: %d""" % (self.release.long_name,self.status,self.type,self.karma)
        if self.request != None:
            val += "\n    Request: %s" % self.request
        if len(self.bugs):
            bugs = self.get_bugstring(show_titles=True)
            val += "\n       Bugs: %s" % bugs
        if len(self.cves):
            val += "\n       CVEs: %s" % self.get_cvestring()
        if self.notes:
            notes = wrap(self.notes, width=67, subsequent_indent=' '*11 +': ')
            val += "\n      Notes: %s" % '\n'.join(notes)
        val += """
  Submitter: %s
  Submitted: %s\n\n  %s
        """ % (self.submitter, self.date_submitted,
               config.get('base_address') + turbogears.url(self.get_url()))
        return val.rstrip()

    def get_build_tag(self):
        """
        Get the tag that this build is currently tagged with.
        TODO: we should probably get this stuff from koji instead of guessing
        """
        tag = '%s-updates' % self.release.dist_tag
        if self.status == 'pending':
            tag += '-candidate'
        elif self.status == 'testing':
            tag += '-testing'
        return tag

    def update_bugs(self, bugs):
        """
        Create any new bugs, and remove any missing ones.  Destroy removed bugs
        that are no longer referenced anymore
        """
        for bug in self.bugs:
            if bug.bz_id not in bugs:
                self.removeBugzilla(bug)
                if len(bug.updates) == 0:
                    log.debug("Destroying stray Bugzilla #%d" % bug.bz_id)
                    bug.destroySelf()
        for bug in bugs:
            try:
                bz = Bugzilla.byBz_id(bug)
                if bz not in self.bugs:
                    self.addBugzilla(bz)
            except SQLObjectNotFound:
                bz = Bugzilla(bz_id=bug)
                self.addBugzilla(bz)

    def update_cves(self, cves):
        """
        Create any new CVES, and remove any missing ones.  Destroy removed CVES 
        that are no longer referenced anymore.
        """
        for cve in self.cves:
            if cve.cve_id not in cves:
                log.debug("Removing CVE %s from %s" % (cve.cve_id, self.title))
                self.removeCVE(cve)
                if cve.cve_id not in cves and len(cve.updates) == 0:
                    log.debug("Destroying stray CVE #%s" % cve.cve_id)
                    cve.destroySelf()
        for cve_id in cves:
            try:
                cve = CVE.byCve_id(cve_id)
                if cve not in self.cves:
                    self.addCVE(cve)
            except SQLObjectNotFound:
                log.debug("Creating new CVE: %s" % cve_id)
                cve = CVE(cve_id=cve_id)
                self.addCVE(cve)

    def get_pushed_age(self):
        return get_age(self.date_pushed)

    def get_submitted_age(self):
        return get_age(self.date_submitted)
    def get_pushed_color(self):
        age = get_age_in_days(self.date_pushed)
        if age == 0:
            color = '#ff0000' # red
        elif age < 4:
            color = '#ff6600' # orange
        elif age < 7:
            color = '#ffff00' # yellow
        else:
            color = '#00ff00' # green
        return color

    def comment(self, text, karma=0, author=None):
        """
        Add a comment to this update, adjusting the karma appropriately.
        Each user can adjust an updates karma once in each direction, thus
        being able to negate their original choice.  If the karma reaches
        the 'stable_karma' configuration option, then request that this update
        be marked as stable.
        """
        stable_karma = config.get('stable_karma')
        if not author: author = identity.current.user_name
        if not filter(lambda c: c.author == author and
                      c.karma == karma, self.comments):
            self.karma += karma
            log.info("Updated %s karma to %d" % (self.title, self.karma))
            if stable_karma and stable_karma == self.karma:
                log.info("Automatically marking %s as stable" % self.title)
                self.request = 'stable'
                mail.send(self.submitter, 'stablekarma', self)
                mail.send_admin('move', self)
        comment = Comment(text=text, karma=karma, update=self, author=author)

        # Send a notification to everyone that has commented on this update
        people = set()
        people.add(self.submitter)
        map(lambda comment: people.add(comment.author), self.comments)
        if 'bodhi' in people:
            people.remove('bodhi')
        for person in people:
            mail.send(person, 'comment', self)

class Comment(SQLObject):
    timestamp   = DateTimeCol(default=datetime.now)
    update      = ForeignKey("PackageUpdate", notNone=True)
    author      = UnicodeCol(notNone=True)
    karma       = IntCol(default=0)
    text        = UnicodeCol()

    def __str__(self):
        karma = '0'
        if self.karma != 0:
            karma = '%+d' % (self.karma,)
        return "%s - %s (karma: %s)\n%s" % (self.author, self.timestamp,
                                            karma, self.text)

class CVE(SQLObject):
    """ Table of CVEs fixed within updates that we know of. """
    cve_id  = UnicodeCol(alternateID=True, notNone=True)
    updates = RelatedJoin("PackageUpdate")

    def get_url(self):
        return "http://www.cve.mitre.org/cgi-bin/cvename.cgi?name=%s" % self.cve_id

class Bugzilla(SQLObject):
    """ Table of Bugzillas that we know about. """
    bz_id    = IntCol(alternateID=True)
    title    = UnicodeCol(default=None)
    updates  = RelatedJoin("PackageUpdate")
    security = BoolCol(default=False)

    _bz_server = config.get("bz_server")
    default_msg = "%s has been pushed to the %s repository.  If problems " + \
                  "still persist, please make note of it in this bug report."

    def _set_bz_id(self, bz_id):
        """
        When the ID for this bug is set (upon creation), go out and fetch the
        details and check if this bug is security related.
        """
        self._SO_set_bz_id(bz_id)
        self._fetch_details()

    def _fetch_details(self):
        if not self._bz_server:
            return
        try:
            log.debug("Fetching bugzilla #%d" % self.bz_id)
            server = xmlrpclib.Server(self._bz_server)
            me = config.get('bodhi_email')
            password = config.get('bodhi_password')
            if not password:
                log.error("No password stored for bodhi_email")
                return
            bug = server.bugzilla.getBug(self.bz_id, me, password)
            del server
            self.title = bug['short_desc']
            if bug['keywords'].lower().find('security') != -1:
                self.security = True
        except xmlrpclib.Fault, f:
            self.title = 'Invalid bug number'
            log.warning("Got fault from Bugzilla: %s" % str(f))
        except Exception, e:
            self.title = 'Unable to fetch bug title'
            log.error(self.title + ': ' + str(e))

    def default_message(self, update):
        message = self.default_msg % (update.get_title(delim=', '), "%s %s" % 
                                   (update.release.long_name, update.status))
        if update.status == "testing":
            message += "\n If you want to test the update, you can install " + \
                       "it with \n su -c 'yum --enablerepo=updates-testing " + \
                       "update %s'" % (' '.join([build.package.name for build
                                                 in update.builds]))

        return message

    def add_comment(self, update, comment=None):
        me = config.get('bodhi_email')
        password = config.get('bodhi_password', None)
        if password:
            if not comment:
                comment = self.default_message(update)
            log.debug("Adding comment to Bug #%d: %s" % (self.bz_id, comment))
            try:
                server = xmlrpclib.Server(self._bz_server)
                server.bugzilla.addComment(self.bz_id, comment, me, password, 0)
                del server
            except Exception, e:
                log.error("Unable to add comment to bug #%d\n%s" % (self.bz_id,
                                                                    str(e)))
        else:
            log.warning("bodhi_password not defined; unable to modify bug")

    def close_bug(self, update):
        me = config.get('bodhi_email')
        password = config.get('bodhi_password')
        if password:
            log.debug("Closing Bug #%d" % self.bz_id)
            ver = '-'.join(get_nvr(update.builds[0].nvr)[-2:])
            try:
                server = xmlrpclib.Server(self._bz_server)
                server.bugzilla.closeBug(self.bz_id, 'ERRATA', me,
                                         password, 0, ver)
                del server
            except Exception, e:
                log.error("Cannot close bug #%d" % self.bz_id)
                log.error(e)
        else:
            log.warning("bodhi_password not defined; unable to close bug")

    def get_url(self):
        return "https://bugzilla.redhat.com/show_bug.cgi?id=%s" % self.bz_id

## Static list of releases -- used by master.kid, and the NewUpdateForm widget
global _releases
_releases = None
def releases():
    global _releases
    if not _releases:
        _releases = [(rel.name, rel.long_name, rel.id) for rel in \
                     Release.select()]
    for release in _releases:
        yield release
