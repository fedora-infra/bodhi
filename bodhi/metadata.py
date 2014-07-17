# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

__version__ = '1.4'

import os
import logging
import shutil
import tempfile

from xml.dom import minidom
from os.path import join, exists
from datetime import datetime
from urlgrabber.grabber import urlgrab

from bodhi.config import config
from bodhi.models import Build, UpdateStatus, UpdateRequest, UpdateSuggestion
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

            # Drop the old cached updateinfo.xml.gz, it's unneeded now
            os.unlink(cacheduinfo)

            existing_ids = set([up['update_id'] for up in umd.get_notices()])
            seen_ids = set()
            from_cache = set()

            # Generate metadata for any new builds
            for update in self.updates:
                if update.alias:
                    seen_ids.add(update.alias)
                    if update.alias in existing_ids:
                        notice = umd.get_notice(update.title)
                        if not notice:
                            log.warn('%s ID in cache but notice cannot be found' % (update.title))
                            self.add_update(update)
                            continue
                        if notice['updated']:
                            if datetime.strptime(notice['updated'], '%Y-%m-%d %H:%M:%S') < update.date_modified:
                                log.debug('Update modified, generating new notice: %s' % update.title)
                                self.add_update(update)
                            else:
                                log.debug('Loading updated %s from cache' % update.title)
                                from_cache.add(update.alias)
                        elif update.date_modified:
                            log.debug('Update modified, generating new notice: %s' % update.title)
                            self.add_update(update)
                        else:
                            log.debug('Loading %s from cache' % update.title)
                            from_cache.add(update.alias)
                    else:
                        log.debug('Adding new update notice: %s' % update.title)
                        self.add_update(update)
                else:
                    missing_ids.append(update.title)

            # Add all relevant notices from the cache to this document
            for notice in umd.get_notices():
                if notice['update_id'] in from_cache:
                    log.debug("Keeping existing notice: %s" % notice['title'])
                    self._add_notice(notice)
                else:
                    # Keep all security notices in the stable repo
                    if 'testing' not in self.repo:
                        if notice['type'] == 'security':
                            if notice['update_id'] not in seen_ids:
                                log.debug("Keeping existing security notice: %s" %
                                        notice['title'])
                                self._add_notice(notice)
                            else:
                                log.debug('%s already added?' % notice['title'])
                        else:
                            log.debug('Purging cached stable notice %s' % notice['title'])
                    else:
                        log.debug('Purging cached testing update %s' % notice['title'])

        # Clean metadata generation
        else:
            log.debug("Generating new updateinfo.xml")
            for update in self.updates:
                if update.alias:
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
        """Based on our given koji tag, populate a list of Update objects"""
        log.debug("Fetching builds tagged with '%s'" % self.tag)
        kojiBuilds = self.koji.listTagged(self.tag, latest=True)
        nonexistent = []
        log.debug("%d builds found" % len(kojiBuilds))
        for build in kojiBuilds:
            self.builds[build['nvr']] = build
            build_obj = self.db.query(Build).filter_by(nvr=build['nvr']).first()
            if build_obj:
                self.updates.add(build_obj.update)
            else:
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
                   child.firstChild.nodeValue == update.alias:
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
        self._insert(root, 'issued', attrs={'date' : notice['issued']})
        if notice['updated']:
            self._insert(root, 'updated', attrs={'date' : notice['updated']})
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
                'type': update.type.value,
                'status': update.status.value,
                'version': __version__,
                'from': config.get('bodhi_email'),
        })

        self._insert(root, 'id', text=update.alias)
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
                    'type': 'cve',
                    'href': cve.url,
                    'id': cve.cve_id
            })
        for bug in update.bugs:
            self._insert(refs, 'reference', attrs={
                    'type': 'bugzilla',
                    'href': bug.url,
                    'id': bug.bug_id,
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
                               update.status is UpdateStatus.testing and 'testing' or '',
                               str(update.release.version), arch, filename)
                pkg = self._insert(collection, 'package', attrs={
                            'name'      : rpm['name'],
                            'version'   : rpm['version'],
                            'release'   : rpm['release'],
                            'epoch'     : rpm['epoch'] or '0',
                            'arch'      : rpm['arch'],
                            'src'       : urlpath
                })
                self._insert(pkg, 'filename', text=filename)

                if build.update.suggest is UpdateSuggestion.reboot:
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
                tempdir = tempfile.mkdtemp('bodhi')
                local_tags = join(tempdir, 'pkgtags.sqlite')
                log.info('Downloading %s' % tags_url)
                urlgrab(tags_url, filename=local_tags)
                for arch in os.listdir(self.repo):
                    repomd = RepoMetadata(join(self.repo, arch, 'repodata'))
                    repomd.add(local_tags)
            except Exception, e:
                log.exception(e)
                log.error("There was a problem injecting pkgtags")
            finally:
                shutil.rmtree(tempdir)
