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
    #arches      = RelatedJoin('Arch')
    #multilib    = RelatedJoin('Multilib')
    #repodir     = UnicodeCol(notNone=True)

#class Arch(SQLObject):
#    """ Table of supported architectures """
#    name            = UnicodeCol(alternateID=True, notNone=True)
#    subarches       = PickleCol()
#    releases        = RelatedJoin('Release')
#    compatarches    = PickleCol(default=[])
#    multilib        = RelatedJoin('Multilib')

#class Multilib(SQLObject):
#    """
#    Table of multilib packages (ie x86_64 packages that need to pull down
#    the i386 version as well).
#    """
#    package     = UnicodeCol(alternateID=True, notNone=True)
#    releases    = RelatedJoin('Release')
#    arches      = RelatedJoin('Arch')

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

    def get_bugstring(self):
        """ Return a space-delimited string of bug numbers for this update """
        return ' '.join([str(bug.bz_id) for bug in self.bugs])

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

#    def run_request(self, stage=None, updateinfo=None):
#        """
#        Based on the request property, do one of a few things:
#
#              'push' : push this update's files to the updates stage
#            'unpush' : remove this update's files from the updates stage
#              'move' : move this packages files from testing to final
#
#        By default we stage to the 'stage_dir' variable set in your app.cfg,
#        but an alternate can be specified (for use in testing dep closure in
#        a lookaside repo).
#
#        If an optinal updateinfo is supplied, then this update will add/remove
#        itself accordingly.  If not, then we will create our own and insert
#        it before we return.
#        """
#        if not stage: stage = config.get('stage_dir')
#        if updateinfo: uinfo = updateinfo
#        else: uinfo = ExtendedMetadata(stage)
#        if self.request == None:
#            log.error("%s attempting to run None request" % self.nvr)
#            return
#        elif self.request == 'move':
#            uinfo.remove_update(self)
#
#        action = {'move':'Moving', 'push':'Pushing', 'unpush':'Unpushing'}
#        yield header("%s %s" % (action[self.request], self.nvr))
#
#        # iterate over each of this update's files by arch
#        for arch in self.filelist.keys():
#            dest = join(stage, self.get_dest_repo(), arch)
#
#            for pkg in self.filelist[arch]:
#                filename = basename(pkg)
#                if filename.find('debuginfo') != -1:
#                    destfile = join(dest, 'debug', filename)
#                    current_file = join(stage, self.get_repo(), arch,
#                                        'debug', filename)
#                else:
#                    destfile = join(dest, filename)
#                    current_file = join(stage, self.get_repo(), arch, filename)
#
#                # regardless of request, delete any pushed files that exist
#                for pushed_file in (current_file, destfile):
#                    if isfile(pushed_file):
#                        os.unlink(pushed_file)
#                        yield " * Removed %s" % pushed_file.split(stage)[-1][1:]
#
#                if self.request == 'unpush':
#                    # we've already removed any existing files from the stage,
#                    # and unpushing doesn't entail anything more
#                    continue
#                elif self.request in ('push', 'move'):
#                    yield " * %s" % destfile.split(stage)[-1][1:]
#                    try:
#                        os.link(pkg, destfile)
#                    except OSError, e:
#                        if e.errno == 18: # cross-device-link
#                            log.debug("Cross-device link; copying file instead")
#                            shutil.copyfile(pkg, destfile)
#
#        # Post-request actions
#        if self.request == 'push':
#            self.pushed = True
#            self.date_pushed = datetime.now()
#            self.assign_id()
#            yield " * Assigned ID %s" % self.update_id
#            yield " * Generating extended metadata"
#            uinfo.add_update(self)
#            yield " * Notifying %s" % self.submitter
#            mail.send(self.submitter, 'pushed', self)
#        elif self.request == 'unpush':
#            mail.send(self.submitter, 'unpushed', self)
#            if uinfo.remove_update(self):
#                yield " * Removed extended metadata from updateinfo"
#            else:
#                yield " * Unable to remove extended metadata from updateinfo"
#            self.pushed = False
#            self.status = 'testing'
#        elif self.request == 'move':
#            self.pushed = True
#            self.status = 'stable'
#            self.assign_id()
#            yield " * Notifying %s" % self.submitter
#            mail.send(self.submitter, 'moved', self)
#            yield " * Generating extended metadata"
#            uinfo.add_update(self)
#            koji_session = buildsys.get_session()
#            log.debug("Moving %s from %s-updates-candidates to "
#                      "%s-updates" % (self.nvr, self.release.dist_tag,
#                                      self.release.dist_tag))
#            koji_session.moveBuild('%s-updates-candidate' %
#                                   self.release.dist_tag,
#                                   '%s-updates' %
#                                   self.release.dist_tag, self.nvr)
#
#        # If we created our own UpdateMetadata, then insert it into the repo
#        if not updateinfo:
#            log.debug("Inserting updateinfo by hand")
#            uinfo.insert_updateinfo()
#            del uinfo
#
#        self.request = None
#        hub.commit()

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
            #uinfo.add_update(self)

        log.info("%s request on %s complete!" % (self.request, self.nvr))
        self.request = None
        hub.commit()

    def send_update_notice(self):
        log.debug("Sending update notice for %s" % self.nvr)
        import turbomail
        list = None
        if self.status == 'stable':
            list = config.get('%s_announce_list' %
                              self.release.id_prefix.lower())
        elif self.status == 'testing':
            list = config.get('%s_test_announce_list' %
                              self.release.id_prefix.lower())
        if list:
            (subject, body) = mail.get_template(self)
            bodhi = config.get('bodhi_email')
            if not bodhi:
                log.warning("bodhi_email not defined in app.cfg; unable to "
                            "send update notice")
                return
            message = turbomail.Message(bodhi, list, subject)
            message.plain = body
            try:
                turbomail.enqueue(message)
                log.debug("Sending mail: %s" % message.plain)
                self.mail_sent = True
            except turbomail.MailNotEnabledException:
                log.warning("TurboMail is not enabled!")

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
        val = """\
================================================================================
  %s
================================================================================
""" % self.nvr
        if self.update_id:
            val += "  Update ID: %s\n" % self.update_id
        val += """    Release: %s
     Status: %s
       Type: %s""" % (self.release.long_name, self.status, self.type)
        if self.request != None:
            val += "\n    Request: %s" % self.request
        if len(self.bugs):
           val += "\n       Bugs: %s" % self.get_bugstring()
        if len(self.cves):
            val += "\n       CVES: %s" % self.get_cvestring()
        if self.notes:
            val += "\n      Notes: %s" % self.notes
        val += """
  Submitter: %s
  Submitted: %s
        """ % (self.submitter, self.date_submitted)
        #for files in self.filelist.values():
        #    for file in files:
        #        val += " %s\n\t    " % basename(file)
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
    _default_closemsg = "%(package)s has been released for %(release)s.  " + \
                        "If problems still persist, please make note of it " + \
                        "in this bug report."

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

    def _add_comment(self, comment):
        me = config.get('bodhi_email')
        password = config.get('bodhi_password', None)
        if password:
            server = xmlrpclib.Server(self._bz_server)
            server.bugzilla.addComment(self.bz_id, comment, me, password, 0)
            del server

    def _close_bug(self):
        """ TODO """
        pass

    def get_url(self):
        return "https://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=%s" % self.bz_id
