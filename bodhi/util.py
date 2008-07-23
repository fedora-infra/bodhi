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
import urllib2
import tempfile
import simplejson
import subprocess
import urlgrabber
import turbogears

from kid import Element
from yum import repoMDObject
from yum.misc import checksum
from os.path import isdir, join, dirname, basename, isfile
from datetime import datetime
from turbogears import config, url, flash

from bodhi.exceptions import RPMNotFound, RepodataException


log = logging.getLogger(__name__)

## Display a given message as a heading
header = lambda x: "%s\n     %s\n%s\n" % ('=' * 80, x, '=' * 80)

pluralize = lambda val, name: val == 1 and name or "%ss" % name

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
    try:
        import createrepo
        conf = createrepo.MetaDataConfig()
        conf.cachedir = cache
        conf.outputdir = dir
        conf.directory = dir
        conf.quiet = True
        mdgen = createrepo.MetaDataGenerator(conf)
        mdgen.doPkgMetadata()
        mdgen.doRepoMetadata()
        mdgen.doFinalMove()
    except ImportError:
        sys.path.append('/usr/share/createrepo')
        import genpkgmetadata
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

def authorized_user(update, identity):
    return 'releng' in identity.current.groups or \
           'cvsadmin' in identity.current.groups or \
           'security_respons' in identity.current.groups or \
           identity.current.user_name == update.submitter or \
           identity.current.user_name in update.get_maintainers()

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

def make_request_icon(update):
    return Element('img', src=url('/static/images/%s-large.png' %
                   update.request), title=str(update.request))

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
            return "%d %s" % (age.seconds, pluralize(age.seconds, "second"))
        minutes = int(age.seconds / 60)
        if minutes >= 60:
            hours = int(minutes/60)
            return "%d %s" % (hours, pluralize(hours, "hour"))
        return "%d %s" % (minutes, pluralize(minutes, "minute"))
    return "%d %s" % (age.days, pluralize(age.days, "day"))

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

def get_pkg_pushers(pkgName, collectionName='Fedora', collectionVersion='devel'):
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
    if config.get('acl_system') == 'dummy':
        return (['guest'], ['guest']), (['guest'], ['guest'])

    pkgPage = None
    pkgPage = urllib2.urlopen(config.get('pkgdb_url') +
                              '/packages/name/%s/%s/%s?tg_format=json' % (
                              pkgName, collectionName, collectionVersion))

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

def link(text, href):
    return '<a href="%s">%s</a>' % (url(href), text)

def load_config(configfile=None):
    """ Load bodhi's configuration """
    setupdir = os.path.dirname(os.path.dirname(__file__))
    curdir = os.getcwd()
    if configfile and os.path.exists(configfile):
        pass
    elif os.path.exists(os.path.join(setupdir, 'setup.py')) \
            and os.path.exists(os.path.join(setupdir, 'dev.cfg')):
        configfile = os.path.join(setupdir, 'dev.cfg')
    elif os.path.exists(os.path.join(curdir, 'bodhi.cfg')):
        configfile = os.path.join(curdir, 'bodhi.cfg')
    elif os.path.exists('/etc/bodhi.cfg'):
        configfile = '/etc/bodhi.cfg'
    elif os.path.exists('/etc/bodhi/bodhi.cfg'):
        configfile = '/etc/bodhi.cfg'
    else:
        log.error("Unable to find configuration to load!")
        return
    turbogears.update_config(configfile=configfile, modulename="bodhi.config")

class Singleton(object):

    def __new__(cls, *args, **kw):
        if not '_instance' in cls.__dict__:
            cls._instance = object.__new__(cls)
        return cls._instance


class ProgressBar(object):
    """ Creates a text-based progress bar """

    def __init__(self, minValue=0, maxValue=100, totalWidth=80):
        self.progBar = "[]"   # This holds the progress bar string
        self.min = minValue
        self.max = maxValue
        self.span = maxValue - minValue
        self.width = totalWidth
        self.amount = 0       # When amount == max, we are 100% done 
        self.updateAmount(0)  # Build progress bar string

    def updateAmount(self, newAmount=0):
        if newAmount < self.min: newAmount = self.min
        if newAmount > self.max: newAmount = self.max
        self.amount = newAmount

        # Figure out the new percent done, round to an integer
        diffFromMin = float(self.amount - self.min)
        percentDone = (diffFromMin / float(self.span)) * 100.0
        percentDone = int(round(percentDone))

        # Figure out how many hash bars the percentage should be
        allFull = self.width - 2
        numHashes = (percentDone / 100.0) * allFull
        numHashes = int(round(numHashes))

        # Build a progress bar with an arrow of equal signs; special cases for
        # empty and full
        if numHashes == 0:
            self.progBar = "[>%s]" % (' '*(allFull-1))
        elif numHashes == allFull:
            self.progBar = "[%s]" % ('='*allFull)
        else:
            self.progBar = "[%s>%s]" % ('='*(numHashes-1),
                                        ' '*(allFull-numHashes))

        # figure out where to put the percentage, roughly centered
        percentPlace = (len(self.progBar) / 2) - len(str(percentDone)) 
        percentString = str(percentDone) + "%"

        # slice the percentage into the bar
        self.progBar = ''.join([self.progBar[0:percentPlace], percentString,
                                self.progBar[percentPlace+len(percentString):]])

    def __str__(self):
        return str(self.progBar)

    def __call__(self, value=None):
        print '\r',
        if not value:
            value = self.amount + 1
        self.updateAmount(value)
        sys.stdout.write(str(self))
        sys.stdout.flush()


def sanity_check_repodata(myurl):
    """
    Sanity check the repodata for a given repository.
    Initial implementation by Seth Vidal.
    """
    tempdir = tempfile.mkdtemp()
    errorstrings = []
    if myurl[-1] != '/':
        myurl += '/'
    baseurl = myurl
    if not myurl.endswith('repodata/'):
        myurl += 'repodata/'
    else:
        baseurl = baseurl.replace('repodata/', '/')
    
    rf = myurl + 'repomd.xml'
    try:
        rm = urlgrabber.urlopen(rf)
        repomd = repoMDObject.RepoMD('foo', rm)
        for t in repomd.fileTypes():
            data = repomd.getData(t)
            base, href = data.location
            if base:
                loc = base + '/' + href
            else:
                loc = baseurl + href

            destfn = tempdir + '/' + os.path.basename(href)
            dest =  urlgrabber.urlgrab(loc, destfn)
            ctype, known_csum = data.checksum
            csum = checksum(ctype, dest)
            if csum != known_csum:
                errorstrings.append("checksum: %s" % t)

            if href.find('xml') != -1:
                retcode = subprocess.call(['/usr/bin/xmllint', '--noout', dest])
                if retcode != 0:
                    errorstrings.append("failed xml read: %s" % t)

    except urlgrabber.grabber.URLGrabError, e:
        errorstrings.append('Error accessing repository %s' % e)
    
    if errorstrings:
        raise RepodataException(','.join(errorstrings))
