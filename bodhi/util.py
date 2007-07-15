# $Id: util.py,v 1.2 2006/12/31 09:10:14 lmacken Exp $
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

"""
Random functions that don't fit elsewhere
"""

import os
import rpm
import sys
import time
import urllib
import logging
import traceback

from kid import Element
from koji import fixEncoding
from os.path import isdir, exists
from datetime import datetime
from turbogears import config, url
from bodhi.exceptions import RPMNotFound

## TODO: give createrepo a competent API
sys.path.append('/usr/share/createrepo')
import genpkgmetadata

log = logging.getLogger(__name__)

## Display a given message as a heading
header = lambda x: "%s\n     %s\n%s" % ('=' * 80, x, '=' * 80)

def rpm_fileheader(pkgpath):
    log.debug("Grabbing the rpm header of %s" % pkgpath)
    is_oldrpm = hasattr(rpm, 'opendb')
    try:
        fd = os.open(pkgpath,0)
        if is_oldrpm:
            h = rpm.headerFromPackage(fd)[0]
        else:
            ts = rpm.TransactionSet()
            h = ts.hdrFromFdno(fd)
            del ts
    except OSError:
        raise RPMNotFound
    os.close(fd)
    return h

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

def synchronized(lock):
    """ Synchronization decorator """
    def wrap(f):
        def new(*args, **kw):
            lock.acquire()
            try:
                return f(*args, **kw)
            finally:
                lock.release()
        return new
    return wrap

def displayname(identity):
    """
    Return the Full Name <email@address> of the current identity
    """
    return fixEncoding('%s %s' % (identity.current.user.display_name,
                                  hasattr(identity.current.user, 'user') and
                                  '<%s>' % identity.current.user.user['email']
                                  or ''))

def authorized_user(update, identity):
    return update.submitter == identity.current.user_name or \
           'releng' in identity.current.groups or \
           displayname(identity) == update.submitter

def make_update_link(obj):
    update = hasattr(obj, 'get_url') and obj or obj.update
    link = Element('a', href=url(update.get_url()))
    link.text = update.title
    return link

def make_type_icon(update):
    return Element('img', src=url('/static/images/%s.png' % update.type),
                   title=update.type)

def make_karma_icon(obj):
    return Element('img', src=url('/static/images/%d.png' % obj.karma))

def get_age(date):
    age = datetime.now() - date
    if age.days == 0:
        if age.seconds < 60:
            return "%d seconds" % age.seconds
        return "%d minutes" % int(age.seconds / 60)
    return "%s days" % age.days

def read_entire_file(uri):
    if (not "://" in uri): uri = "file://" + uri
    try:
        uri = urllib.urlopen(uri).read()
    except:
        log.warning("Couldn't read file \"%s\"." % (uri,))
        raise
    return uri

#
# Class for formatting errors. Hilights the bad line of code.
#
class _ErrorFormatter(object):

    #
    # Analyzes the given traceback and returns a developer-friendly error
    # output with markups.
    # If code is given, that string of code will be used as the source code,
    # instead of loading it.
    # If lineno is given, that number will be used as the linenumber. Only makes
    # sense together when code is given.
    # If deep_trace is True, the traceback history will be traversed as well.
    #
    def format(self, tb, code=None, lineno=-1, filename="", deep_trace=True):

        # tracebacks are dangerous objects; to avoid circular references,
        # we have to drop references to a traceback ASAP

        # get recent traceback
        exc_type = tb[0]
        exc_value = tb[1]
        exc_tb = tb[2]

        # get filename and lineno
        if (not filename and lineno == -1):
            if (hasattr(exc_value, "filename") and
                  hasattr(exc_value, "lineno")):
                filename = exc_value.filename
                lineno = exc_value.lineno
            else:
                tbs = traceback.extract_tb(exc_tb)
                filename = tbs[-1][0]
                lineno = tbs[-1][1]
                del tbs

        # print error message
        out = "\n"
        out += "[EXC]%s\n" % str(exc_value)

        # dig into the traceback for additional information
        if (deep_trace):
            for trace in traceback.extract_tb(exc_tb):
                cntxt = trace[0]
                lno = trace[1]
                funcname = trace[2]
                out += "in %s: line %d %s\n" % (cntxt, lno, funcname)

        # load code from file if no code was specified
        if (not code):
            # get last traceback (otherwise we would load the wrong file for
            # hilighting)
            this_tb = exc_tb
            while (this_tb.tb_next):
                tmp = this_tb
                del this_tb
                this_tb = tmp.tb_next
                del tmp

            # get the .py file; we don't want .pyc or .pyo!
            path = this_tb.tb_frame.f_globals.get("__file__")
            del this_tb
            if (path and path[-4:-1] == ".py"): path = path[:-1]

            if (path and exists(path)):
                code = read_entire_file(path)
                filename = path

        del exc_tb

        # find and hilight the bad line of code, while adding handy line numbers
        if (code):
            lines = code.splitlines()
            lno = 1
            for i in range(len(lines)):
                if (lno == lineno):
                    lines[i] = "[ERR]>%4d " % lno + lines[i]
                else:
                    lines[i] = "[---] %4d " % lno + lines[i]
                lno += 1

            # take a small chop out of the code
            begin = max(0, lineno - 6)
            part = lines[begin:begin + 12]

            out += "[EXC]%s\n\n" % filename
            out += "\n".join(part)
        else:
            out += "[EXC]%s\n\n" % filename
            out += "[EXC]>> could not load source code for hilighting <<"

        return out

#
# We are unable to load the source code if only a relative filename was
# available. Therefore, we have to extend the import handler in order to always
# give us an absolute path.
#
_old_imp = __import__
def _new_imp(name, globs = {}, locls = {}, fromlist = []):

    module = _old_imp(name, globs, locls, fromlist)
    # builtin modules have no "__file__" attribute, so we have to check for it
    if (module):
        if (hasattr(module, "__file__")):
            module.__file__ = os.path.abspath(module.__file__)
        return module
    else:
        return ""

import __builtin__
__builtin__.__import__ = _new_imp

_error_formatter_singleton = _ErrorFormatter()
def ErrorFormatter(): return _error_formatter_singleton
