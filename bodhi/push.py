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
        self.header = lambda x: "%s\n     %s\n%s" % ('=' * 100, x, '=' * 100)
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
        """ List updates tagged with a push/unpush/move request """
        updates = PackageUpdate.select(PackageUpdate.q.request != None)
        return dict(updates=updates, label='Push Updates',
                    callback='/admin/push/run_requests')

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
    def run_requests(self):
        """
        Run all of the appropriate requests for a list of selected updates
        """
        @comet(content_type='text/plain')
        def _run_requests():
            log.debug("_run_requests()")
            start_time = datetime.now()
            yield "Starting push at %s" % start_time
            try:
                self._lock_repo()
                yield "Acquired repository lock"
            except RepositoryLocked:
                err = "Unable to acquire lock for repository"
                log.warning(err)
                yield err
                # TODO: block somehow until it becomes available
                # (or even attach to a current push console)

            # We need to keep track of the repos that we are proding so we
            # can regenerate the appropriate metadata
            releases = { True : set(), False : set() } # testing : releases

            # All of your updateinfo.xml.gz are belong to us
            updateinfo = ExtendedMetadata()

            # Execute each updates request
            for package in cherrypy.session['updates']:
                log.debug("Running request on %s" % package)
                update = PackageUpdate.byNvr(package)
                releases[update.testing].add(update.release)
                for msg in update.run_request():
                    yield msg
                if update.request == 'push':
                    log.debug("Adding update metadata to repo")
                    updateinfo.add_update(update)
                elif update.request == 'unpush':
                    updateinfo.remove_update(update)
                # TODO: figure out how to remove the metadata for 'move's

            # Regenerate the repository metadata
            yield self.header("Generating repository metadata")
            try:
                for (testing, releases) in releases.items():
                    for release in releases:
                        for output in self.generate_metadata(release, testing):
                            yield output
                            log.info(output)
                yield " * Inserting updateinfo.xml into repositories"
                updateinfo.insert_updateinfo()
            except Exception, e:
                msg = "Exception thrown: " + str(e)
                log.error(msg)
                yield "ERROR: " + msg
                raise e

            # Clean up
            self._unlock_repo()
            cherrypy.session['updates'] = []
            yield self.header("Push completed in %s" % str(datetime.now() -
                                                           start_time))
        return _run_requests()


    def generate_metadata(self, release, testing):
        """
        Generate repository metadata for a given release.
        """
        baserepo = join(self.stage_dir, testing and 'testing' or '',
                        release.repodir)
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
cherrypy.config.update({'/admin/push/run_requests':{'stream_response':True}})
