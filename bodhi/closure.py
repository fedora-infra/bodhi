# $Id: closure.py,v 1.5 2006/11/12 21:04:47 lmacken Exp $
#
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
#

import os
import sys
import time
import logging
import tempfile

from os.path import join, exists, normpath
from bodhi.model import PackageUpdate
from turbogears import config
from yum.constants import *

sys.path.append('/usr/share/createrepo')
import genpkgmetadata

# pull in RepoClosure
execfile('/usr/bin/repoclosure')

log = logging.getLogger(__name__)

confheader = """
[main]
cachedir=%s
debuglevel=2
logfile=/var/log/yum.log
pkgpolicy=newest
distroverpkg=fedora-release
reposdir=/dev/null
"""

repo_config = """
[core-%(rel)s-%(arch)s]
name=Fedora Core %(rel)s - %(arch)s
baseurl=http://download.fedora.redhat.com/pub/fedora/linux/core/%(rel)s/%(arch)s/os/
enabled=1

[updates %(rel)s-%(arch)s]
name=Fedora Core Updates %(rel)s - %(arch)s
baseurl=http://download.fedora.redhat.com/pub/fedora/linux/core/updates/%(rel)s/%(arch)s/
enabled=1

[updates-testing %(rel)s-%(arch)s]
name=Fedora Core Updates Testing %(rel)s - %(arch)s
baseurl=http://download.fedora.redhat.com/pub/fedora/linux/core/updates/testing/%(rel)s/%(arch)s/
enabled=%(testing)s

[testrepo-%(rel)s-%(arch)s]
name=Fedora Core %(rel)s - %(arch)s
baseurl=file://%(testrepo)s/final/%(rel)s/%(arch)s
enabled=%(final)s

[testrepo-testing-%(rel)s-%(arch)s]
name=Fedora Core %(rel)s - %(arch)s
baseurl=file://%(testrepo)s/testing/%(rel)s/%(arch)s
enabled=%(testing)s
"""

class TestRepoClosure(object):

    def __init__(self, updates):
        self.updates = updates
        self.testing = False
        self.final = False
        self.testrepo_dir = config.get('testrepo_dir')
        self.cache_dir = config.get('createrepo_cache_dir')

        # set our cache directory
        global confheader
        confheader %= self.cache_dir

        # create a set of releases that we need to check closure on
        self.releases = set()
        for update in self.updates:
            if update.testing:
                self.testing = True
            else:
                self.final = True
            self.releases.add(update.release)

    def run(self):
        """
        Prepare the closure repo, and begin the test
        """
        log.debug("Running TestRepoClosure")
        start = time.time()

        self._clean()
        self._copy_to_repo()
        self._generate_metadata()

        # Run repoclosure on the given repos.
        for release in self.releases:
            log.debug("Checking Dependecies for %s" % release.name)
            self._test_closure(release)

        log.debug("Dependency checking complete in %f seconds" % (
                  time.time() - start))

    def _copy_to_repo(self):
        """
        Copy the files to the test repository
        """
        log.debug("Copying update packages to our test repo")
        for update in self.updates:
            oldreq = update.request
            update.request = 'push'
            for msg in update.run_request(self.testrepo_dir):
                log.debug(msg)
            update.request = oldreq

    def _clean(self):
        """
        Wipe out the existing testrepo and create the appropriate repo
        directories for this batch of updates.
        """
        import shutil
        log.debug("Cleaning the closure repository")
        if exists(self.testrepo_dir):
            log.debug("Removing old test repo tree")
            shutil.rmtree(self.testrepo_dir)
        for update in self.updates:
            repo = join(self.testrepo_dir, update.get_repo())
            for arch in update.release.arches:
                archdir = join(repo, arch.name)
                srpmdir = join(repo, 'SRPMS')
                if not exists(archdir):
                    log.debug("Creating " + archdir)
                    os.makedirs(join(archdir, 'debug'))
                if not exists(srpmdir):
                    log.debug("Creating " + srpmdir)
                    os.mkdir(srpmdir)

    def _generate_metadata(self):
        """
        Build the repository metadata and config file
        """
        for tf in ('testing', ''):
            for release in os.listdir(join(self.testrepo_dir, tf)):
                if release == 'testing': continue
                for arch in os.listdir(join(self.testrepo_dir, tf, release)):
                    fullpath = normpath(join(self.testrepo_dir, tf,
                                             release, arch))
                    log.debug("Generating metadata for %s" % fullpath)
                    genpkgmetadata.main(['-c', str(self.cache_dir), '-q',
                                         str(fullpath)])

    def _test_closure(self, release):
        """
        Run repoclosure on for a given release
        """
        for arch in release.arches:
            for testing in (True, False):
                log.debug("Checking closure on %s-%s-%s" % (release.name,
                          arch.name, testing and 'testing' or 'final'))
                if not self.testing and testing:
                    log.debug("Skipping updates-testing check for %s - %s" %
                              (release.name, arch.name))
                    continue
                conf = self.generate_config(release, arch, testing)
                log.debug("Using yum configuration = %s" % conf)
                closure = RepoClosure(config = conf)
                log.debug("Reading Metadata()")
                closure.readMetadata()
                log.debug("Checking for broken deps")
                baddeps = closure.getBrokenDeps(newest=True)
                log.debug("Broken deps:")
                pkgs = baddeps.keys()
                pkgs.sort()
                for pkg in pkgs:
                    log.debug('[%s]' % pkg)
                    for (n, f, v) in baddeps[pkg]:
                        r = '%s' % n
                        if f:
                            flag = LETTERFLAGS[f]
                            r = '%s %s' % (r, flag)
                        if v:
                            r = '%s %s' % (r, v)
                        log.debug(' * %s' % r)

    def generate_config(self, release, arch, testing):
        """
        Generate a yum configuration file for this given release containing
        the core repo, both updates and updates-testing for each arch that
        this release supports
        """
        conffile = tempfile.mktemp()
        fd = open(conffile, 'w')
        fd.write(confheader)
        repo = repo_config % {
            'testrepo'  : self.testrepo_dir,
            'rel'       : release.repodir,
            'arch'      : arch.name,
            'testing'   : testing and '1' or '0',
            'final'     : self.final and '1' or '0'
        }
        fd.write(repo)
        fd.close()
        return conffile

#
# Main method used for testing purposes
#
if __name__ == '__foo__':
    from turbogears.database import PackageHub

    hub = PackageHub("bodhi")
    __connection__ = hub

    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)

    closure = TestRepoClosure(PackageUpdate.select())
    closure.run()
