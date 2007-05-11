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
import logging
import xmlrpclib
import turbogears

from sqlobject import *
from datetime import datetime

from turbogears import config, flash
from turbogears.database import PackageHub

from os.path import isdir, isfile, join, basename
from bodhi.util import get_nvr, excluded_arch, rpm_fileheader, header
from bodhi.metadata import ExtendedMetadata
from bodhi.exceptions import RPMNotFound
from bodhi.identity.tables import *

log = logging.getLogger(__name__)
hub = PackageHub("bodhi")
__connection__ = hub

soClasses=('Release', 'Arch', 'Multilib', 'Package', 'PackageUpdate', 'CVE',
           'Bugzilla', 'Visit', 'VisitIdentity', 'User', 'Group', 'Permission',
           'Comment')

class Release(SQLObject):
    """ Table of releases that we will be pushing updates for """
    name        = UnicodeCol(alternateID=True, notNone=True)
    long_name   = UnicodeCol(notNone=True)
    updates     = MultipleJoin('PackageUpdate', joinColumn='release_id')
    arches      = RelatedJoin('Arch')
    multilib    = RelatedJoin('Multilib')
    repodir     = UnicodeCol(notNone=True)
    id_prefix   = UnicodeCol(notNone=True)

class Arch(SQLObject):
    """ Table of supported architectures """
    name            = UnicodeCol(alternateID=True, notNone=True)
    subarches       = PickleCol()
    releases        = RelatedJoin('Release')
    compatarches    = PickleCol(default=[])
    multilib        = RelatedJoin('Multilib')

class Multilib(SQLObject):
    """
    Table of multilib packages (ie x86_64 packages that need to pull down
    the i386 version as well).
    """
    package     = UnicodeCol(alternateID=True, notNone=True)
    releases    = RelatedJoin('Release')
    arches      = RelatedJoin('Arch')

class Package(SQLObject):
    name           = UnicodeCol(alternateID=True, notNone=True)
    updates        = MultipleJoin('PackageUpdate', joinColumn='package_id')
    suggest_reboot = BoolCol(default=False)

    def __str__(self):
        x = '[ %s ]' % self.name
        if len(self.updates):
            pending = filter(lambda u: not u.pushed, self.updates)
            if len(pending):
                x += "\n[ %d Pending Updates ]\n" % len(pending)
                for update in pending:
                    x += "  o %s\n" % update.nvr
            available = filter(lambda u: u.pushed, self.updates)
            if len(available):
                x += "\n[ %d Available Updates ]\n" % len(available)
                for update in available:
                    x += "  o %s\n" % update.nvr
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
    testing         = BoolCol(default=True)
    pushed          = BoolCol(default=False)
    notes           = UnicodeCol()
    mail_sent       = BoolCol(default=False)
    archived_mail   = UnicodeCol(default=None) # URL of archived update announce mail
    request         = EnumCol(enumValues=['push', 'unpush', 'move', None], default=None)
    comments        = MultipleJoin('Comment', joinColumn='update_id')
    filelist        = PickleCol(default={}) # { 'arch' : [file1, file2, ..] }

    ##
    ## On publictest2 this makes SQLObject explode (concurrency issues).
    ## TODO: figure out how to automatically build the filelist when a
    ## PackageUpdate is created (for now we'll just call _build_filelist by
    ## hand).
    ##
    #def _set_nvr(self, nvr):
    #    """
    #    Called when the a PackageUpdate is created. Here we do some
    #    initialization such as building the filelist
    #    """
    #    self._SO_set_nvr(nvr)
    #    if self.filelist == {}:
    #        self._build_filelist()

    def get_bugstring(self):
        """ Return a space-delimited string of bug numbers for this update """
        return ' '.join([str(bug.bz_id) for bug in self.bugs])

    def get_cvestring(self):
        """ Return a space-delimited string of CVE ids for this update """
        return ' '.join([cve.cve_id for cve in self.cves])

    def get_repo(self):
        """
        Return the relative path to the repository in which this update
        is to be pushed.  The absolute path can be created by prepending
        this value with the stage_dir and appending the architecture
        """
        return join(self.testing and 'testing' or '', self.release.repodir)

    def assign_id(self):
        """
        Assign an update ID to this update.  This function finds the next number
        in the sequence of pushed updates for this release, increments it and
        prefixes it with the id_prefix of the release and the year
        (ie FEDORA-2007-0001)
        """
        if self.update_id != None or self.update_id != u'None':
            log.debug("Keeping current update id %s" % self.update_id)
            return
        update = PackageUpdate.select(orderBy=PackageUpdate.q.update_id)
        try:
            id = int(update[0].update_id.split('-')[-1]) + 1
        except (AttributeError, IndexError):
            id = 1
        self.update_id = '%s-%s-%0.4d' % (self.release.id_prefix,
                                          time.localtime()[0],id)
        log.debug("Setting update_id for %s to %s" % (self.nvr, self.update_id))

    def _build_filelist(self):
        """ Build and store the filelist for this update. """
        log.debug("Building filelist for %s" % self.nvr)
        filelist = {}
        filelist['SRPMS'] = [self.get_srpm_path()]
        sourcepath = self.get_source_path()
        rpmheader = rpm_fileheader(filelist['SRPMS'][0])
        for arch in self.release.arches:
            filelist[arch.name] = []
            for subarch in arch.subarches:
                if subarch == 'noarch':
                    # Check for excluded/exclusive archs
                    if excluded_arch(rpmheader, arch.name):
                        log.debug("Excluding arch %s for %s" % (arch.name,
                                                                self.nvr))
                        continue
                path = join(sourcepath, subarch)
                if isdir(path):
                    for file in os.listdir(path):
                        filelist[arch.name].append(join(path, file))
                        log.debug(" * %s" % file)
            # Check for multilib packages
            for compatarch in arch.compatarches:
                path = join(sourcepath, compatarch)
                if isdir(path):
                    for file in os.listdir(path):
                        try:
                            nvr = get_nvr(basename(file))
                            multilib = Multilib.byPackage(nvr[:-2])
                            if arch in multilib.arches and \
                               self.release in multilib.releases:
                                filelist[arch.name].append(join(path, file))
                                log.debug(" * %s" % file)
                        except SQLObjectNotFound:
                            continue
                        except IndexError:
                            log.debug("Unknown file: %s" % file)
                            continue
        self.filelist = filelist

    def run_request(self, stage=None, updateinfo=None):
        """
        Based on the request property, do one of a few things:

              'push' : push this update's files to the updates stage
            'unpush' : remove this update's files from the updates stage
              'move' : move this packages files from testing to final

        By default we stage to the 'stage_dir' variable set in your app.cfg,
        but an alternate can be specified (for use in testing dep closure in
        a lookaside repo).

        If an optinal updateinfo is supplied, then this update will add/remove
        itself accordingly.  If not, then we will create our own and insert
        it before we return.
        """
        if updateinfo: uinfo = updateinfo
        else: uinfo = ExtendedMetadata(stage)
        if self.request == None:
            log.error("%s attempting to run None request" % self.nvr)
            return
        elif self.request == 'move':
            uinfo.remove_update(self)
            # disable testing status now so that we can simply push to
            # self.get_repo() later in this method
            self.testing = False

        action = {'move':'Moving', 'push':'Pushing', 'unpush':'Unpushing'}
        log.debug("%s %s" % (action[self.request], self.nvr))
        yield header("%s %s" % (action[self.request], self.nvr))

        # iterate over each of this update's files by arch
        for arch in self.filelist.keys():
            dest = join(stage and stage or config.get('stage_dir'),
                        self.get_repo(), arch)

            for file in self.filelist[arch]:
                filename = basename(file)
                if filename.find('debuginfo') != -1:
                    destfile = join(dest, 'debug', filename)
                else:
                    destfile = join(dest, filename)

                # regardless of request, delete any pushed files that exist
                if isfile(destfile):
                    log.debug("Deleting %s" % destfile)
                    os.unlink(destfile)
                    yield " * Removed %s" % join(self.get_repo(),arch,filename)

                if self.request == 'unpush':
                    # we've already removed any existing files from the stage,
                    # and unpushing doesn't entail anything more
                    continue
                elif self.request == 'push' or self.request == 'move':
                    log.debug("Pushing %s to %s" % (file, destfile))
                    yield " * %s" % join(self.get_repo(), arch, filename)
                    try:
                        os.link(file, destfile)
                    except OSError, e:
                        if e.errno == 18: # cross-device-link
                            log.debug("Cross-device link; copying file instead")
                            import shutil
                            shutil.copyfile(file, destfile)

        # Post-request actions
        # We only want to execute these when this update has been pushed to
        # our default stage.  If an alternate stage has been supplied (ie,
        # for dependency closure tests), we don't want to assign an official
        # update ID to this update, or send an notifications around.
        if not stage:
            if self.request == 'push':
                self.pushed = True
                self.date_pushed = datetime.now()
                self.assign_id()
                mail.send(self.submitter, 'pushed', self)
                uinfo.add_update(self)
            elif self.request == 'unpush':
                self.pushed = False
                self.testing = True
                mail.send(self.submitter, 'unpushed', self)
                uinfo.remove_update(self)
            elif self.request == 'move':
                self.pushed = True
                if self.update_id == None or self.update_id == u'None':
                    self.assign_id()
                mail.send(self.submitter, 'moved', self)
                uinfo.add_update(self)
                koji = xmlrpclib.ServerProxy(config.get('koji_hub'),
                                             allow_none=True)
                log.debug("Moving %s from dist-%s-updates-candidates to "
                          "dist-%s-updates" % (self.nvr,
                                               self.release.name.lower(),
                                               self.release.name.lower()))
                try:
                    koji.moveBuild('dist-%s-updates-candidate' %
                                   self.release.name.lower(),
                                   'dist-%s-updates' %
                                   self.release.name.lower(), self.nvr)
                except xmlrpclib.Fault, f:
                    log.error("ERROR: %s" % str(f))
                del koji

        # If we created our own UpdateMetadata, then insert it into the repo
        if not updateinfo:
            log.debug("Inserting updateinfo by hand")
            uinfo.insert_updateinfo()
            del uinfo

        self.request = None
        hub.commit()

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
        koji = xmlrpclib.ServerProxy(config.get('koji_hub'), allow_none=True)
        latest = None
        builds = []

        # Grab a list of builds tagged with dist-$RELEASE-updates, and find
        # the most recent update for this package, other than this one.  If
        # nothing is tagged for -updates, then grab the first thing in
        # dist-$RELEASE.  We aren't checking -updates-candidate first, because
        # there could potentially be packages that never make their way over
        # -updates, so we don't want to generate ChangeLogs against those.
        for tag in ['dist-%s-updates', 'dist-%s']:
            try:
                builds = koji.getLatestBuilds(tag % self.release.name.lower(),
                                              None, self.package.name)

                # Find the first build that is older than us
                for build in builds:
                    if rpm.labelCompare(get_nvr(self.nvr),
                                        get_nvr(build['nvr'])) > 0:
                        log.debug("%s > %s" % (self.nvr, build['nvr']))
                        latest = get_nvr(build['nvr'])
                        # break?
                if not latest:
                    continue
            except xmlrpclib.Fault, f:
                # Nothing built and tagged with -updates, so try dist instead
                log.warning(str(f))
                continue
            break

        del koji
        if not latest:
            return None

        latest = join(config.get('build_dir'), latest[0], latest[1], latest[2],
                      'src', '%s.src.rpm' % '-'.join(latest))

        if not isfile(latest):
            log.error("Cannot find latest-pkg: %s" % latest)
            latest = None

        return latest

    def get_path(self):
        """ Return the relative path to this update """
        status = self.testing and 'testing/' or ''
        if not self.pushed: status = 'pending/'
        return '/%s%s/%s' % (status, self.release.name, self.nvr)

    def get_url(self):
        return turbogears.url(self.get_path())

    def __str__(self):
        """
        Return a string representation of this update.
        TODO: eventually put the URL of this update
        """
        val = """\
================================================================================
  %(package)s
================================================================================
  Update ID: %(update_id)s
    Release: %(release)s
       Type: %(type)s
       Bugs: %(bugs)s
       CVES: %(cves)s
      Notes: %(notes)s
  Submitter: %(submitter)s
  Submitted: %(submitted)s
      Files:""" % ({
                    'update_id' : self.update_id,
                    'package'   : self.nvr,
                    'release'   : self.release.long_name,
                    'type'      : self.type,
                    'notes'     : self.notes,
                    'email'     : self.submitter,
                    'bugs'      : self.get_bugstring(),
                    'cves'      : self.get_cvestring(),
                    'submitted' : self.date_submitted,
                    'submitter' : self.submitter
                  })

        for files in self.filelist.values():
            for file in files:
                val += " %s\n\t    " % basename(file)
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
        header = self.get_rpm_header()
        descrip = header[rpm.RPMTAG_CHANGELOGTEXT]
        if not descrip: return ""

        who = header[rpm.RPMTAG_CHANGELOGNAME]
        when = header[rpm.RPMTAG_CHANGELOGTIME]

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
            me = User.by_user_name(config.get('from_address'))
            if not me.password:
                log.error("No password stored for %s" % me.user_name)
                return
            bug = server.bugzilla.getBug(self.bz_id, me.user_name, me.password)
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
        me = User.by_user_name(config.get('from_address'))
        server = xmlrpclib.Server(self._bz_server)
        server.bugzilla.addComment(self.bz_id, comment, me.user_name,
                                   me.password, 0)
        del server

    def _close_bug(self):
        pass

    def get_url(self):
        return "https://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=%s" % self.bz_id
