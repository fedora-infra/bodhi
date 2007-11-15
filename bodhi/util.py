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
import logging
import simplejson
import urllib2

from kid import Element
from os.path import isdir, join, dirname, basename, isfile
from datetime import datetime
from turbogears import config, url, flash
from bodhi.exceptions import RPMNotFound

## TODO: give createrepo a competent API
sys.path.append('/usr/share/createrepo')
import genpkgmetadata

log = logging.getLogger(__name__)

## Display a given message as a heading
header = lambda x: "%s\n     %s\n%s\n" % ('=' * 80, x, '=' * 80)

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
    except (OSError, TypeError):
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
    return '%s %s' % (identity.current.user.display_name,
                      hasattr(identity.current.user, 'user') and
                      '<%s>' % identity.current.user.user['email'] or '')

def authorized_user(update, identity):
    return update.submitter == identity.current.user_name or \
           'releng' in identity.current.groups or \
           'security_respons' in identity.current.groups or \
           displayname(identity) == update.submitter

def make_update_link(obj):
    """ Return a link Element for a given PackageUpdate or PackageBuild """
    update = None
    if hasattr(obj, 'get_url'):   # PackageUpdate
        update = obj
    elif hasattr(obj, 'update'):  # Comment
        update = obj.update
    elif hasattr(obj, 'updates'): # Package
        update = obj.updates[0]
    else:
        log.error("Unknown parameter make_update_link(%s)" % obj)
        return None
    link = Element('a', href=url(update.get_url()))
    link.text = update.get_title(', ')
    return link

def make_type_icon(update):
    return Element('img', src=url('/static/images/%s.png' % update.type),
                   title=update.type)

def make_karma_icon(update):
    if update.karma < 0:
        karma = -1
    elif update.karma > 0:
        karma = 1
    else:
        karma = 0
    return Element('img', src=url('/static/images/karma%d.png' % karma))

def get_age(date):
    age = datetime.utcnow() - date
    if age.days == 0:
        if age.seconds < 60:
            return "%d seconds" % age.seconds
        return "%d minutes" % int(age.seconds / 60)
    return "%s days" % age.days

def get_age_in_days(date):
    if date:
        age = datetime.utcnow() - date
        return age.days
    else:
        return 0

def flash_log(msg):
    """ Flash and log a given message """
    flash(msg)
    log.debug(msg)

def get_release_names():
    from bodhi.tools.init import releases
    return map(lambda release: release['long_name'], releases)

def get_release_tuples():
    from bodhi.tools.init import releases
    names = []
    for release in releases:
        names.append(release['name'])
        names.append(release['long_name'])
    return names

def get_repo_tag(repo):
    """ Pull the koji tag from the given mash repo """
    mashconfig = join(dirname(config.get('mash_conf')), basename(repo)+'.mash')
    if isfile(mashconfig):
        mashconfig = file(mashconfig, 'r')
        lines = mashconfig.readlines()
        mashconfig.close()
        return filter(lambda x: x.startswith('tag ='), lines)[0].split()[-1]
    else:
        log.error("Cannot find mash configuration for %s: %s" % (repo,
                                                                 mashconfig))

def get_pkg_pushers(pkgName, collectionName, collectionVersion):
    """ Pull users who can commit and are watching a package

    Return two two-tuples of lists:
    * The first tuple is for usernames.  The second tuple is for groups.
    * The first list of the tuple is for committers.  The second is for
      watchers.

    An example::
      >>> people, groups = get_pkg_pushers('foo', 'Fedora', 'devel')
      >>> print people
      (['toshio', 'lmacken'], ['wtogami', 'toshio', 'lmacken'])
      >>> print groups
      (['cvsextras'], [])

    Note: The interface to the pkgdb could undergo the following changes:
      FAS2 related:
      * pkg['packageListings'][0]['owneruser'] =>
        pkg['packageListings'][0]['owner']
      * pkg['packageListings'][0]['people'][0..n]['user'] =>
        pkg['packageListings'][0]['people'][0..n]['userid']

    * We may want to create a 'push' acl specifically for bodhi instead of
      reusing 'commit'.
    * ['status']['translations'] may one day contain more than the 'C'
      translation.  The pkgdb will have to figure out how to deal with that
      if so.
    """
    pkgPage = None
    try:
        pkgPage = urllib2.urlopen(config.get('pkgdb_url') +
                                  '/packages/name/%s/%s/%s?tg_format=json' % (
                                  pkgName, collectionName, collectionVersion))
    except urllib2.URLError:
        log.error("Cannot connect to pkgdb")
        raise

    pkg = simplejson.load(pkgPage)
    if pkg.has_key('status') and not pkg['status']:
        raise Exception, 'Package %s not found in PackageDB.  Error: %s' % (
                pkgName, pkg['message'])

    # Owner is allowed to commit and gets notified of pushes
    # This will always be the 0th element as we'll retrieve at most one
    # value for any given Package-Collection-Version
    pNotify = [pkg['packageListings'][0]['owneruser']]
    pAllowed = [pNotify[0]]

    # Find other people in the acl
    for person in pkg['packageListings'][0]['people']:
        if person['aclOrder']['watchcommits'] and \
           pkg['statusMap'][str(person['aclOrder']['watchcommits']['statuscode'])] == 'Approved':
            pNotify.append(person['user'])
        if person['aclOrder']['commit'] and \
           pkg['statusMap'][str(person['aclOrder']['commit']['statuscode'])] == 'Approved':
            pAllowed.append(person['user'])

    # Find groups that can push
    gNotify = []
    gAllowed = []
    for group in pkg['packageListings'][0]['groups']:
        if group['aclOrder']['watchcommits'] and \
           pkg['statusMap'][str(group['aclOrder']['watchcommits']['statuscode'])] == 'Approved':
            gNotify.append(group['name'])
        if group['aclOrder']['commit'] and \
           pkg['statusMap'][str(group['aclOrder']['commit']['statuscode'])] == 'Approved':
            gAllowed.append(group['name'])

    return ((pAllowed, pNotify), (gAllowed, gNotify))

def build_evr(build):
    if not build['epoch']:
        build['epoch'] = 0
    return (str(build['epoch']), build['version'], build['release'])
