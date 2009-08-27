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
# Authors: Luke Macken <lmacken@fedoraproject.org>

__version__ = '1.4'

import os
import logging

from xml.dom import minidom
from os.path import join, exists
from sqlobject import SQLObjectNotFound
from turbogears import config

from bodhi.util import get_repo_tag
from bodhi.model import PackageBuild
from bodhi.buildsys import get_session
from bodhi.modifyrepo import RepoMetadata
from bodhi.exceptions import RepositoryNotFound

from yum.update_md import UpdateMetadata

log = logging.getLogger(__name__)

class ExtendedMetadata:

    def __init__(self, repo, cacheduinfo=None):
        self.tag = get_repo_tag(repo)
        self.repo = repo
        self.doc = None
        self.updates = set()
        self.builds = {}
        self._from = config.get('bodhi_email')
        self.koji = get_session()
        self._create_document()
        self._fetch_updates()
        missing_ids = []

        if cacheduinfo and exists(cacheduinfo):
            log.debug("Loading cached updateinfo.xml.gz")
            umd = UpdateMetadata()
            umd.add(cacheduinfo)

            # Generate metadata for any new builds
            for update in self.updates:
                for build in update.builds:
                    if not umd.get_notice(build.nvr):
                        if update.updateid:
                            self.add_update(update)
                            break
                        else:
                            missing_ids.append(update.title)

            # Add all relevant notices from the metadata to this document
            ids = [update.updateid for update in self.updates if update.updateid]
            for notice in umd.get_notices():
                if notice['update_id'] in ids:
                    self._add_notice(notice)
                else:
                    log.debug("Removing %s from updateinfo" % notice['title'])
        else:
            log.debug("Generating new updateinfo.xml")
            for update in self.updates:
                if update.updateid:
                    self.add_update(update)
                else:
                    missing_ids.append(update.title)

        if missing_ids:
            log.error("%d updates with missing ID!" % len(missing_ids))
            log.debug(missing_ids)

    def _fetch_updates(self):
        """
        Based on our given koji tag, populate a list of PackageUpdates.
        """
        log.debug("Fetching builds tagged with '%s'" % self.tag)
        kojiBuilds = self.koji.listTagged(self.tag, latest=True)
        nonexistent = []
        log.debug("%d builds found" % len(kojiBuilds))
        for build in kojiBuilds:
            self.builds[build['nvr']] = build
            try:
                b = PackageBuild.byNvr(build['nvr'])
                for update in b.updates:
                    if update.status in ('testing', 'stable'):
                        self.updates.add(update)
            except SQLObjectNotFound, e:
                nonexistent.append(build['nvr'])
        if nonexistent:
            log.warning("Couldn't find the following koji builds tagged as "
                        "%s in bodhi: %s" % (self.tag, nonexistent))

    def _create_document(self):
        log.debug("Creating new updateinfo Document for %s" % self.tag)
        self.doc = minidom.Document()
        updates = self.doc.createElement('updates')
        self.doc.appendChild(updates)

    def _insert(self, parent, name, attrs={}, text=None):
        """ Helper function to trivialize inserting an element into the doc """
        child = self.doc.createElement(name)
        for item in attrs.items():
            child.setAttribute(item[0], unicode(item[1]))
        if text:
            txtnode = self.doc.createTextNode(unicode(text))
            child.appendChild(txtnode)
        parent.appendChild(child)
        return child

    def _get_notice(self, update):
        for elem in self.doc.getElementsByTagName('update'):
            for child in elem.childNodes:
                if child.nodeName == 'id' and child.firstChild and \
                   child.firstChild.nodeValue == update.updateid:
                    return elem
        return None

    def _add_notice(self, notice):
        """ Add a yum.update_md.UpdateNotice to the metadata """

        root = self._insert(self.doc.firstChild, 'update', attrs={
                'type'      : notice['type'],
                'status'    : notice['status'],
                'version'   : __version__,
                'from'      : self._from,
        })

        self._insert(root, 'id', text=notice['update_id'])
        self._insert(root, 'title', text=notice['title'])
        self._insert(root, 'release', text=notice['release'])
        self._insert(root, 'issued', attrs={ 'date' : notice['issued'] })
        self._insert(root, 'reboot_suggested', text=notice['reboot_suggested'])

        ## Build the references
        refs = self.doc.createElement('references')
        for ref in notice._md['references']:
            self._insert(refs, 'reference', attrs={
                    'type' : ref['type'],
                    'href' : ref['href'],
                    'id'   : ref['id']
            })
        root.appendChild(refs)

        ## Errata description
        self._insert(root, 'description', text=notice['description'])

        ## The package list
        pkglist = self.doc.createElement('pkglist')
        for group in notice['pkglist']:
            collection = self.doc.createElement('collection')
            collection.setAttribute('short', group['short'])
            self._insert(collection, 'name', text=group['name'])
            for pkg in group['packages']:
                p = self._insert(collection, 'package', attrs={
                        'name'    : pkg['name'],
                        'version' : pkg['version'],
                        'release' : pkg['release'],
                        'arch'    : pkg['arch'],
                        'src'     : pkg['src']
                })
                self._insert(p, 'filename', text=pkg['filename'])
                collection.appendChild(p)

        pkglist.appendChild(collection)
        root.appendChild(pkglist)

    def add_update(self, update):
        """
        Generate the extended metadata for a given update
        """
        ## Make sure this update doesn't already exist
        if self._get_notice(update):
            log.debug("Update %s already in updateinfo" % update.title)
            return

        root = self._insert(self.doc.firstChild, 'update', attrs={
                'type'      : update.type,
                'status'    : update.status,
                'version'   : __version__,
                'from'      : config.get('bodhi_email')
        })

        self._insert(root, 'id', text=update.updateid)
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
            kojiBuild = None
            try:
                kojiBuild = self.builds[build.nvr]
            except:
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
                urlpath = join(config.get('file_url'),
                               update.status == 'testing' and 'testing' or '',
                               update.release.name[-1], arch, filename)
                pkg = self._insert(collection, 'package', attrs={
                            'name'      : rpm['name'],
                            'version'   : rpm['version'],
                            'release'   : rpm['release'],
                            'epoch'     : rpm['epoch'],
                            'arch'      : rpm['arch'],
                            'src'       : urlpath
                })
                self._insert(pkg, 'filename', text=filename)

                if build.package.suggest_reboot:
                    self._insert(pkg, 'reboot_suggested', text='True')

                collection.appendChild(pkg)

        pkglist.appendChild(collection)
        root.appendChild(pkglist)

    def insert_updateinfo(self):
        for arch in os.listdir(self.repo):
            try:
                repomd = RepoMetadata(join(self.repo, arch, 'repodata'))
                log.debug("Inserting updateinfo.xml.gz into %s/%s" % (self.repo, arch))
                repomd.add(self.doc)
            except RepositoryNotFound:
                log.error("Cannot find repomd.xml in %s" % self.repo)
