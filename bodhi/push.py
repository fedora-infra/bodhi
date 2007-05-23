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
import commands

from Comet import comet
from datetime import datetime
from turbogears import (controllers, expose, flash, redirect, config,
                        identity, url)

from bodhi.util import mkmetadatadir, header
from bodhi.model import PackageUpdate
from bodhi.metadata import ExtendedMetadata
from bodhi.modifyrepo import RepoMetadata

from os.path import isfile, isdir, basename, join

log = logging.getLogger(__name__)

class RepositoryLocked(Exception):
    pass

class PushController(controllers.Controller):

    def __init__(self):
        self.createrepo_cache = config.get('createrepo_cache_dir')
        self.stage_dir = config.get('stage_dir')
        self.lockfile = join(self.stage_dir, '.lock')
        self.orig_repo = None
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

    def repodiff(self):
        """
        When this method is first called, it saves a snapshot of the
        updates-stage tree (tree -s output).  When called a second time,
        it takes another snapshot, diffs it with the original, and stores
        the diff in 'repodiff_dir'.
        """
        if not self.orig_repo:
            self.orig_repo = tempfile.mkstemp()
            tree = commands.getoutput("tree -s %s" % self.stage_dir)
            os.write(self.orig_repo[0], tree)
        else:
            self.new_repo = tempfile.mkstemp()
            tree = commands.getoutput("tree -s %s" % self.stage_dir)
            os.write(self.new_repo[0], tree)
            os.close(self.new_repo[0])
            os.close(self.orig_repo[0])
            diff = join(config.get('repodiff_dir'), '%s' %
                        datetime.now().strftime("%Y%m%d-%H%M%S"))
            diff = open(diff, 'w')
            diff.write(commands.getoutput("diff -u %s %s" % (self.orig_repo[1],
                                                             self.new_repo[1])))
            diff.close()
            os.unlink(self.orig_repo[1])
            os.unlink(self.new_repo[1])
            self.orig_repo = None

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
            raise redirect(url("/push"))
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
            start_time = datetime.now()
            yield "Starting push at %s" % start_time
            self.repodiff()
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
                if update.request == 'move':
                    releases[False].add(update.release)
                for msg in update.run_request(updateinfo=updateinfo):
                    log.debug(msg)
                    yield msg

            # Regenerate the repository metadata
            yield header("Generating repository metadata")
            try:
                for (testing, releases) in releases.items():
                    for release in releases:
                        for output in generate_metadata(release, testing):
                            yield output
                            log.info(output)
                yield " * Inserting updateinfo.xml into repositories"
                updateinfo.insert_updateinfo()
            except Exception, e:
                log.error(e)
                msg = "Exception thrown: " + str(e)
                log.error(msg)
                yield "ERROR: " + msg
                raise e

            # Clean up
            self._unlock_repo()
            cherrypy.session['updates'] = []
            msg = "Push completed %s" % str(datetime.now() - start_time)
            log.debug(msg)
            yield header(msg)
            self.repodiff()

        return _run_requests()

def generate_metadata(release, testing, stage=None):
    """
    Generate repository metadata for a given release.
    """
    if not stage: stage = config.get('stage_dir')
    baserepo = join(stage, testing and 'testing' or '', release.repodir)

    for arch in [arch.name for arch in release.arches] + [u'SRPMS']:
        repo = join(baserepo, arch)

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

        yield ' * %s' % join(testing and 'testing' or '', release.name, arch)
        mkmetadatadir(repo)

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
                                  release.name, arch, 'debug')
             mkmetadatadir(debugrepo)

## Allow us to return a generator for streamed responses
cherrypy.config.update({'/admin/push/run_requests':{'stream_response':True}})
