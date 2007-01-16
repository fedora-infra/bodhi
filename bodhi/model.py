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

import logging

from sqlobject import *
from datetime import datetime

from turbogears import identity, config, flash
from turbogears.database import PackageHub

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
    repo        = UnicodeCol(notNone=True)
    testrepo    = UnicodeCol(notNone=True)

class Arch(SQLObject):
    name            = UnicodeCol(alternateID=True, notNone=True)
    subarches       = PickleCol()
    releases        = RelatedJoin('Release')
    compatarches    = PickleCol(default=[])
    multilib        = RelatedJoin('Multilib')

class Multilib(SQLObject):
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
    testing         = BoolCol()
    pushed          = BoolCol(default=False)
    date_pushed     = DateTimeCol(default=None)
    notes           = UnicodeCol()
    mail_sent       = BoolCol(default=False)
    #close_bugs      = BoolCol(default=False)
    archived_mail   = UnicodeCol(default=None)
    needs_push      = BoolCol(default=False)
    needs_unpush    = BoolCol(default=False)
    comments        = MultipleJoin('Comment', joinColumn='update_id')

    ## TODO: create File table ?
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
        return ' '.join([str(bug.bz_id) for bug in self.bugs])

    def get_cvestring(self):
        return ' '.join([cve.cve_id for cve in self.cves])

    def get_repo(self):
        return self.testing and self.release.testrepo or self.release.repo

    def assign_id(self):
        """
        Assign an update ID to this update.  This function finds the next number in the
        sequence of pushed updates for this release, increments it and prefixes it
        with 'prefix_id' (configurable in app.cfg) and the year (ie FEDORA-2007-0001)
        """
        import time
        if self.update_id != None: # maintain assigned ID for repushes
            return
        update = PackageUpdate.select(orderBy=PackageUpdate.q.update_id).reversed()
        try:
            id = int(update[0].update_id.split('-')[-1]) + 1
        except AttributeError: # no other updates; this is the first
            id = 1
        self.update_id = '%s-%s-%0.4d' % (config.get('id_prefix'),time.localtime()[0],id)
        log.debug("Setting update_id for %s to %s" % (self.nvr, self.update_id))

    def _build_filelist(self):
        """ Build and store the filelist for this update. """
        import os, util
        from os.path import isdir, join, basename
        from buildsys import buildsys
        log.debug("Building filelist for %s" % self.nvr)
        filelist = {}
        filelist['SRPMS'] = [buildsys.get_srpm_path(self)]
        sourcepath = buildsys.get_source_path(self)
        for arch in self.release.arches:
            filelist[arch.name] = []
            for subarch in arch.subarches:
                path = join(sourcepath, subarch)
                if isdir(path):
                    for file in os.listdir(path):
                        filelist[arch.name].append(join(path, file))
                        log.debug(" * %s" % file)
            ## Check for multilib packages
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

#class Comment(SQLObject):
#    """ Table of comments on updates. """
#    update  = ForeignKey('PackageUpdate', notNone=True)
#    user    = UnicodeCol(notNone=True)
#    text    = UnicodeCol(notNone=True)

class CVE(SQLObject):
    """ Table of CVEs fixed within updates that we know of. """
    cve_id  = UnicodeCol(alternateID=True, notNone=True)
    updates = RelatedJoin("PackageUpdate")

class Bugzilla(SQLObject):
    """ Table of Bugzillas that we know about. """
    bz_id    = IntCol(alternateID=True)
    title    = UnicodeCol(default=None)
    updates  = RelatedJoin("PackageUpdate")
    security = BoolCol(default=False)

    _bz_server = config.get("bz_server")
    _default_closemsg = "%(package)s has been released for %(release)s.  If problems still persist, please make note of it in this bug report."

    def _set_bz_id(self, bz_id):
        """
        When the ID for this bug is set (upon creation), go out and fetch the details
        and check if this bug is security related.
        """
        self._SO_set_bz_id(bz_id)
        self._fetch_details()

    def _fetch_details(self):
        import xmlrpclib
        try:
            log.debug("Fetching bugzilla title for bug #%d" % self.bz_id)
            server = xmlrpclib.Server(self._bz_server)
            me = User.by_user_name(config.get('from_address'))
            bug = server.bugzilla.getBug(self.bz_id, me.user_name, me.password)
            del server
            self.title = bug['short_desc']
            if bug['keywords'].lower().find('security') != -1:
                self.security = True
        except Exception, e:
            log.error("Unable to fetch Bugzilla title")
            raise e

    def _add_comment(self, comment):
        me = User.by_user_name(config.get('from_address'))
        server = xmlrpclib.Server(self._bz_server)
        server.bugzilla.addComment(self.bz_id, comment, me.user_name, me.password, 0)
        del server
        pass

    def _close_bug(self):
        pass

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

##
## Updates System Initialization
##

def init_updates_stage():
    """ Initialize the updates-stage """

    stage_dir = config.get('stage_dir')
    print "\nInitializing the staging directory"

    def mkmetadatadir(dir):
        print dir
        os.mkdir(dir)
        genpkgmetadata.main(['-q', str(dir)])

    if isdir(stage_dir):
        import shutil
        olddir = stage_dir + '.old'
        if isdir(olddir):
            shutil.rmtree(olddir)
        print "Moving existing stage_dir to stage_dir.old"
        shutil.move(stage_dir, olddir)

    os.mkdir(stage_dir)
    os.mkdir(join(stage_dir, 'testing'))
    for release in Release.select():
        for status in ('', 'testing'):
            dir = join(stage_dir, status, release.name)
            os.mkdir(dir)
            mkmetadatadir(join(dir, 'SRPMS'))
            for arch in release.arches:
                mkmetadatadir(join(dir, arch.name))
                mkmetadatadir(join(dir, arch.name, 'debug'))

def import_releases():
    """ Import the releases and multilib  """

    print "\nInitializing Release table and multilib packages..."

    releases = (
        {
            'name'      : 'FC7',
            'long_name' : 'Fedora Core 7',
            'arches'    : map(Arch.byName, ('i386', 'x86_64', 'ppc')),
            'repo'      : join(config.get('stage_dir'), 'FC7'),
            'testrepo'  : join(config.get('stage_dir'), 'testing', 'FC7')
        },
        {
            'name'      : 'FC6',
            'long_name' : 'Fedora Core 6',
            'arches'    : map(Arch.byName, ('i386', 'x86_64', 'ppc')),
            'repo'      : join(config.get('stage_dir'), 'FC6'),
            'testrepo'  : join(config.get('stage_dir'), 'testing', 'FC6')
        },
        {
            'name'      : 'FC5',
            'long_name' : 'Fedora Core 5',
            'arches'    : map(Arch.byName, ('i386', 'x86_64', 'ppc')),
            'repo'      : join(config.get('stage_dir'), 'FC5'),
            'testrepo'  : join(config.get('stage_dir'), 'testing', 'FC5')
        },
        {
            'name'      : 'EPEL5',
            'long_name' : 'EPEL5 Enterprise Extras',
            'arches'    : map(Arch.byName, ('i386', 'x86_64', 'ppc')),
            'repo'      : join(config.get('stage_dir'), 'EPEL5'),
            'testrepo'  : join(config.get('stage_dir'), 'testing', 'EPEL5')
        }
    )

    for release in releases:
        num_multilib = 0
        rel = Release(name=release['name'], long_name=release['long_name'],
                      repo=release['repo'], testrepo=release['testrepo'])
        map(rel.addArch, release['arches'])
        for arch in biarch.keys():
            if not biarch[arch].has_key(release['name'][-1]):
                continue
            for pkg in biarch[arch][release['name'][-1]]:
                try:
                    multilib = Multilib.byPackage(pkg)
                    num_multilib += 1
                except SQLObjectNotFound:
                    multilib = Multilib(package=pkg)
                multilib.addRelease(rel)
                multilib.addArch(Arch.byName(arch))
        print rel
        print " - Added %d multilib packages for %s" % (num_multilib, rel.name)

def init_arches():
    """ Initialize the arch tables """
    arches = {
            # arch        subarches
            'i386'      : ['i386', 'i486', 'i586', 'i686', 'athlon', 'noarch'],
            'x86_64'    : ['x86_64', 'ia32e', 'noarch'],
            'ppc'       : ['ppc', 'noarch']
    }

    biarches = {
            # arch        compatarches
            'i386'      : [],
            'x86_64'    : ['i386', 'i486', 'i586', 'i686', 'athlon'],
            'ppc'       : ['ppc64', 'ppc64iseries']
    }

    print "Initializing Arch tables..."
    for arch in arches.keys():
        a = Arch(name=arch, subarches=arches[arch], compatarches=biarches[arch])
        print a

def clean_tables():
    Release.dropTable(ifExists=True, cascade=True)
    Package.dropTable(ifExists=True, cascade=True)
    Arch.dropTable(ifExists=True, cascade=True)
    Group.dropTable(ifExists=True, cascade=True)
    Multilib.dropTable(ifExists=True, cascade=True)
    hub.commit()
    Release.createTable(ifNotExists=True)
    Package.createTable(ifNotExists=True)
    Arch.createTable(ifNotExists=True)
    Multilib.createTable(ifNotExists=True)
    Group.createTable(ifNotExists=True)

def load_config():
    """ Load the appropriate configuration so we can get at the values """
    configfile = 'dev.cfg'
    if not isfile(configfile):
        configfile = 'prod.cfg'
    turbogears.update_config(configfile=configfile,
                             modulename='bodhi.config')

##
## Initialize the package/release/multilib tables
##
if __name__ == '__main__':
    import os
    import sys
    import turbogears
    from os.path import join, isdir, isfile
    from deprecated.biarch import biarch
    from turbogears import config
    sys.path.append('/usr/share/createrepo')
    import genpkgmetadata

    load_config()
    hub.begin()
    clean_tables()
    init_arches()
    import_releases()
    init_updates_stage()

    ##
    ## Create the admin group
    ##
    print "\nCreating admin group"
    admin = Group(display_name='Administrators', group_name='admin')
    print admin

    # TODO: this flips shit; find out why.
    #print "\nCreating my own identity"
    #me = User(user_name='updatesys')
    #print me

    hub.commit()
