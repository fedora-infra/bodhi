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
            yield "Starting push on %s\n" % datetime.now()
            try:
                self._lock_repo()
                yield "Acquired lock for repository"
            except RepositoryLocked:
                err = "Unable to acquire lock for repository"
                log.debug(err)
                yield err
                return

            md = ExtendedMetadata()

            line = '=' * 100
            for package in cherrypy.session['updates']:
                update = PackageUpdate.byNvr(package)
                try:
                    yield "%s\nPushing %s\n%s" % (line, update.nvr, line)
                    for output in self.push_update(update):
                        log.info(output)
                        yield output
                    yield "%s\nGenerating repository metadata\n%s" % (line, line)
                    for output in self.generate_metadata(update):
                        log.info(output)
                        yield output
                    update.needs_push = False
                    update.pushed = True
                    update.assign_id()
                    yield "%s\nSetting update ID to %s" % (line, update.update_id)
                    yield "Generating extended update metadata"
                    md.add_update(update)
                    yield "Sending notification to %s" % update.submitter
                    mail.send(update.submitter, 'pushed', update)
                    update.sync()
                except Exception, e:
                    log.error("Exception during push: %s" % e)
                    yield "ERROR: Exception thrown during push: %s" % e
                    raise e

            yield "Inserting extended metadata into repos"
            md.insert_updateinfo()
            self._unlock_repo()
            cherrypy.session['updates'] = []

            yield "\nPushing Complete! <%s>\n" % datetime.now()

        return _do_push()

    @expose()
    def unpush_updates(self):
        @comet(content_type='text/plain')
        def _do_unpush():
            try:
                self._lock_repo()
                yield "Acquired lock for repository"
            except RepositoryLocked:
                err = "Unable to acquire lock for repository"
                log.debug(err)
                yield err
                return
            line = '=' * 100
            for package in cherrypy.session['updates']:
                update = PackageUpdate.byNvr(package)
                yield "%s\nUnpushing %s\n%s" % (line, update.nvr, line)
                for msg in self.unpush_update(update):
                    log.info(msg)
                    yield msg
                # does this wipe out the updateinfo?
                yield "%s\nRegenerating metadata\n%s" % (line, line)
                for msg in self.generate_metadata(update):
                    log.info(msg)
                    yield msg
                update.pushed = False
                update.needs_unpush = False
                yield "Removing extended metadata from updateinfo.xml.gz"
                updateinfo = ExtendedMetadata()
                updateinfo.remove_update(update)
                updateinfo.insert_updateinfo()
                mail.send(update.submitter, 'unpushed', update)
            yield "%s\nUpdates successfully unpushed!" % (line)
            self._unlock_repo()
        return _do_unpush()

    def push_update(self, update):
        try:
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
                    yield "Pushing %s" % (filename)
                    os.link(file, destfile)
        except Exception, e:
            yield "Caught the following exception during push: %s" % str(e)
            for msg in self.unpush_update(update):
                yield msg

    def unpush_update(self, update):
        """
        Remove all files for a given update that may or may not exist in the
        updates stage.
        """
        yield "Unpushing %s" % update.nvr
        for arch in update.filelist.keys():
            dest = join(update.get_repo(), arch)
            for file in update.filelist[arch]:
                if file.find('debuginfo') != -1:
                    destfile = join(dest, 'debug', basename(file))
                else:
                    destfile = join(dest, basename(file))
                if isfile(destfile):
                    yield "Deleting %s" % destfile
                    os.unlink(destfile)
                else:
                    yield "Cannot find file in update: %s" % destfile

    def generate_metadata(self, update):
        """
        Generate the repomd for all repos that this update effects
        """
        baserepo = update.get_repo()
        for arch in update.filelist.keys():
            repo = join(baserepo, arch)

            #cache_dir = join(self.createrepo_cache, 'fc%s-%s' %
            #                 (update.release.name[-1], arch))
            #if not isdir(cache_dir):
            #    log.info("Creating createrepo cache directory: %s" % cache_dir)
            #    os.makedirs(cache_dir)

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
                log.debug("Copying update updateinfo from %s to %s" % (repo, tmpmd))
                #shutil.copyfile(updateinfo, tmpmd)
                os.remove(updateinfo)

            yield repo
            genpkgmetadata.main(['--cachedir',str(self.createrepo_cache),'-q',str(repo)])

            ## Insert the updateinfo.xml.gz back into the repodata
            if tmpmd:
                #shutil.copyfile(tmpmd, updateinfo)
                repomd = RepoMetadata(join(repo, 'repodata'))
                repomd.add(tmpmd)
                tmpmd = None
                log.debug("Inserted updateinfo.xml.gz into %s" % join(repo, 'repodata'))

            debugrepo = join(repo, 'debug')
            if isdir(debugrepo):
                 genpkgmetadata.main(['--cachedir', str(self.createrepo_cache),
                                      '-q', str(debugrepo)])
                 yield debugrepo

## Allow us to return a generator for streamed responses
cherrypy.config.update({'/push/push_updates':{'stream_response':True}})
cherrypy.config.update({'/push/unpush_updates':{'stream_response':True}})
