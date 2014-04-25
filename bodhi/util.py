"""
Random functions that don't fit elsewhere
"""

import os
import sys
import arrow
import socket
import tempfile
import markdown
import subprocess
import libravatar
import collections
import pkg_resources
import functools


from os.path import isdir, join, dirname, basename, isfile
from datetime import datetime

from fedora.client import PackageDB
from sqlalchemy import create_engine
from pyramid.i18n import TranslationStringFactory

from . import log
from .exceptions import RPMNotFound, RepodataException
from .config import config

try:
    import rpm
except ImportError:
    log.warning("Could not import 'rpm'")

try:
    import yum
    import yum.misc
except ImportError:
    log.warning("Could not import 'yum'")


_ = TranslationStringFactory('bodhi')

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


def link(href, text):
    return '<a href="%s">%s</a>' % (href, text)


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
    critpath_type = config.get('critpath.type')
    if critpath_type == 'pkgdb':
        pkgdb = PackageDB(config.get('pkgdb_url'))
        critpath_pkgs = pkgdb.get_critpath_pkgs([collection])
        critpath_pkgs = getattr(critpath_pkgs, collection, [])
        # Fallback to rawhide's critpath list
        if not critpath_pkgs:
            critpath_pkgs = pkgdb.get_critpath_pkgs(['devel'])
            critpath_pkgs = getattr(critpath_pkgs, 'devel', [])
    else:
        critpath_pkgs = config.get('critpath_pkgs', '').split()
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

    import urlgrabber

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
        repomd = yum.repoMDObject.RepoMD('foo', rm)
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
            csum = yum.misc.checksum(ctype, dest)
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


def age(context, date):
    return arrow.get(date).humanize()


def avatar(context, username, size):
    # context is a mako context object
    request = context['request']

    @request.cache.cache_on_arguments()
    def work(username, size):
        https = request.registry.settings.get('prefer_ssl'),
        openid = "http://%s.id.fedoraproject.org/" % username
        return libravatar.libravatar_url(
            openid=openid,
            https=https,
            size=size,
            default='retro',
        )

    return work(username, size)


def version(context):
    return pkg_resources.get_distribution('bodhi').version


def hostname(context):
    return socket.gethostname()


def markup(context, text):
    return markdown.markdown(text)


def status2html(context, status):
    status = unicode(status)
    cls = {
        'pending': 'primary',
        'testing': 'warning',
        'stable': 'success',
        'unpushed': 'danger',
        'obsolete': 'default',
        'processing': 'info',
    }[status]
    return "<span class='label label-%s'>%s</span>" % (cls, status)


def karma2html(context, karma):
    cls = {
        -2: 'danger',
        -1: 'warning',
        0: 'info',
        1: 'primary',
        2: 'success',
    }.get(karma)

    if not cls:
        if karma < -2:
            cls = 'danger'
        else:
            cls = 'success'

    if karma > 0:
        karma = "+%i" % karma
    else:
        karma = "%i" % karma

    return "<span class='label label-%s'>%s</span>" % (cls, karma)


def type2html(context, kind):
    kind = unicode(kind)
    cls = {
        'security': 'danger',
        'bugfix': 'warning',
        'newpackage': 'primary',
        'enhancement': 'success',
    }.get(kind)

    return "<span class='label label-%s'>%s</span>" % (cls, kind)


def severity2html(context, severity):
    severity = unicode(severity)
    cls = {
        'urgent': 'danger',
        'high': 'warning',
        'medium': 'primary',
        'low': 'success',
    }.get(severity)

    return "<span class='label label-%s'>%s</span>" % (cls, severity)


def suggestion2html(context, suggestion):
    suggestion = unicode(suggestion)
    cls = {
        'reboot': 'danger',
        'logout': 'warning',
    }.get(suggestion)

    return "<span class='label label-%s'>%s</span>" % (cls, suggestion)


def request2html(context, request):
    request = unicode(request)
    cls = {
        'unpush': 'danger',
        'obsolete': 'warning',
        'testing': 'primary',
        'stable': 'success',
    }.get(request)

    return "<span class='label label-%s'>%s</span>" % (cls, request)


def update2html(context, update):
    request = context.get('request')

    if hasattr(update, 'title'):
        title = update.title
    else:
        title = update['title']

    url = request.route_url('update', id=title)
    settings = request.registry.settings
    max_length = int(settings.get('max_update_length_for_ui', 30))
    if len(title) > max_length:
        title = title[:max_length] + "..."
    return link(url, title)
