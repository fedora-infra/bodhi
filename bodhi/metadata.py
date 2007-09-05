# $Id: metadata.py,v 1.1 2006/12/31 09:10:14 lmacken Exp $
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

__version__ = '1.4'

import os
import rpm
import gzip
import logging

from xml.dom import minidom
from os.path import join, basename, exists
from sqlobject import SQLObjectNotFound
from turbogears import config

from bodhi.util import sha1sum
from bodhi.model import PackageBuild
from bodhi.buildsys import get_session
from bodhi.modifyrepo import RepoMetadata
from bodhi.exceptions import RepositoryNotFound

log = logging.getLogger(__name__)

class ExtendedMetadata:

    def __init__(self, tag):
        self.tag = tag
        self.doc = None
        self.updates = set()
        self.koji = get_session()
        self._create_document()
        self._fetch_updates()
        log.debug("Generating XML update metadata for updates")
        map(self.add_update, self.updates)

    def _fetch_updates(self):
        """
        Based on our given koji tag, populate a list of PackageUpdates.
        """
        log.debug("Fetching builds tagged with '%s'" % self.tag)
        builds = self.koji.listTagged(self.tag, latest=True)
        log.debug("%d builds found" % len(builds))
        for build in builds:
            try:
                b = PackageBuild.byNvr(build['nvr'])
                map(self.updates.add, b.updates)
            except SQLObjectNotFound, e:
                log.warning(e)
        log.debug("%d updates = %s" % (len(self.updates), self.updates))

    def _create_document(self):
        log.debug("Creating new updateinfo Document for %s" % self.tag)
        self.doc = minidom.Document()
        updates = self.doc.createElement('updates')
        self.doc.appendChild(updates)

    def _insert(self, parent, name, attrs={}, text=None):
        """ Helper function to trivialize inserting an element into the doc """
        child = self.doc.createElement(name)
        for item in attrs.items():
            child.setAttribute(item[0], str(item[1]))
        if text:
            txtnode = self.doc.createTextNode(str(text))
            child.appendChild(txtnode)
        parent.appendChild(child)
        return child

    def _get_notice(self, update):
        for elem in self.doc.getElementsByTagName('update'):
            for child in elem.childNodes:
                if child.nodeName == 'id' and child.firstChild and \
                   child.firstChild.nodeValue == update.update_id:
                    return elem
        return None

    #def remove_update(self, update):
    #    elem = self._get_notice(update)
    #    if elem:
    #        log.debug("Removing %s from updateinfo.xml" % update.title)
    #        self.doc.firstChild.removeChild(elem)
    #        return True
    #    return False

    def add_update(self, update):
        """
        Generate the extended metadata for a given update
        """
        ## Make sure this update doesn't already exist
        if self._get_notice(update):
            log.debug("Update %s already in updateinfo" % update.title)
            return

        log.debug("Generating extended metadata for %s" % update.title)

        root = self._insert(self.doc.firstChild, 'update', attrs={
                'type'      : update.type,
                'status'    : update.status,
                'version'   : __version__,
                'from'      : config.get('release_team_address')
        })

        self._insert(root, 'id', text=update.update_id)
        self._insert(root, 'title', text=update.title)
        self._insert(root, 'release', text=update.release.long_name)
        self._insert(root, 'issued', attrs={ 'date' : update.date_pushed })

        ## Build the references
        refs = self.doc.createElement('references')
        for cve in update.cves:
            self._insert(refs, 'reference', attrs={
                    'type' : 'cve',
                    'href' : cve.get_url(),
                    'id'   : cve.cve_id
            })
        for bug in update.bugs:
            self._insert(refs, 'reference', attrs={
                    'type' : 'bugzilla',
                    'href' : bug.get_url(),
                    'id'   : bug.bz_id,
                    'title': bug.title
            })
        root.appendChild(refs)

        ## Errata description
        self._insert(root, 'description', text=update.notes)

        ## The package list
        pkglist = self.doc.createElement('pkglist')
        collection = self.doc.createElement('collection')
        collection.setAttribute('short', update.release.name)
        self._insert(collection, 'name', text=update.release.long_name)

        for build in update.builds:
            log.debug("Generating package list for %s" % build.nvr)
            kojiBuild = self.koji.getBuild(build.nvr)
            rpms = self.koji.listBuildRPMs(kojiBuild['id'])
            for rpm in rpms:
                filename = "%s.%s.rpm" % (rpm['nvr'], rpm['arch'])
                if rpm['arch'] == 'src':
                    arch = 'SRPMS'
                elif rpm['arch'] == 'noarch':
                    arch = 'i386'
                else:
                    arch = rpm['arch']
                filepath = join(config.get('build_dir'), kojiBuild['name'],
                                kojiBuild['version'], kojiBuild['release'],
                                rpm['arch'], filename)
                urlpath = join(config.get('file_url'),
                               update.status == 'testing' and 'testing' or '',
                               update.release.name[-1], arch, filename)
                pkg = self._insert(collection, 'package', attrs={
                            'name'      : rpm['name'],
                            'version'   : rpm['version'],
                            'release'   : rpm['release'],
                            'arch'      : rpm['arch'],
                            'src'       : urlpath
                })
                self._insert(pkg, 'filename', text=filename)
                try:
                    self._insert(pkg, 'sum', attrs={ 'text' : 'sha1' },
                                 text=sha1sum(filepath))
                except IOError:
                    log.error("Cannot find package for checksum: %s" % filepath)

                if build.package.suggest_reboot:
                    self._insert(pkg, 'reboot_suggested', text='True')

                collection.appendChild(pkg)

        pkglist.appendChild(collection)
        root.appendChild(pkglist)
        log.debug("Metadata generation successful")

    def insert_updateinfo(self, repo):
        try:
            repomd = RepoMetadata(repo)
            log.debug("Inserting updateinfo.xml.gz into %s" % repo)
            repomd.add(self.doc)
        except RepositoryNotFound:
            log.error("Cannot find repomd.xml in %s" % repo)
