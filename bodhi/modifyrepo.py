#!/usr/bin/env python
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
# (C) Copyright 2006  Red Hat, Inc.
# Luke Macken <lmacken@redhat.com>
# modified by Seth Vidal 2008

import os
import sys

from createrepo.utils import checksum_and_rename, GzipFile, MDError
from yum.misc import checksum

from xml.dom import minidom


class RepoMetadata:

    def __init__(self, repo):
        """ Parses the repomd.xml file existing in the given repo directory. """
        self.repodir = os.path.abspath(repo)
        self.repomdxml = os.path.join(self.repodir, 'repomd.xml')
        self.checksum_type = 'sha256'
        if not os.path.exists(self.repomdxml):
            raise MDError, '%s not found' % self.repomdxml
        self.doc = minidom.parse(self.repomdxml)

    def _insert_element(self, parent, name, attrs=None, text=None):
        child = self.doc.createElement(name)
        if not attrs:
            attrs = {}
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
            raise MDError, 'metadata cannot be None'
        if isinstance(metadata, minidom.Document):
            md = metadata.toxml()
            mdname = 'updateinfo.xml'
        elif isinstance(metadata, str):
            if os.path.exists(metadata):
                if metadata.endswith('.gz'):
                    oldmd = GzipFile(filename=metadata, mode='rb')
                else:
                    oldmd = file(metadata, 'r')
                md = oldmd.read()
                oldmd.close()
                mdname = os.path.basename(metadata)
            else:
                raise MDError, '%s not found' % metadata
        else:
            raise MDError, 'invalid metadata type'

        ## Compress the metadata and move it into the repodata
        if not mdname.endswith('.gz'):
            mdname += '.gz'
        mdtype = mdname.split('.')[0]
        destmd = os.path.join(self.repodir, mdname)
        newmd = GzipFile(filename=destmd, mode='wb')
        newmd.write(md)
        newmd.close()
        print "Wrote:", destmd

        open_csum = checksum(self.checksum_type, metadata)


        csum, destmd = checksum_and_rename(destmd, self.checksum_type)
        base_destmd = os.path.basename(destmd)
        

        ## Remove any stale metadata
        for elem in self.doc.getElementsByTagName('data'):
            if elem.attributes['type'].value == mdtype:
                self.doc.firstChild.removeChild(elem)

        ## Build the metadata
        root = self.doc.firstChild
        root.appendChild(self.doc.createTextNode("  "))
        data = self._insert_element(root, 'data', attrs={ 'type' : mdtype })
        data.appendChild(self.doc.createTextNode("\n    "))

        self._insert_element(data, 'location',
                             attrs={ 'href' : 'repodata/' + base_destmd })
        data.appendChild(self.doc.createTextNode("\n    "))
        self._insert_element(data, 'checksum', 
                             attrs={ 'type' : self.checksum_type }, 
                             text=csum)
        data.appendChild(self.doc.createTextNode("\n    "))
        self._insert_element(data, 'timestamp',
                             text=str(os.stat(destmd).st_mtime))
        data.appendChild(self.doc.createTextNode("\n    "))
        self._insert_element(data, 'open-checksum', 
                             attrs={ 'type' : self.checksum_type },
                             text=open_csum)

        data.appendChild(self.doc.createTextNode("\n  "))
        root.appendChild(self.doc.createTextNode("\n"))

        print "           type =", mdtype 
        print "       location =", 'repodata/' + mdname
        print "       checksum =", csum
        print "      timestamp =", str(os.stat(destmd).st_mtime)
        print "  open-checksum =", open_csum

        ## Write the updated repomd.xml
        outmd = file(self.repomdxml, 'w')
        self.doc.writexml(outmd)
        outmd.write("\n")
        outmd.close()
        print "Wrote:", self.repomdxml


if __name__ == '__main__':
    if len(sys.argv) != 3 or '-h' in sys.argv:
        print "Usage: %s <input metadata> <output repodata>" % sys.argv[0]
        sys.exit()
    try:
        repomd = RepoMetadata(sys.argv[2])
    except MDError, e:
        print "Could not access repository: %s" % str(e)
        sys.exit(1)
    try:
        repomd.add(sys.argv[1])
    except MDError, e:
        print "Could not add metadata from file %s: %s" % (sys.argv[1], str(e))
        sys.exit(1)

