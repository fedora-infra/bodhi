#!/usr/bin/env python
# $Id: modifyrepo.py,v 1.1 2006/12/07 07:19:41 lmacken Exp $
#
# This tools is used to insert arbitrary metadata into an RPM repository.
# Example:
#           ./modifyrepo.py updateinfo.xml myrepo/repodata
# or in Python:
#           >>> from modifyrepo import RepoMetadata
#           >>> repomd = RepoMetadata('myrepo/repodata')
#           >>> repomd.add('updateinfo.xml')
#
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
# Luke Macken <lmacken@redhat.com>

"""
    This tool is in CVS HEAD of createrepo 
"""

import os
import sys
import sha
import gzip

from xml.dom import minidom

class RepoMetadata:

    def __init__(self, repo):
        """ Parses the repomd.xml file existing in the given repo directory. """
        self.repodir = os.path.abspath(repo)
        self.repomdxml = os.path.join(self.repodir, 'repomd.xml')
        if not os.path.exists(self.repomdxml):
            raise Exception('%s not found' % self.repomdxml)
        self.doc = minidom.parse(self.repomdxml)

    def _insert_element(self, parent, name, attrs={}, text=None):
        child = self.doc.createElement(name)
        for item in attrs.items():
            child.setAttribute(item[0], item[1])
        if text:
            txtnode = self.doc.createTextNode(text)
            child.appendChild(txtnode)
        parent.appendChild(child)
        return child

    def add(self, metadata):
        """ Insert arbitrary metadata into this repository.
            metadata can be either an xml.dom.minidom.Document object, or
            a filename.
        """
        md = None
        if not metadata:
            raise Exception('metadata cannot be None')
        if isinstance(metadata, minidom.Document):
            md = metadata.toxml()
            mdname = 'updateinfo.xml'
        elif isinstance(metadata, str):
            if os.path.exists(metadata):
                oldmd = file(metadata, 'r')
                md = oldmd.read()
                oldmd.close()
                mdname = os.path.basename(metadata)
            else:
                raise Exception('%s not found' % metadata)
        else:
            raise Exception('invalid metadata type')

        ## Compress the metadata and move it into the repodata
        mdname += '.gz'
        mdtype = mdname.split('.')[0]
        destmd = os.path.join(self.repodir, mdname)
        newmd = gzip.GzipFile(destmd, 'wb')
        newmd.write(md)
        newmd.close()
        print "Wrote:", destmd

        ## Read the gzipped metadata
        f = file(destmd, 'r')
        newmd = f.read()
        f.close()

        ## Remove any stale metadata
        for elem in self.doc.getElementsByTagName('data'):
            if elem.attributes['type'].value == mdtype:
                self.doc.firstChild.removeChild(elem) 
        ## Build the metadata
        root = self.doc.firstChild
        data = self._insert_element(root, 'data', attrs={ 'type' : mdtype })
        self._insert_element(data, 'location',
                             attrs={ 'href' : 'repodata/' + mdname })
        self._insert_element(data, 'checksum', attrs={ 'type' : 'sha' },
                             text=sha.new(newmd).hexdigest())
        self._insert_element(data, 'timestamp',
                             text=str(os.stat(destmd).st_mtime))
        self._insert_element(data, 'open-checksum', attrs={ 'type' : 'sha' },
                             text=sha.new(md).hexdigest())

        print "           type =", mdtype 
        print "       location =", 'repodata/' + mdname
        print "       checksum =", sha.new(newmd).hexdigest()
        print "      timestamp =", str(os.stat(destmd).st_mtime)
        print "  open-checksum =", sha.new(md).hexdigest()

        ## Write the updated repomd.xml
        outmd = file(self.repomdxml, 'w')
        self.doc.writexml(outmd)
        outmd.close()
        print "Wrote:", self.repomdxml


if __name__ == '__main__':
    if len(sys.argv) != 3 or '-h' in sys.argv:
        print "Usage: %s <input metadata> <output repodata>" % sys.argv[0]
        sys.exit()

    repomd = RepoMetadata(sys.argv[2])
    repomd.add(sys.argv[1])
