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
import tempfile
import subprocess
import urlgrabber
#import turbogears

from yum import repoMDObject
from yum.misc import checksum
from os.path import isdir, join, dirname, basename, isfile
from datetime import datetime
from decorator import decorator
#from turbogears import config, flash, redirect, url as tg_url
#from fedora.tg.util import request_format
from fedora.client import PackageDB
#from fedora.tg.util import url as csrf_url

from bodhi.exceptions import (RPMNotFound, RepodataException,
                              InvalidUpdateException)

from pyramid.i18n import TranslationStringFactory
from pyramid.threadlocal import get_current_request

_ = TranslationStringFactory('bodhi')
log = logging.getLogger(__name__)

## Display a given message as a heading
header = lambda x: u"%s\n     %s\n%s\n" % ('=' * 80, x, '=' * 80)

pluralize = lambda val, name: val == 1 and name or "%ss" % name


def rpm_fileheader(pkgpath):
    log.debug("Grabbing the rpm header of %s" % pkgpath)
    is_oldrpm = hasattr(rpm, 'opendb')
    try:
        fd = os.open(pkgpath, 0)
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
    # FIXME: port to pyramid auth
    return True
    return 'releng' in identity.current.groups or \
           'cvsadmin' in identity.current.groups or \
           'security_respons' in identity.current.groups or \
           identity.current.user_name == update.submitter or \
           identity.current.user_name in update.get_maintainers()


def make_update_link(obj):
    """ Return a link Element for a given PackageUpdate or PackageBuild """
    from kid import Element
    update = None
    if hasattr(obj, 'updates'):    # Package or PackageBuild
        update = obj.updates[0]
    elif hasattr(obj, 'get_url'):  # PackageUpdate
        update = obj
    elif hasattr(obj, 'update'):   # Comment
        update = obj.update
    else:
        log.error("Unknown parameter make_update_link(%s)" % obj)
        return None
    link = Element('a', href=url(update.get_url()))
    link.text = update.get_title(', ')
    return link


def make_type_icon(update):
    from kid import Element
    return Element('img', src=url('/static/images/%s.png' % update.type),
                   title=update.type)


def make_request_icon(update):
    from kid import Element
    return Element('img', src=url('/static/images/%s-large.png' %
                   update.request), title=str(update.request))


def make_karma_icon(update):
    if update.karma < 0:
        karma = -1
    elif update.karma > 0:
        karma = 1
    else:
        karma = 0
    from kid import Element
    return Element('img', src=url('/static/images/karma%d.png' % karma))


def get_age(date):
    age = datetime.utcnow() - date
    if age.days == 0:
        if age.seconds < 60:
            return "%d %s" % (age.seconds, pluralize(age.seconds, "second"))
        minutes = int(age.seconds / 60)
        if minutes >= 60:
            hours = int(minutes / 60)
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
    # FIXME: request.session.flash()
    #flash(msg)
    log.debug(msg)


def get_release_names():
    from bodhi.tools.init import releases
    return [release['long_name'] for release in releases]


def get_release_tuples():
    from bodhi.tools.init import releases
    names = []
    for release in releases:
        names.append(release['name'])
        names.append(release['long_name'])
    return names


def get_repo_tag(repo):
    """ Pull the koji tag from the given mash repo """
    mashconfig = join(dirname(config.get('mash_conf')),
                      basename(repo) + '.mash')
    if isfile(mashconfig):
        mashconfig = file(mashconfig, 'r')
        lines = mashconfig.readlines()
        mashconfig.close()
        return filter(lambda x: x.startswith('tag ='), lines)[0].split()[-1]
    else:
        log.error("Cannot find mash configuration for %s: %s" % (repo,
                                                                 mashconfig))


def get_pkg_pushers(pkgName, collectionName='Fedora',
                    collectionVersion='devel'):
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

    This may raise: fedora.client.AppError if there's an error talking to the
    PackageDB (for instance, no such package)
    """
    request = get_current_request()
    settings = request.registry.settings
    if request.registry.settings['acl_system'] == 'dummy':
        return (['guest'], ['guest']), (['guest'], ['guest'])

    pkgdb = PackageDB(settings['pkgdb_url'])
    # Note if AppError is raised (for no pkgNamme or other server errors) we
    # do not catch the exception here.
    pkg = pkgdb.get_owners(pkgName, collectionName, collectionVersion)

    # Owner is allowed to commit and gets notified of pushes
    # This will always be the 0th element as we'll retrieve at most one
    # value for any given Package-Collection-Version
    pNotify = [pkg.packageListings[0]['owner']]
    pAllowed = [pNotify[0]]

    # Find other people in the acl
    for person in pkg['packageListings'][0]['people']:
        if person['aclOrder']['watchcommits'] and \
           pkg['statusMap'][str(person['aclOrder']['watchcommits']['statuscode'])] == 'Approved':
            pNotify.append(person['username'])
        if person['aclOrder']['commit'] and \
           pkg['statusMap'][str(person['aclOrder']['commit']['statuscode'])] == 'Approved':
            pAllowed.append(person['username'])

    # Find groups that can push
    gNotify = []
    gAllowed = []
    for group in pkg['packageListings'][0]['groups']:
        if group['aclOrder']['watchcommits'] and \
           pkg['statusMap'][str(group['aclOrder']['watchcommits']['statuscode'])] == 'Approved':
            gNotify.append(group['groupname'])
        if group['aclOrder']['commit'] and \
           pkg['statusMap'][str(group['aclOrder']['commit']['statuscode'])] == 'Approved':
            gAllowed.append(group['groupname'])

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
        configfile = '/etc/bodhi/bodhi.cfg'
    else:
        log.error("Unable to find configuration to load!")
        return
    log.debug("Loading configuration: %s" % configfile)
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
        if newAmount < self.min:
            newAmount = self.min

        if newAmount > self.max:
            newAmount = self.max

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
            self.progBar = "[>%s]" % (' ' * (allFull - 1))
        elif numHashes == allFull:
            self.progBar = "[%s]" % ('=' * allFull)
        else:
            self.progBar = "[%s>%s]" % ('=' * (numHashes - 1),
                                        ' ' * (allFull - numHashes))

        # figure out where to put the percentage, roughly centered
        percentPlace = (len(self.progBar) / 2) - len(str(percentDone))
        percentString = str(percentDone) + "%"

        # slice the percentage into the bar
        self.progBar = ''.join(
            [self.progBar[0:percentPlace], percentString,
             self.progBar[percentPlace + len(percentString):]])

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
            dest = urlgrabber.urlgrab(loc, destfn)
            ctype, known_csum = data.checksum
            csum = checksum(ctype, dest)
            if csum != known_csum:
                errorstrings.append("checksum: %s" % t)

            if href.find('xml') != -1:
                retcode = subprocess.call(
                    ['/usr/bin/xmllint', '--noout', dest])
                if retcode != 0:
                    errorstrings.append("failed xml read: %s" % t)

    except urlgrabber.grabber.URLGrabError, e:
        errorstrings.append('Error accessing repository %s' % e)

    if errorstrings:
        raise RepodataException(','.join(errorstrings))

    updateinfo = os.path.join(myurl, 'updateinfo.xml.gz')
    if os.path.exists(updateinfo):
        ret = subprocess.call(['zgrep', '<id/>', updateinfo])
        if not ret:
            raise RepodataException('updateinfo.xml.gz contains empty ID tags')


def to_unicode(obj, encoding='utf-8'):
    if isinstance(obj, basestring):
        if not isinstance(obj, unicode):
            obj = unicode(obj, encoding, 'replace')
    return obj


@decorator
def json_redirect(f, *args, **kw):
    try:
        return f(*args, **kw)
    except InvalidUpdateException, e:
        if request_format() == 'json':
            return dict()
        else:
            raise redirect('/new', **e.args[0])


"""
Misc iPython hacks that I've had to write at one point or another
"""


def reset_date_pushed(status='testing'):
    """
    Reset the date_pushed on all testing updates with the most recent bodhi
    comment that relates to it's current status.

    This needed to happen when a few batches of updates were pushed without
    a date_pushed field, so we had to recreate it based on bodhi's comments.
    """
    from bodhi.model import PackageUpdate
    from sqlobject import AND
    for update in PackageUpdate.select(AND(PackageUpdate.q.date_pushed == None,
                                           PackageUpdate.q.status == status)):
        date = None
        for comment in update.comments:
            if comment.author == 'bodhi':
                if comment.text == 'This update has been pushed to %s' % update.status:
                    if date and comment.timestamp < date:
                        print "Skipping older push %s for %s" % (comment.timestamp, update.title)
                    else:
                        date = comment.timestamp
                        print "Setting %s to %s" % (update.title, comment.timestamp)
                        update.date_pushed = date


def testing_statistics():
    """ Calculate and display various testing statistics """
    from datetime import timedelta
    from bodhi.model import PackageUpdate

    deltas = []
    occurrences = {}
    accumulative = timedelta()

    for update in PackageUpdate.select():
        for comment in update.comments:
            if comment.text == 'This update has been pushed to testing':
                for othercomment in update.comments:
                    if othercomment.text == 'This update has been pushed to stable':
                        delta = othercomment.timestamp - comment.timestamp
                        deltas.append(delta)
                        occurrences[delta.days] = occurrences.setdefault(delta.days, 0) + 1
                        accumulative += deltas[-1]
                        break
                break

    deltas.sort()
    all = PackageUpdate.select().count()
    percentage = int(float(len(deltas)) / float(all) * 100)
    mode = sorted(occurrences.items(), cmp=lambda x, y: cmp(x[1], y[1]))[-1][0]

    print "%d out of %d updates went through testing (%d%%)" % (len(deltas), all, percentage)
    print "mean = %d days" % (accumulative.days / len(deltas))
    print "median = %d days" % deltas[len(deltas) / 2].days
    print "mode = %d days" % mode


def url(*args, **kw):
    if config.get('identity.provider') in ('sqlobjectcsrf', 'jsonfas2'):
        return csrf_url(*args, **kw)
    else:
        return tg_url(*args, **kw)
