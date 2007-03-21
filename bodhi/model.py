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
import mail
import logging

from sqlobject import *
from datetime import datetime

from turbogears import identity, config, flash
from turbogears.database import PackageHub

from os.path import isdir, isfile, join, basename

log = logging.getLogger(__name__)
hub = PackageHub("bodhi")
__connection__ = hub

soClasses=('Release', 'Arch', 'Multilib', 'Package', 'PackageUpdate', 'CVE',
           'Bugzilla', 'Visit', 'VisitIdentity', 'User', 'Group', 'Permission')

class Release(SQLObject):
    """ Table of releases that we will be pushing updates for """
    name        = UnicodeCol(alternateID=True, notNone=True)
    long_name   = UnicodeCol(notNone=True)
    updates     = MultipleJoin('PackageUpdate', joinColumn='release_id')
    arches      = RelatedJoin('Arch')
    multilib    = RelatedJoin('Multilib')
    repodir     = UnicodeCol(notNone=True)

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
    name    = UnicodeCol(alternateID=True, notNone=True)
    updates = MultipleJoin('PackageUpdate', joinColumn='package_id')

class PackageUpdate(SQLObject):
    """ This class defines an update in our system. """
    nvr             = UnicodeCol(notNone=True, alternateID=True, unique=True)
    date_submitted  = DateTimeCol(default=datetime.now, notNone=True)
    date_modified   = DateTimeCol(default=None)
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
    date_pushed     = DateTimeCol(default=None)
    notes           = UnicodeCol()
    mail_sent       = BoolCol(default=False)
    archived_mail   = UnicodeCol(default=None) # URL of archived update announce mail
    request         = EnumCol(enumValues=['push', 'unpush', 'move', None], default=None)
    comments        = MultipleJoin('Comment')
    filelist        = PickleCol(default={}) # { 'arch' : [file1, file2, ..] }

    def _set_nvr(self, nvr):
        """
        Called when the a PackageUpdate is created. Here we do some
        initialization such as building the filelist
        """
        self._SO_set_nvr(nvr)
        if self.filelist == {}:
            self._build_filelist()

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
        prefixes it with 'prefix_id' (configurable in app.cfg) and the year
        (ie FEDORA-2007-0001)
        """
        import time
        if self.update_id != None: # maintain assigned ID for repushes
            return
        update = PackageUpdate.select(orderBy=PackageUpdate.q.update_id)
        try:
            id = int(update.reversed()[0].update_id.split('-')[-1]) + 1
        except AttributeError: # no other updates; this is the first
            id = 1
        self.update_id = '%s-%s-%0.4d' % (config.get('id_prefix'),
                                          time.localtime()[0],id)
        log.debug("Setting update_id for %s to %s" % (self.nvr, self.update_id))

    def _build_filelist(self):
        """Build and store the filelist for this update. """
        import util
        from buildsys import buildsys
        log.debug("Building filelist for %s" % self.nvr)
        filelist = {}
        filelist['SRPMS'] = [buildsys.get_srpm_path(self)]
        sourcepath = buildsys.get_source_path(self)
        rpmheader = util.rpm_fileheader(filelist['SRPMS'][0])
        for arch in self.release.arches:
            filelist[arch.name] = []
            for subarch in arch.subarches:
                if subarch == 'noarch':
                    # Check for excluded/exclusive archs
                    if util.excluded_arch(rpmheader, arch.name):
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
                            nvr = util.get_nvr(basename(file))
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

    def run_request(self, stage=None):
        """
        Based on the request property, do one of a few things:

              'push' : push this update's files to the updates stage
            'unpush' : remove this update's files from the updates stage
              'move' : move this packages files from testing to final

        By default we stage to the 'stage_dir' variable set in your app.cfg,
        but an alternate can be specified (for use in testing dep closure in
        a lookaside repo)
        """
        if self.request == None:
            log.error("%s attempting to run None request" % self.nvr)
            return

        log.debug("Running %s request for %s" % (self.request, self.nvr))

        # iterate over each of this update's files by arch
        for arch in self.filelist.keys():
            dest = join(stage and stage or config.get('stage_dir'),
                        self.get_repo(), arch)
            log.debug("Pushing %s packages to %s" % (arch, dest))
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
                    yield "Removed %s" % join(self.get_repo(), arch, filename)

                if self.request == 'unpush':
                    # we've already removed any existing files from the stage,
                    # and unpushing doesn't entail anything more
                    continue

                elif self.request == 'push' or self.request == 'move':
                    log.debug("Pushing %s to %s" % (file, destfile))
                    yield " * %s" % join(self.get_repo(), arch, filename)
                    os.link(file, destfile)

        # post-request actions
        if self.request == 'push':
            self.pushed = True
            self.assign_id()
            mail.send(self.submitter, 'pushed', self)
        elif self.request == 'unpush':
            self.pushed = False
            mail.send(self.submitter, 'unpushed', self)
        elif self.request == 'move':
            mail.send(self.submitter, 'moved', self)
        self.request = None

    def __str__(self):
        """
        Return a string representation of this update.
        TODO: eventually put the URL of this update
        """
        val = """\
    Package: %(package)s
       Type: %(type)s
       Bugs: %(bugs)s
       CVES: %(cves)s
      Notes: %(notes)s
      Files:\n""" % ({
                    'package'   : self.nvr,
                    'type'      : self.type,
                    'notes'     : self.notes,
                    'email'     : self.submitter,
                    'bugs'      : self.get_bugstring(),
                    'cves'      : self.get_cvestring()
              })

        for files in self.filelist.values():
            for file in files:
                val += "\t     %s\n" % basename(file)
        return val.rstrip()

class Comment(SQLObject):
    """ Table of comments on updates. """
    update  = ForeignKey('PackageUpdate')
    user    = ForeignKey('User')
    text    = UnicodeCol(notNone=True)

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
        import xmlrpclib
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

##
## Identity tables
##

class Visit(SQLObject):
    visit_key = StringCol(length=40, alternateID=True,
                          alternateMethodName="by_visit_key")
    created = DateTimeCol(default=datetime.now)
    expiry = DateTimeCol()

    def lookup_visit(cls, visit_key):
        try:
            return cls.by_visit_key(visit_key)
        except SQLObjectNotFound:
            return None
    lookup_visit = classmethod(lookup_visit)

class VisitIdentity(SQLObject):
    visit_key = StringCol(length=40, alternateID=True,
                          alternateMethodName="by_visit_key")
    user_id = IntCol()

class Group(SQLObject):
    class sqlmeta:
        table = "tg_group"

    group_name = UnicodeCol(length=16, alternateID=True,
                            alternateMethodName="by_group_name")
    display_name = UnicodeCol(length=255)
    created = DateTimeCol(default=datetime.now)
    users = RelatedJoin("User", intermediateTable="user_group",
                        joinColumn="group_id", otherColumn="user_id")
    permissions = RelatedJoin("Permission", joinColumn="group_id", 
                              intermediateTable="group_permission",
                              otherColumn="permission_id")

class User(SQLObject):
    class sqlmeta:
        table = "tg_user"

    user_name = UnicodeCol(length=16, alternateID=True,
                           alternateMethodName="by_user_name")
    password = UnicodeCol(length=40, default=None)
    groups = RelatedJoin("Group", intermediateTable="user_group",
                         joinColumn="user_id", otherColumn="group_id")
    created = DateTimeCol(default=datetime.now)

    def _get_permissions(self):
        perms = set()
        for g in self.groups:
            perms = perms | set(g.permissions)
        return perms

    def _set_password(self, cleartext_password):
        "Runs cleartext_password through the hash algorithm before saving."
        hash = identity.encrypt_password(cleartext_password)
        self._SO_set_password(hash)

    def set_password_raw(self, password):
        "Saves the password as-is to the database."
        self._SO_set_password(password)

class Permission(SQLObject):
    permission_name = UnicodeCol(length=16, alternateID=True,
                                 alternateMethodName="by_permission_name")
    description = UnicodeCol(length=255)

    groups = RelatedJoin("Group",
                         intermediateTable="group_permission",
                         joinColumn="permission_id", 
                         otherColumn="group_id")
