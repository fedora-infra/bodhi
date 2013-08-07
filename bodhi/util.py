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
import collections
import functools


from yum import repoMDObject
from yum.misc import checksum
from os.path import isdir, join, dirname, basename, isfile
from datetime import datetime

from fedora.client import PackageDB
from sqlalchemy import create_engine
from pyramid.i18n import TranslationStringFactory
from pyramid.threadlocal import get_current_request

from .exceptions import (RPMNotFound, RepodataException,
                         InvalidUpdateException)

from bodhi.config import config


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


def build_evr(build):
    if not build['epoch']:
        build['epoch'] = 0
    return (str(build['epoch']), build['version'], build['release'])


def link(text, href):
    return '<a href="%s">%s</a>' % (url(href), text)


class memoized(object):
    '''Decorator. Caches a function's return value each time it is called.  If
    called later with the same arguments, the cached value is returned (not
    reevaluated).

    http://wiki.python.org/moin/PythonDecoratorLibrary#Memoize
    '''
    def __init__(self, func):
        self.func = func
        self.cache = {}

    def __call__(self, *args):
        if not isinstance(args, collections.Hashable):
            # uncacheable. a list, for instance.
            # better to not cache than blow up.
            return self.func(*args)
        if args in self.cache:
            return self.cache[args]
        else:
            value = self.func(*args)
            self.cache[args] = value
            return value

    def __repr__(self):
        '''Return the function's docstring.'''
        return self.func.__doc__

    def __get__(self, obj, objtype):
        '''Support instance methods.'''
        return functools.partial(self.__call__, obj)


def get_db_from_config(dev=False):
    from .models import DBSession, Base
    if dev:
        db_url = 'sqlite:///:memory:'
    else:
        db_url = config['sqlalchemy.url']
    engine = create_engine(db_url)
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine
    Base.metadata.create_all(engine)
    return DBSession()


@memoized
def get_critpath_pkgs(collection='devel'):
    """Return a list of critical path packages for a given collection"""
    critpath_type = config.get('critpath.type', 'pkgdb')
    if critpath_type == 'pkgdb':
        pkgdb = PackageDB(config.get('pkgdb_url'))
        critpath_pkgs = pkgdb.get_critpath_pkgs([collection])
        critpath_pkgs = getattr(critpath_pkgs, collection, [])
        # Fallback to rawhide's critpath list
        if not critpath_pkgs:
            critpath_pkgs = pkgdb.get_critpath_pkgs(['devel'])
            critpath_pkgs = getattr(critpath_pkgs, 'devel', [])
    else:
        critpath_pkgs = config.get('critpath_pkgs', [])
    return critpath_pkgs


class Singleton(object):

    def __new__(cls, *args, **kw):
        if not '_instance' in cls.__dict__:
            cls._instance = object.__new__(cls)
        return cls._instance


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
