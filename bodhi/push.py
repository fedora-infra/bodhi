# $Id: push.py,v 1.5 2007/01/08 06:07:07 lmacken Exp $
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
import shutil
import logging
import tempfile
import cherrypy

from Comet import comet
from model import PackageUpdate
from buildsys import buildsys
from datetime import datetime
from metadata import ExtendedMetadata
from modifyrepo import RepoMetadata
from turbogears import controllers, expose, flash, redirect, config, identity

from os.path import isfile, isdir, basename, join

import sys
sys.path.append('/usr/share/createrepo')
import genpkgmetadata

log = logging.getLogger(__name__)

class RepositoryLocked(Exception):
    pass

class PushController(controllers.Controller):

    def __init__(self):
        self.createrepo_cache = config.get('createrepo_cache_dir')
        self.stage_dir = config.get('stage_dir')
        self.lockfile = join(self.stage_dir, '.lock')
        self.header = lambda x: "%s\n%s\n%s" % ('=' * 100, x, '=' * 100)
        if isfile(self.lockfile):
            log.debug("Removing stale repository lockfile")
            self._unlock_repo()

    def _lock_repo(self):
        if isfile(self.lockfile):
            raise RepositoryLocked
        lock = file(self.lockfile, 'w')
        lock.close()

    def _unlock_repo(self):
        if isfile(self.lockfile):
            os.unlink(self.lockfile)

    @expose(template='bodhi.templates.push')
    def index(self):
        """ List updates that need to be pushed """
        updates = PackageUpdate.select(PackageUpdate.q.needs_push == True)
        return dict(updates=updates, label='Push Updates',
                    callback='/admin/push/push_updates')

    @expose(template='bodhi.templates.push')
    def unpush(self):
        """ List updates that need to be unpushed """
        updates = PackageUpdate.select(PackageUpdate.q.needs_unpush == True)
        return dict(updates=updates, label='Unpush Updates',
                    callback='/admin/push/unpush_updates')

    @expose(template='bodhi.templates.pushconsole')
    def console(self, updates, callback, **kw):
        if not updates:
            flash("No updates selected for pushing")
            raise redirect("/push")
        if not isinstance(updates, list):
            updates = [updates]
        log.debug("Setting updates in session: %s" % updates)
        cherrypy.session['updates'] = updates
        return dict(callback=callback)

    @expose()
    def push_updates(self):
        """
        This method is called by the pushconsole template.
        It returns a generator that spits out the push results.  We're using
        comet here, so the results will be pushed out to the client
        asynchronously.

        TODO: find out why this is broke in konqueror
        """
        @comet(content_type='text/plain')
        def _do_push():
            start_time = datetime.now()
            yield "Starting push at %s" % start_time
            try:
                self._lock_repo()
                yield "Acquired lock for repository"
            except RepositoryLocked:
                err = "Unable to acquire lock for repository"
                log.info(err)
                yield err
                return

            updateinfo = ExtendedMetadata()
            releases = { True : set(), False : set() } # testing : releases

            for package in cherrypy.session['updates']:
                update = PackageUpdate.byNvr(package)
                releases[update.testing].add(update.release)
                try:
                    yield self.header("Pushing %s" % update.nvr)
                    for output in self.push_files(update):
                        yield output
                        log.info(output)
                    update.assign_id()
                    yield " * Setting update ID to %s" % update.update_id
                    yield " * Generating extended update metadata"
                    updateinfo.add_update(update)
                    update.needs_push = False
                    update.pushed = True
                    yield " * Sending notification to %s" % update.submitter
                    mail.send(update.submitter, 'pushed', update)
                    update.sync()
                except Exception, e:
                    log.error("Exception during push: %s" % e)
                    yield "ERROR: Exception thrown during push: %s" % e
                    yield self.header("Unpushing %s" % update.nvr)
                    for msg in self.unpush_files(update):
                        yield msg
                        log.info(msg)
                    return

            yield self.header("Generating repository metadata")
            for (testing, releases) in releases.items():
                for release in releases:
                    for output in self.generate_metadata(release, testing):
                        yield output
                        log.info(output)

            yield " * Inserting updateinfo.xml into repositories"
            updateinfo.insert_updateinfo()

            self._unlock_repo()
            cherrypy.session['updates'] = []
            yield self.header("Push completed in %s" % str(datetime.now() -
                                                          start_time))
        return _do_push()

    @expose()
    def unpush_updates(self):

        @comet(content_type='text/plain')
        def _do_unpush():
            start_time = datetime.now()
            yield "Starting unpush on %s" % start_time
            try:
                self._lock_repo()
                yield "Acquired lock for repository"
            except RepositoryLocked:
                err = "Unable to acquire lock for repository"
                log.debug(err)
                yield err
                return

            updateinfo = ExtendedMetadata()
            releases = { True : set(), False : set() } # testing : releases

            for package in cherrypy.session['updates']:
                update = PackageUpdate.byNvr(package)
                releases[update.testing].add(update.release)
                yield self.header("Unpushing %s" % update.nvr)
                for msg in self.unpush_files(update):
                    log.info(msg)
                    yield msg
                update.pushed = False
                update.needs_unpush = False
                yield " * Removing extended metadata from updateinfo.xml"
                updateinfo.remove_update(update)
                mail.send(update.submitter, 'unpushed', update)

            yield self.header("Generating repository metadata")
            for (testing, releases) in releases.items():
                for release in releases:
                    for output in self.generate_metadata(release, testing):
                        yield output
                        log.info(output)

            yield " * Re-inserting updated updateinfo.xml"
            updateinfo.insert_updateinfo()

            yield self.header("Unpush completed in %s" % str(datetime.now() -
                                                             start_time))
            self._unlock_repo()

        return _do_unpush()

    def push_files(self, update):
        """
        Go through the updates filelist and copy the files to updates stage.
        """
        for arch in update.filelist.keys():
            dest = join(update.get_repo(), arch)
            for file in update.filelist[arch]:
                filename = basename(file)
                if filename.find('debuginfo') != -1:
                    destfile = join(dest, 'debug', filename)
                else:
                    destfile = join(dest, filename)
                if isfile(destfile):
                    yield "Removing already pushed file: %s" % filename
                    os.unlink(destfile)
                yield " * %s" % join(update.testing and 'testing' or '',
                                     update.release.name, arch, filename)
                os.link(file, destfile)

    def unpush_files(self, update):
        """
        Remove all files for a given update that may or may not exist in the
        updates stage.
        """
        for arch in update.filelist.keys():
            dest = join(update.get_repo(), arch)
            for file in update.filelist[arch]:
                filename = basename(file)
                if file.find('debuginfo') != -1:
                    destfile = join(dest, 'debug', filename)
                else:
                    destfile = join(dest, filename)
                if isfile(destfile):
                    yield " * %s" % join(update.testing and 'testing' or '',
                                         update.release.name, arch, filename)
                    os.unlink(destfile)
                else:
                    yield "Cannot find file in update: %s" % destfile

    def generate_metadata(self, release, testing):
        """
        Generate repository metadata for a given release.
        """
        baserepo = testing and release.testrepo or release.repo
        for arch in release.arches:
            repo = join(baserepo, arch.name)

            ## Move the updateinfo.xml.gz out of the way
            tmpmd = None
            updateinfo = join(repo, 'repodata', 'updateinfo.xml.gz')
            if isfile(updateinfo):
                import gzip
                tmpmd = tempfile.mktemp()
                tmp = open(tmpmd, 'w')
                md = gzip.open(updateinfo, 'r')
                tmp.write(md.read())
                tmp.close()
                md.close()
                log.debug("Copying update updateinfo from %s to %s" %
                          (repo,tmpmd))
                os.remove(updateinfo)

            yield ' * %s' % join(testing and 'testing' or '', release.name,
                                 arch.name)
            genpkgmetadata.main(['--cachedir', str(self.createrepo_cache),
                                 '-q', str(repo)])

            ## Insert the updateinfo.xml.gz back into the repodata
            if tmpmd:
                tmpxml = join(repo, 'repodata', 'updateinfo.xml')
                shutil.move(tmpmd, tmpxml)
                repomd = RepoMetadata(join(repo, 'repodata'))
                repomd.add(str(tmpxml))
                os.remove(tmpxml)
                tmpmd = None
                log.debug("Inserted updateinfo.xml into %s" %
                          join(repo, 'repodata'))

            debugrepo = join(repo, 'debug')
            if isdir(debugrepo):
                 yield ' * %s' % join(testing and 'testing' or '',
                                      release.name, arch.name, 'debug')
                 genpkgmetadata.main(['--cachedir', str(self.createrepo_cache),
                                      '-q', str(debugrepo)])

## Allow us to return a generator for streamed responses
cherrypy.config.update({'/admin/push/push_updates':{'stream_response':True}})
cherrypy.config.update({'/admin/push/unpush_updates':{'stream_response':True}})
