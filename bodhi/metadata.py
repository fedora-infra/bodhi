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
from datetime import datetime
from sqlobject import SQLObjectNotFound
from turbogears import config
from urlgrabber.grabber import URLGrabError, urlgrab

from bodhi.util import get_repo_tag
from bodhi.model import PackageBuild, PackageUpdate
from bodhi.buildsys import get_session
from bodhi.modifyrepo import RepoMetadata
from bodhi.exceptions import RepositoryNotFound

from yum.update_md import UpdateMetadata

log = logging.getLogger(__name__)

class ExtendedMetadata(object):

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
            seen_ids = set()

            cached_notices = {}
            for up in umd.get_notices():
                cached_notices[up['update_id']] = up

            for update in self.updates:
                if update.updateid:
                    if update.updateid in seen_ids:
                        log.debug('Skipping duplicate update: %s' % update.title)
                        continue
                    seen_ids.add(update.updateid)
                    if update.updateid in cached_notices:
                        cached_notice = cached_notices[update.updateid]
                        if not cached_notice:
                            log.debug('Updating modified notice for %s' % update.title)
                            self.add_update(update)
                            continue
                        updated = cached_notice['updated']
                        if updated:
                            updated = datetime.strptime(updated, '%Y-%m-%d %H:%M:%S')
                            if update.date_modified > updated:
                                log.debug('Updating old notice for %s' % update.title)
                                self.add_update(update)
                            else:
                                log.debug('Adding cached notice for %s' % update.title)
                                self._add_notice(cached_notice)
                        elif update.date_modified:
                            log.debug('Updating old notice for %s' % update.title)
                            self.add_update(update)
                        else:
                            log.debug('Adding cached notice for %s' % update.title)
                            self._add_notice(cached_notice)
                    else:
                        log.debug('Adding new update notice: %s' % update.title)
                        self.add_update(update)
                else:
                    missing_ids.append(update.title)

            # Add older security updates (#259)
            for update_id, notice in cached_notices.items():
                if notice['type'] == 'security' and update_id not in seen_ids:
                    log.debug('Adding older security update %r' % notice['title'])
                    self._add_notice(notice)
        else:
            log.debug("Generating new updateinfo.xml")
            for update in self.updates:
                if update.updateid:
                    log.debug('New update: %r %r' % (update.updateid, update.title))
                    self.add_update(update)
                else:
                    missing_ids.append(update.title)

            # Add *all* security updates
            # TODO: only the most recent
            #for update in PackageUpdate.select(PackageUpdate.q.type=='security'):
            #    self.add_update(update)

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

    def _insert(self, parent, name, attrs=None, text=None):
        """ Helper function to trivialize inserting an element into the doc """
        if not attrs:
            attrs = {}
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
        if notice['updated']:
            self._insert(root, 'updated', attrs={ 'date' : notice['updated'] })
        self._insert(root, 'reboot_suggested', text=notice['reboot_suggested'])

        ## Build the references
        refs = self.doc.createElement('references')
        for ref in notice._md['references']:
            attrs = {
                'type' : ref['type'],
                'href' : ref['href'],
                'id'   : ref['id'],
            }
            if ref.get('title'):
                attrs['title'] = ref['title']
            self._insert(refs, 'reference', attrs=attrs)
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
                        'src'     : pkg['src'],
                        'epoch'   : pkg.get('epoch', 0) or '0',
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
        self._insert(root, 'issued', attrs={
            'date' : update.date_pushed.strftime('%Y-%m-%d %H:%M:%S'),
        })
        if update.date_modified:
            self._insert(root, 'updated', attrs={
                'date' : update.date_modified.strftime('%Y-%m-%d %H:%M:%S'),
            })

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
                elif rpm['arch'] in ('noarch', 'i686'):
                    arch = 'i386'
                else:
                    arch = rpm['arch']
                urlpath = join(config.get('file_url'),
                               update.status == 'testing' and 'testing' or '',
                               str(update.release.get_version()), arch, filename)
                pkg = self._insert(collection, 'package', attrs={
                            'name'      : rpm['name'],
                            'version'   : rpm['version'],
                            'release'   : rpm['release'],
                            'epoch'     : rpm['epoch'] or '0',
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

    def insert_pkgtags(self):
        """ Download and inject the pkgtags sqlite from fedora-tagger """

        if config.get('pkgtags_url') not in [None, ""]:
            try:
                tags_url = config.get('pkgtags_url')
                local_tags = '/tmp/pkgtags.sqlite'
                log.info('Downloading %s' % tags_url)
                urlgrab(tags_url, filename=local_tags)
                for arch in os.listdir(self.repo):
                    repomd = RepoMetadata(join(self.repo, arch, 'repodata'))
                    repomd.add(local_tags)
            except Exception, e:
                log.exception(e)
                log.error("There was a problem injecting pkgtags")
