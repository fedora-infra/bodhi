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

import rpm
import time
import logging
import bugzilla
import turbomail
import xmlrpclib

from sqlobject import *
from datetime import datetime

from turbogears import config, url
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
    locked      = BoolCol(default=False)

    def get_version(self):
        import re
        regex = re.compile('\w+(\d+)$')
        num = int(regex.match(self.name).groups()[0])
        del re, regex
        return num

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
        del states
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
        del rpm_header
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
    approved         = BoolCol(default=False)

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
            prefix, year, id = update[-1].update_id.split('-')
            if int(year) != time.localtime()[0]: # new year
                id = 0
            id = int(id) + 1
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
        elif self.request == 'obsolete':
            self.pushed = False
            self.status = 'obsolete'
        elif self.request == 'stable':
            self.pushed = True
            self.date_pushed = datetime.utcnow()
            self.status = 'stable'
            self.assign_id()
        self.request = None
        hub.commit()

    def modify_bugs(self):
        """
        Comment on and close this updates bugs as necessary
        """
        if self.status == 'testing':
            map(lambda bug: bug.add_comment(self), self.bugs)
        elif self.status == 'stable':
            map(lambda bug: bug.add_comment(self), self.bugs)

            if self.close_bugs:
                if self.type == 'security':
                    # Close all tracking bugs first
                    for bug in self.bugs:
                        if not bug.parent:
                            log.debug("Closing tracker bug %d" % bug.bz_id)
                            bug.close_bug(self)

                    # Now, close our parents bugs as long as nothing else
                    # depends on them, and they are not in a NEW state
                    bz = Bugzilla.get_bz()
                    for bug in self.bugs:
                        if bug.parent:
                            parent = bz.getbug(bug.bz_id)
                            if parent.bug_status == "NEW":
                                log.debug("Parent bug %d is still NEW; not "
                                          "closing.." % bug.bz_id)
                                continue
                            depsclosed = True
                            for dep in parent.dependson:
                                tracker = bz.getbug(dep)
                                if tracker.bug_status != "CLOSED":
                                    log.debug("Tracker %d not yet closed" %
                                              bug.bz_id)
                                    depsclosed = False
                            if depsclosed:
                                log.debug("Closing parent bug %d" % bug.bz_id)
                                bug.close_bug()
                else:
                    map(lambda bug: bug.close_bug(self), self.bugs)

    def status_comment(self):
        """
        Add a comment to this update about a change in status
        """
        if self.status == 'stable':
            self.comment('This update has been pushed to stable',
                         author='bodhi')
        elif self.status == 'testing':
            self.comment('This update has been pushed to testing',
                         author='bodhi')
        elif self.status == 'obsolete':
            self.comment('This update has been obsoleted', author='bodhi')

    def send_update_notice(self):
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
        path = ['/%s' % self.release.name]
        if self.update_id:
            path.append(self.update_id)
        else:
            path.append(self.status)
            path.append(self.title)
        return join(*path)

    def __str__(self):
        """
        Return a string representation of this update.
        """
        val = u"%s\n%s\n%s\n" % ('=' * 80, u'\n'.join(wrap(
            self.title.replace(',', ', '), width=80, initial_indent=' '*5,
            subsequent_indent=' '*5)), '=' * 80)
        if self.update_id:
            val += u"  Update ID: %s\n" % self.update_id
        val += u"""    Release: %s
     Status: %s
       Type: %s
      Karma: %d""" % (self.release.long_name,self.status,self.type,self.karma)
        if self.request != None:
            val += u"\n    Request: %s" % self.request
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
                comments.append(u"%s%s - %s (karma %s)" % (' ' * 13,
                                comment.author, comment.timestamp,
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
        if self.status in ('pending', 'obsolete'):
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
        """
        Add a comment to this update, adjusting the karma appropriately.
        Each user can adjust an updates karma once in each direction, thus
        being able to negate their original choice.  If the karma reaches
        the 'stable_karma' configuration option, then request that this update
        be marked as stable.
        """
        stable_karma = config.get('stable_karma')
        unstable_karma = config.get('unstable_karma')
        if not author: author = identity.current.user_name
        if karma != 0 and not filter(lambda c: c.author == author and
                                     c.karma == karma, self.comments):
            self.karma += karma
            log.info("Updated %s karma to %d" % (self.title, self.karma))
            if stable_karma and stable_karma == self.karma:
                log.info("Automatically marking %s as stable" % self.title)
                self.request = 'stable'
                mail.send(self.submitter, 'stablekarma', self)
                mail.send_admin('stablekarma', self)
            if self.status == 'testing' and unstable_karma and \
               self.karma == unstable_karma:
                log.info("Automatically unpushing %s" % self.title)
                self.obsolete()
                mail.send(self.submitter, 'unstable', self)
        Comment(text=text, karma=karma, update=self, author=author,
                anonymous=anonymous)

        # Send a notification to everyone that has commented on this update
        people = set()
        people.add(self.submitter)
        for comment in self.comments:
            if comment.author == 'bodhi' or comment.anonymous:
                continue
            people.add(comment.author)
        for person in people:
            mail.send(person, 'comment', self)

    def unpush(self):
        """ Move this update back to its dist-fX-updates-candidate tag """
        log.debug("Unpushing %s" % self.title)
        koji = buildsys.get_session()
        tag = '%s-updates-candidate' % self.release.dist_tag
        for build in self.builds:
            log.debug("Moving %s from %s to %s" % (build.nvr,
                      self.get_build_tag(), tag))
            koji.moveBuild(self.get_build_tag(), tag, build.nvr, force=True)
        self.pushed = False
        self.status = 'pending'
        mail.send_admin('unpushed', self)

    def obsolete(self, newer=None):
        """
        Obsolete this update. Even though unpushing/obsoletion is an "instant"
        action, changes in the repository will not propagate until the next
        mash takes place.
        """
        log.debug("Obsoleting %s" % self.title)
        self.unpush()
        self.status = 'obsolete'
        self.request = None
        if newer:
            self.comment("This update has been obsoleted by %s" % newer,
                         author='bodhi')
        else:
            self.comment("This update has been obsoleted", author='bodhi')

class Comment(SQLObject):
    timestamp   = DateTimeCol(default=datetime.utcnow)
    update      = ForeignKey("PackageUpdate", notNone=True)
    author      = UnicodeCol(notNone=True)
    karma       = IntCol(default=0)
    text        = UnicodeCol()
    anonymous   = BoolCol(default=False)

    def __str__(self):
        karma = '0'
        if self.karma != 0:
            karma = '%+d' % (self.karma,)
        return "%s - %s (karma: %s)\n%s" % (self.author, self.timestamp,
                                            karma, self.text)

class CVE(SQLObject):
    """
    Table of CVEs fixed within updates that we know of.

    This table has since been deprecated.  We are now tracking CVEs via 
    Bugzilla.  See http://fedoraproject.org/wiki/Security/TrackingBugs
    for more information on our bug tracking policy.

    @deprecated: We no longer track CVEs directly in bodhi.  See our new
    security bug tracking policy for more details:
        http://fedoraproject.org/wiki/Security/TrackingBugs
    """
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
    parent   = BoolCol(default=False)

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

    def _fetch_details(self):
        bz = Bugzilla.get_bz()
        try:
            bug = bz.getbug(self.bz_id)
        except xmlrpclib.Fault, f:
            self.title = 'Invalid bug number'
            log.warning("Got fault from Bugzilla: %s" % str(f))
            return
        if bug.product == 'Security Response':
            self.parent = True
        self.title = str(bug.short_desc)
        if 'security' in bug.keywords.lower():
            self.security = True

    def _default_message(self, update):
        message = self.default_msg % (update.get_title(delim=', '), "%s %s" % 
                                   (update.release.long_name, update.status))
        if update.status == "testing":
            message += "\n If you want to test the update, you can install " + \
                       "it with \n su -c 'yum --enablerepo=updates-testing " + \
                       "update %s'" % (' '.join([build.package.name for build
                                                 in update.builds]))

        return message

    def add_comment(self, update, comment=None):
        bz = Bugzilla.get_bz()
        if not comment:
            comment = self._default_message(update)
        log.debug("Adding comment to Bug #%d: %s" % (self.bz_id, comment))
        try:
            bug = bz.getbug(self.bz_id)
            bug.addcomment(comment)
        except Exception, e:
            log.error("Unable to add comment to bug #%d\n%s" % (self.bz_id,
                                                                str(e)))

    def close_bug(self, update):
        me = config.get('bodhi_email')
        password = config.get('bodhi_password')
        if password:
            log.debug("Closing Bug #%d" % self.bz_id)
            ver = '-'.join(get_nvr(update.builds[0].nvr)[-2:])
            try:
                server = xmlrpclib.Server(self._bz_server)
                server.bugzilla.closeBug(self.bz_id, 'CURRENTRELEASE', me,
                                         password, 0, ver)
                del server
            except Exception, e:
                log.error("Cannot close bug #%d" % self.bz_id)
                log.exception(e)
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
