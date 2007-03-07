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

__version__ = '1.2'

import os
import rpm
import util
import time
import gzip
import logging

from model import Release, Bugzilla, CVE
from xml.dom import minidom
from os.path import join, basename, isdir, exists
from datetime import datetime
from sqlobject import OR
from turbogears import config
from modifyrepo import RepoMetadata

log = logging.getLogger(__name__)

## TODO: These should eventually make their way into the model
FILE_URL = 'http://download.fedoraproject.org/pub/fedora/linux/core/updates%s/%s/%s/%s'
rebootpkgs = ("kernel", "kernel-smp", "kernel-xen-hypervisor", "kernel-PAE",
              "kernel-xen0", "kernel-xenU", "kernel-xen", "kernel-xen-guest",
              "glibc", "hal", "dbus")

class ExtendedMetadata:

    def __init__(self):
        self.docs = {} # {repodir : [Release, xml.Document]}
        self.stage_dir = config.get('stage_dir')

    def _get_updateinfo(self, update):
        """
        Return the updateinfo metadata Document for the repository at a given
        path.  If the updateinfo.xml.gz is not present, then it will create
        a new Document and return it.
        """
        repo = join(self.stage_dir, update.get_repo())
        if self.docs.has_key(repo):
            return self.docs[repo]
        uinfo = join(repo, 'i386', 'repodata', 'updateinfo.xml.gz')
        if exists(uinfo):
            log.debug("Grabbing existing updateinfo: %s" % uinfo)
            uinfo = gzip.open(uinfo)
            doc = minidom.parse(uinfo)
            uinfo.close()
        else:
            log.debug("Creating new Document for updateinfo: %s" % uinfo)
            doc = minidom.Document()
            updates = doc.createElement('updates')
            doc.appendChild(updates)
        self.docs[repo] = [update.release, doc]
        return doc

    def _insert(self, doc, parent, name, attrs={}, text=None):
        """ Helper function to trivialize inserting an element into the doc """
        child = doc.createElement(name)
        for item in attrs.items():
            child.setAttribute(item[0], str(item[1]))
        if text:
            txtnode = doc.createTextNode(str(text))
            child.appendChild(txtnode)
        parent.appendChild(child)
        return child

    def _get_notice(self, doc, update):
        for elem in doc.getElementsByTagName('update'):
            for child in elem.childNodes:
                print child.toprettyxml()
                if child.nodeName == 'id' and \
                   child.firstChild.nodeValue == update.update_id:
                       return elem
        return None

    def remove_update(self, update):
        doc = self._get_updateinfo(update)
        elem = self._get_notice(doc, update)
        if elem:
            doc.firstChild.removeChild(elem)
            return True
        return False

    def add_update(self, update):
        """ Build the extended metdata for a given update """
        log.debug("Generating extended metadata for %s" % update.nvr)

        doc = self._get_updateinfo(update)

        ## Make sure this update doesn't already exist
        if self._get_notice(doc, update):
            log.debug("Update %s already in updateinfo" % update.nvr)
            return

        root = self._insert(doc, doc.firstChild, 'update', attrs={
                'type'      : update.type,
                'status'    : update.testing and 'testing' or 'final',
                'version'   : __version__,
                'from'      : 'updates@fedora.redhat.com'
        })
        self._insert(doc, root, 'id', text=update.update_id)
        self._insert(doc, root, 'title', text='%s Update: %s' % 
                     (update.release.long_name, update.nvr))
        self._insert(doc, root, 'issued', attrs={ 'date' : datetime.now() })
        #self._insert(doc, root, 'updated', attrs={ 'date' : datetime.now() })

        ## Build the references
        refs = doc.createElement('references')
        for cve in update.cves:
            self._insert(doc, refs, 'reference', attrs={
                    'type' : 'cve',
                    'href' : cve.get_url(),
                    'id'   : cve.cve_id
            })
        for bug in update.bugs:
            self._insert(doc, refs, 'reference', attrs={
                    'type' : 'bugzilla',
                    'href' : bug.get_url(),
                    'id'   : bug.bz_id
            })
        root.appendChild(refs)

        ## Errata description
        self._insert(doc, root, 'description', text=update.notes)

        ## The package list
        pkglist = doc.createElement('pkglist')
        collection = doc.createElement('collection')
        collection.setAttribute('short', update.release.name)
        self._insert(doc, collection, 'name', text=update.release.long_name)

        for arch in update.filelist.keys():
            for package in update.filelist[arch]:
                rpmhdr = util.rpm_fileheader(package)
                filename = basename(package)
                nvr = util.get_nvr(filename)
                pkg = self._insert(doc, collection, 'package', attrs={
                    'name'      : rpmhdr[rpm.RPMTAG_NAME],
                    'version'   : rpmhdr[rpm.RPMTAG_VERSION],
                    'release'   : rpmhdr[rpm.RPMTAG_RELEASE],
                    'epoch'     : rpmhdr[rpm.RPMTAG_EPOCH],
                    'arch'      : arch,
                    'src'       : FILE_URL % (update.testing and
                                              '-testing' or '',
                                              update.release.name[-1],
                                              arch, filename)
                })

                self._insert(doc, pkg, 'filename', text=filename)
                self._insert(doc, pkg, 'sum', attrs={'type':'sha1'},
                             text=util.sha1sum(package))

                ## TODO: add reboot_suggested field to Packages
                if nvr[0] in rebootpkgs:
                    self._insert(doc, pkg, 'reboot_suggested', text='True')

                collection.appendChild(pkg)

        pkglist.appendChild(collection)
        root.appendChild(pkglist)

    def insert_updateinfo(self):
        """ insert the updateinfo.xml.gz metadata into the repo """
        for (repo, data) in self.docs.items():
            for arch in data[0].arches:
                repomd = RepoMetadata(join(repo, arch.name, 'repodata'))
                repomd.add(data[1])
            log.debug("Inserted updateinfo.xml.gz into %s" % repo)
