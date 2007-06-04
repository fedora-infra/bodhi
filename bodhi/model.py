#!/usr/bin/python -tt
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
import mail
import time
import shutil
import logging
import xmlrpclib
import turbogears

from sqlobject import *
from datetime import datetime

from turbogears import config, flash
from turbogears.database import PackageHub

from os.path import isdir, isfile, join, basename
from textwrap import wrap

from bodhi import buildsys
from bodhi.util import get_nvr, excluded_arch, rpm_fileheader, header
from bodhi.metadata import ExtendedMetadata
from bodhi.exceptions import RPMNotFound
from bodhi.identity.tables import *

log = logging.getLogger(__name__)
hub = PackageHub("bodhi")
__connection__ = hub

soClasses=('Release', 'Package', 'PackageUpdate', 'CVE', 'Bugzilla', 'Comment')

class Release(SQLObject):
    """ Table of releases that we will be pushing updates for """
    name        = UnicodeCol(alternateID=True, notNone=True)
    long_name   = UnicodeCol(notNone=True)
    updates     = MultipleJoin('PackageUpdate', joinColumn='release_id')
    id_prefix   = UnicodeCol(notNone=True)
    dist_tag    = UnicodeCol(notNone=True) # ie dist-fc7

class Package(SQLObject):
    name           = UnicodeCol(alternateID=True, notNone=True)
    updates        = MultipleJoin('PackageUpdate', joinColumn='package_id')
    suggest_reboot = BoolCol(default=False)

    def __str__(self):
        x = header(self.name)
        if len(self.updates):
            pending = filter(lambda u: not u.pushed, self.updates)
            if len(pending):
                x += "\n  Pending Updates (%d) \n" % len(pending)
                for update in pending:
                    x += "    o %s\n" % update.nvr
            available = filter(lambda u: u.pushed, self.updates)
            if len(available):
                x += "\n  Available Updates (%d)\n" % len(available)
                for update in available:
                    x += "    o %s\n" % update.nvr
        return x

class PackageUpdate(SQLObject):
    """ This class defines an update in our system. """
    nvr             = UnicodeCol(notNone=True, alternateID=True, unique=True)
    date_submitted  = DateTimeCol(default=datetime.now, notNone=True)
    date_modified   = DateTimeCol(default=None)
    date_pushed     = DateTimeCol(default=None)
    package         = ForeignKey('Package')
    submitter       = UnicodeCol(notNone=True)
    update_id       = UnicodeCol(default=None)
    type            = EnumCol(enumValues=['security', 'bugfix', 'enhancement'])
    embargo         = DateTimeCol(default=None)
    cves            = RelatedJoin("CVE")
    bugs            = RelatedJoin("Bugzilla")
    release         = ForeignKey('Release')
    status          = EnumCol(enumValues=['pending', 'testing', 'stable'],
                              default='pending')
    pushed          = BoolCol(default=False)
    notes           = UnicodeCol()
    mail_sent       = BoolCol(default=False)
    request         = EnumCol(enumValues=['push', 'unpush', 'move', None],
                              default=None)
    comments        = MultipleJoin('Comment', joinColumn='update_id')

    def get_bugstring(self, show_titles=False):
        """ Return a space-delimited string of bug numbers for this update """
        val = ''
        if show_titles:
            i = 0
            for bug in self.bugs:
                val += '%s%s - %s\n' % (i and ' ' * 11 + ': ' or '',
                                        bug.bz_id, bug.title)
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
        log.debug("Setting update_id for %s to %s" % (self.nvr, self.update_id))
        hub.commit()

    def request_complete(self):
        """
        Perform post-request actions.
        """
        if self.request == 'push':
            self.pushed = True
            self.date_pushed = datetime.now()
            self.status = 'testing'
            self.assign_id()
            #uinfo.add_update(self)
            self.send_update_notice()
            map(lambda bug: bug.add_comment(self), self.bugs)
            mail.send(self.submitter, 'pushed', self)
        elif self.request == 'unpush':
            mail.send(self.submitter, 'unpushed', self)
            #uinfo.remove_update(self):
            self.pushed = False
            self.status = 'pending'
        elif self.request == 'move':
            self.pushed = True
            self.date_pushed = datetime.now()
            self.status = 'stable'
            self.assign_id()
            mail.send(self.submitter, 'moved', self)
            self.send_update_notice()
            map(lambda bug: bug.add_comment(self), self.bugs)
            map(lambda bug: bug.close_bug(self), self.bugs)
            #uinfo.add_update(self)

        log.info("%s request on %s complete!" % (self.request, self.nvr))
        self.request = None
        hub.commit()

    def send_update_notice(self):
        log.debug("Sending update notice for %s" % self.nvr)
        import turbomail
        list = None
        sender = config.get('notice_sender')
        if not sender:
            log.error("notice_sender not defined in configuration!  Unable " +
                      "to send update notice")
            return
        if self.status == 'stable':
            list = config.get('%s_announce_list' %
                              self.release.id_prefix.lower())
        elif self.status == 'testing':
            list = config.get('%s_test_announce_list' %
                              self.release.id_prefix.lower())
        if list:
            (subject, body) = mail.get_template(self)
            message = turbomail.Message(sender, list, subject)
            message.plain = body
            try:
                turbomail.enqueue(message)
                log.debug("Sending mail: %s" % message.plain)
                self.mail_sent = True
            except turbomail.MailNotEnabledException:
                log.warning("TurboMail is not enabled!")
        else:
            log.error("Cannot find mailing list address for update notice")

    def get_source_path(self):
        """ Return the path of this built update """
        return join(config.get('build_dir'), *get_nvr(self.nvr))

    def get_srpm_path(self):
        """ Return the path to the SRPM for this update """
        srpm = join(self.get_source_path(), "src", "%s.src.rpm" % self.nvr)
        if not isfile(srpm):
            log.debug("Cannot find SRPM: %s" % srpm)
            raise RPMNotFound
        return srpm

    def get_latest(self):
        """
        Return the path to the last released srpm of this package
        """
        latest = None
        builds = []
        koji_session = buildsys.get_session()

        # Grab a list of builds tagged with dist-$RELEASE-updates, and find
        # the most recent update for this package, other than this one.  If
        # nothing is tagged for -updates, then grab the first thing in
        # dist-$RELEASE.  We aren't checking -updates-candidate first, because
        # there could potentially be packages that never make their way over
        # -updates, so we don't want to generate ChangeLogs against those.
        for tag in ['%s-updates', '%s']:
            builds = koji_session.getLatestBuilds(tag % self.release.dist_tag,
                                                  None, self.package.name)

            # Find the first build that is older than us
            for build in builds:
                if rpm.labelCompare(get_nvr(self.nvr),
                                    get_nvr(build['nvr'])) > 0:
                    log.debug("%s > %s" % (self.nvr, build['nvr']))
                    latest = get_nvr(build['nvr'])
                    break
            if not latest:
                continue

        if not latest:
            return None

        latest = join(config.get('build_dir'), latest[0], latest[1], latest[2],
                      'src', '%s.src.rpm' % '-'.join(latest))

        if not isfile(latest):
            log.error("Cannot find latest-pkg: %s" % latest)
            latest = None

        return latest

    def get_url(self):
        """ Return the relative URL to this update """
        status = self.status == 'testing' and 'testing/' or ''
        if not self.pushed: status = 'pending/'
        return '/%s%s/%s' % (status, self.release.name, self.nvr)

    def __str__(self):
        """
        Return a string representation of this update.
        """
        val = "%s\n  %s\n%s\n" % ('=' * 80, self.nvr, '=' * 80)
        if self.update_id:
            val += "  Update ID: %s\n" % self.update_id
        val += """    Release: %s
     Status: %s
       Type: %s""" % (self.release.long_name, self.status, self.type)
        if self.request != None:
            val += "\n    Request: %s" % self.request
        if len(self.bugs):
           val += "\n       Bugs: %s" % self.get_bugstring(show_titles=True)
        if len(self.cves):
            val += "\n       CVEs: %s" % self.get_cvestring()
        if self.notes:
            val += "\n      Notes: %s" % self.notes
        val += """
  Submitter: %s
  Submitted: %s
        """ % (self.submitter, self.date_submitted)
        return val.rstrip()

    def get_rpm_header(self):
        """
        Get the rpm header of this update
        """
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
                log.debug("Removing CVE %s from %s" % (cve.cve_id, self.nvr))
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

class Comment(SQLObject):
    timestamp   = DateTimeCol(default=datetime.now)
    update      = ForeignKey("PackageUpdate", notNone=True)
    author      = UnicodeCol(notNone=True)
    text        = UnicodeCol(notNone=True)

    def __str__(self):
        return "%s - %s\n%s" % (self.author, self.timestamp, self.text)

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
        try:
            log.debug("Fetching bugzilla #%d" % self.bz_id)
            server = xmlrpclib.Server(self._bz_server)
            me = config.get('bodhi_email')
            password = config.get('bodhi_password')
            if not password:
                log.error("No password stored for %s" % me)
                return
            bug = server.bugzilla.getBug(self.bz_id, me, password)
            del server
            self.title = bug['short_desc']
            if bug['keywords'].lower().find('security') != -1:
                self.security = True
        except xmlrpclib.Fault:
            self.title = 'Invalid bug number'
        except Exception, e:
            self.title = 'Unable to fetch bug title'
            log.error(self.title)

    def default_message(self, update):
        return self.default_msg % (update.nvr, "%s %s" % 
                                   (update.release.long_name, update.status))

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
            except Exception, e:
                log.error("Unable to add comment to bug #s\n%s" % (self.bz_id,
                                                                   str(e)))
            del server
        else:
            log.warning("bodhi_password not defined; unable to modify bug")

    def close_bug(self, update):
        me = config.get('bodhi_email')
        password = config.get('bodhi_password')
        if password:
            log.debug("Closing Bug #%d" % self.bz_id)
            ver = get_nvr(update.nvr)[-2]
            try:
                server = xmlrpclib.Server(self._bz_server)
                server.bugzilla.closeBug(self.bz_id, 'NEXTRELEASE', me,
                                         password, 0, ver)
            except Exception, e:
                log.error("Cannot close bug #%d" % self.bz_id)
        else:
            log.warning("bodhi_password not defined; unable to close bug")

    def get_url(self):
        return "https://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=%s" % self.bz_id
