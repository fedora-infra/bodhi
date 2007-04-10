# $Id: util.py,v 1.2 2006/12/31 09:10:14 lmacken Exp $
# Random functions that don't fit elsewhere.
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

import os
import rpm
import sys
import time
import logging

from os.path import isdir
from turbogears import config

sys.path.append('/usr/share/createrepo')
import genpkgmetadata

log = logging.getLogger(__name__)

def rpm_fileheader(pkgpath):
    is_oldrpm = hasattr(rpm, 'opendb')
    fd = os.open(pkgpath,0)
    try:
        if is_oldrpm:
            h = rpm.headerFromPackage(fd)[0]
        else:
            ts = rpm.TransactionSet()
            h = ts.hdrFromFdno(fd)
            del ts
    finally:
        os.close(fd)
    return h

def getChangeLog(header, timelimit=0):
    descrip = header[rpm.RPMTAG_CHANGELOGTEXT]
    if not descrip: return ""

    who = header[rpm.RPMTAG_CHANGELOGNAME]
    when = header[rpm.RPMTAG_CHANGELOGTIME]

    num = len(descrip)
    if num == 1: when = [when]

    str = ""
    i = 0
    while (i < num) and (when[i] > timelimit):
        str += '* %s %s\n%s\n' % (time.strftime("%a %b %e %Y",
                                  time.localtime(when[i])), who[i], descrip[i])
        i += 1
    return str

def excluded_arch(rpmheader, arch):
    """
    Determine if an RPM should be excluded from a given architecture, either
    if it is explicitly marked as ExcludeArch, or if it is Exclusive to another
    """
    excluded = rpmheader[rpm.RPMTAG_EXCLUDEARCH]
    exclusive = rpmheader[rpm.RPMTAG_EXCLUSIVEARCH]
    return (excluded and arch in excluded) or \
           (exclusive and arch not in exclusive)

def sha1sum(file):
    import sha
    fd = open(file)
    hash = sha.new(fd.read())
    fd.close()
    return hash.hexdigest()

def get_nvr(nvr):
    """ Return the [ name, version, release ] a given name-ver-rel. """
    x = nvr.split('-')
    return ['-'.join(x[:-2]), x[-2], x[-1]]

def mkmetadatadir(dir):
    """
    Generate package metadata for a given directory; if it doesn't exist, then
    create it.
    """
    log.debug("mkmetadatadir(%s)" % dir)
    if not isdir(dir):
        os.makedirs(dir)
    cache = config.get('createrepo_cache_dir')
    genpkgmetadata.main(['--cachedir', str(cache), '-q', str(dir)])
