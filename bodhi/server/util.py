# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""
Random functions that don't fit elsewhere
"""

from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime
from os.path import join, dirname, basename, isfile
import collections
import functools
import hashlib
import os
import pkg_resources
import socket
import subprocess
import tempfile
import urllib

from kitchen.iterutils import iterate
from pyramid.i18n import TranslationStringFactory
from pyramid.settings import asbool
from sqlalchemy.orm import scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension
import arrow
import colander
import libravatar
import markdown
import requests
import transaction

from bodhi.server import log, buildsys
from bodhi.server.config import config
from bodhi.server.exceptions import RepodataException

try:
    import rpm
except ImportError:
    log.warning("Could not import 'rpm'")


_ = TranslationStringFactory('bodhi')


def header(x):
    """Display a given message as a heading."""
    return u"%s\n     %s\n%s\n" % ('=' * 80, x, '=' * 80)


def pluralize(val, name):
    """
    Returns name if val == 1, or returns name with an 's' appended to the end if val != 1.
    """
    return val == 1 and name or "%ss" % name


def get_rpm_header(nvr, tries=0):
    """ Get the rpm header for a given build """

    tries += 1
    headers = [
        'name', 'summary', 'version', 'release', 'url', 'description',
        'changelogtime', 'changelogname', 'changelogtext',
    ]
    rpmID = nvr + '.src'
    koji_session = buildsys.get_session()
    try:
        result = koji_session.getRPMHeaders(rpmID=rpmID, headers=headers)
    except Exception as e:
        msg = "Failed %i times to get rpm header data from koji for %s:  %s"
        log.warning(msg % (tries, nvr, str(e)))
        if tries < 3:
            # Try again...
            return get_rpm_header(nvr, tries=tries)
        else:
            # Give up for good and re-raise the failure...
            raise

    if result:
        return result

    raise ValueError("No rpm headers found in koji for %r" % nvr)


def get_nvr(nvr):
    """ Return the [ name, version, release ] a given name-ver-rel. """
    x = map(unicode, nvr.split('-'))
    return ('-'.join(x[:-2]), x[-2], x[-1])


def packagename_from_nvr(context, nvr):
    x = map(unicode, nvr.split('-'))
    return '-'.join(x[:-2])


def mkmetadatadir(path):
    """
    Generate package metadata for a given directory; if it doesn't exist, then
    create it.
    """
    if not os.path.isdir(path):
        os.makedirs(path)
    subprocess.check_call(['createrepo_c', '--xz', '--database', '--quiet', path])


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
    return tuple(map(str, (build['epoch'], build['version'], build['release'])))


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


@memoized
def get_critpath_pkgs(collection='master'):
    """Return a list of critical path packages for a given collection"""
    critpath_pkgs = []
    critpath_type = config.get('critpath.type')
    if critpath_type == 'pkgdb':
        from pkgdb2client import PkgDB
        pkgdb = PkgDB(config.get('pkgdb_url'))
        results = pkgdb.get_critpath_packages(branches=collection)
        if collection in results['pkgs']:
            critpath_pkgs = results['pkgs'][collection]
    else:
        critpath_pkgs = config.get('critpath_pkgs', '').split()
    return critpath_pkgs


class Singleton(object):
    def __new__(cls, *args, **kw):
        if '_instance' not in cls.__dict__:
            cls._instance = object.__new__(cls)
        return cls._instance


def sanity_check_repodata(myurl):
    """
    Sanity check the repodata for a given repository.
    """

    import librepo
    h = librepo.Handle()
    h.setopt(librepo.LRO_REPOTYPE, librepo.LR_YUMREPO)
    h.setopt(librepo.LRO_DESTDIR, tempfile.mkdtemp())

    if myurl[-1] != '/':
        myurl += '/'
    if myurl.endswith('repodata/'):
        myurl = myurl.replace('repodata/', '')

    h.setopt(librepo.LRO_URLS, [myurl])
    h.setopt(librepo.LRO_LOCAL, True)
    h.setopt(librepo.LRO_CHECKSUM, True)
    try:
        h.perform()
    except librepo.LibrepoException as e:
        rc, msg, general_msg = e
        raise RepodataException(msg)

    updateinfo = os.path.join(myurl, 'updateinfo.xml.gz')
    if os.path.exists(updateinfo):
        ret = subprocess.call(['zgrep', '<id/>', updateinfo])
        if not ret:
            raise RepodataException('updateinfo.xml.gz contains empty ID tags')


def age(context, date, nuke_ago=False):
    humanized = arrow.get(date).humanize()
    if nuke_ago:
        return humanized.replace(' ago', '')
    else:
        return humanized

hardcoded_avatars = {
    'bodhi': 'https://apps.fedoraproject.org/img/icons/bodhi-{size}.png',
    # Taskotron may have a new logo at some point.  Check this out:
    # https://mashaleonova.wordpress.com/2015/08/18/a-logo-for-taskotron/
    # Ask tflink before actually putting this in place though.  we need
    # a nice small square version.  It'll look great!
    # In the meantime, we can use this temporary logo.
    'taskotron': 'https://apps.fedoraproject.org/img/icons/taskotron-{size}.png'
}


def avatar(context, username, size):

    # Handle some system users
    # https://github.com/fedora-infra/bodhi/issues/308
    if username in hardcoded_avatars:
        return hardcoded_avatars[username].format(size=size)

    # context is a mako context object
    request = context['request']
    https = request.registry.settings.get('prefer_ssl'),

    @request.cache.cache_on_arguments()
    def work(username, size):
        openid = "http://%s.id.fedoraproject.org/" % username
        if asbool(config.get('libravatar_enabled', True)):
            if asbool(config.get('libravatar_dns', False)):
                return libravatar.libravatar_url(
                    openid=openid,
                    https=https,
                    size=size,
                    default='retro',
                )
            else:
                query = urllib.urlencode({'s': size, 'd': 'retro'})
                hash = hashlib.sha256(openid).hexdigest()
                template = "https://seccdn.libravatar.org/avatar/%s?%s"
                return template % (hash, query)

        return 'libravatar.org'

    return work(username, size)


def splitter(value):
    """Parse a string or list of comma or space delimited builds"""
    if value == colander.null:
        return

    items = []
    for v in iterate(value):
        if isinstance(v, basestring):
            for item in v.replace(',', ' ').split():
                items.append(item)

        elif v is not None:
            items.append(v)

    return items


def version(context=None):
    return pkg_resources.get_distribution('bodhi').version


def hostname(context=None):
    return socket.gethostname()


def markup(context, text):
    return markdown.markdown(text, safe_mode="replace",
                             html_replacement_text="--RAW HTML NOT ALLOWED--")


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


def state2class(context, state):
    state = unicode(state)
    cls = {
        'disabled': 'default active',
        'pending': 'warning',
        'current': 'success',
        'archived': 'danger'
    }
    return cls[state] if state in cls.keys() else 'default'


def type2color(context, t):
    t = unicode(t)
    cls = {
        'bugfix': 'rgba(150,180,205,0.5)',
        'security': 'rgba(205,150,180,0.5)',
        'newpackage': 'rgba(150,205,180,0.5)',
        'default': 'rgba(200,200,200,0.5)'
    }
    return cls[t] if t in cls.keys() else cls['default']


def state2html(context, state):
    state_class = state2class(context, state)
    return "<span class='label label-%s'>%s</span>" % (state_class, state)


def karma2class(context, karma, default='default'):
    if karma and karma >= -2 and karma <= 2:
        return {
            -2: 'danger',
            -1: 'danger',
            0: 'info',
            1: 'success',
            2: 'success',
        }.get(karma)
    return default


def karma2html(context, karma):

    # Recurse if we are handle multiple karma values
    if isinstance(karma, tuple):
        return '</td><td>'.join([karma2html(context, item) for item in karma])

    cls = karma2class(context, karma, None)

    if not cls:
        if karma < -2:
            cls = 'danger'
        elif karma == 0:
            cls = 'primary'
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


def type2icon(context, kind):
    kind = unicode(kind)
    cls = {
        'security': 'danger',
        'bugfix': 'warning',
        'newpackage': 'primary',
        'enhancement': 'success',
    }.get(kind)

    fontawesome = {
        'security': 'fa-shield',
        'bugfix': 'fa-bug',
        'newpackage': 'fa-archive',
        'enhancement': 'fa-bolt',
    }.get(kind)

    return "<span class='label label-%s'><i class='fa %s'></i></span>" % (cls, fontawesome)


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

    if hasattr(update, 'alias'):
        alias = update.alias
    else:
        alias = update['alias']

    url = request.route_url('update', id=alias or title)
    settings = request.registry.settings
    max_length = int(settings.get('max_update_length_for_ui', 30))
    if len(title) > max_length:
        title = title[:max_length] + "..."
    return link(url, title)


def pages_list(context, page, pages):
    margin = 4
    num_pages = (2 * margin) + 1

    if page <= margin + 1:
        # Current `page` is close to the beginning of `pages`
        min_page = 1
        max_page = min(pages, num_pages)

    elif (pages - page) >= margin:
        min_page = max(page - margin, 1)
        max_page = min(page + margin, pages)

    else:
        # Current `page` is close to the end of `pages`
        max_page = min(pages, page + margin)
        min_page = max(max_page - (num_pages - 1), 1)

    return range(min_page, max_page + 1)


def page_url(context, page):
    request = context.get('request')
    params = dict(request.params)
    params['page'] = page
    return request.path_url + "?" + urllib.urlencode(params)


def bug_link(context, bug, short=False):
    url = "https://bugzilla.redhat.com/show_bug.cgi?id=" + str(bug.bug_id)
    display = "#%i" % bug.bug_id
    link = "<a target='_blank' href='%s'>%s</a>" % (url, display)
    if not short:
        if bug.title:
            # We're good...
            link = link + " " + bug.title
        else:
            # Otherwise, the backend is async grabbing the title from rhbz, so
            link = link + " <img class='spinner' src='static/img/spinner.gif'>"

    return link


def testcase_link(context, test, short=False):
    settings = context['request'].registry
    default = 'https://fedoraproject.org/wiki/'
    url = settings.get('test_case_base_url', default) + test.name
    display = test.name.replace('QA:Testcase ', '')
    link = "<a target='_blank' href='%s'>%s</a>" % (url, display)
    if not short:
        link = "Test Case " + link
    return link


def sorted_builds(builds):
    return sorted(builds,
                  cmp=lambda x, y: rpm.labelCompare(get_nvr(x), get_nvr(y)),
                  reverse=True)


def sorted_updates(updates):
    """
    Order our updates so that the highest version gets tagged last so that
    it appears as the 'latest' in koji.

    Returns 2 lists, the first being builds that should be tagged synchronously
    in a specific order, where as the second batch can be done asynchronously
    in koji with a multicall.
    """
    builds = defaultdict(set)
    build_to_update = {}
    sync, async = [], []
    for update in updates:
        for build in update.builds:
            n, v, r = get_nvr(build.nvr)
            builds[n].add(build.nvr)
            build_to_update[build.nvr] = update
    for package in builds:
        if len(builds[package]) > 1:
            log.info('Found multiple %s packages' % package)
            log.debug(builds[package])
            for build in sorted_builds(builds[package])[::-1]:
                update = build_to_update[build]
                if update not in sync:
                    sync.append(update)
                if update in async:
                    async.remove(update)
        else:
            update = build_to_update[builds[package].pop()]
            if update not in async and update not in sync:
                async.append(update)
    log.info('sync = %s' % ([up.title for up in sync],))
    log.info('async = %s' % ([up.title for up in async],))
    return sync, async


def cmd(cmd, cwd=None):
    log.info('Running %r', cmd)
    if isinstance(cmd, basestring):
        cmd = cmd.split()
    p = subprocess.Popen(cmd, cwd=cwd,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    out, err = p.communicate()
    if out:
        log.debug(out)
    if err:
        log.error(err)
    if p.returncode != 0:
        log.error('return code %s', p.returncode)
    return out, err, p.returncode


def tokenize(string):
    """ Given something like "a b, c d" return ['a', 'b', 'c', 'd']. """

    for substring in string.split(','):
        substring = substring.strip()
        if substring:
            for token in substring.split():
                token = token.strip()
                if token:
                    yield token


def taskotron_results(settings, entity='results', **kwargs):
    """ Given an update object, yield resultsdb results. """
    url = settings['resultsdb_api_url'] + "/api/v1.0/" + entity
    if kwargs:
        url = url + "?" + urllib.urlencode(kwargs)
    data = True

    try:
        while data:
            log.debug("Grabbing %r" % url)
            response = requests.get(url)
            if response.status_code != 200:
                raise IOError("status code was %r" % response.status_code)
            json = response.json()
            url, data = json['next'], json['data']
            for datum in data:
                # Skip ABORTED results
                # https://github.com/fedora-infra/bodhi/issues/167
                if entity == 'results' and datum.get('outcome') == 'ABORTED':
                    continue
                yield datum
    except Exception:
        log.exception("Problem talking to %r" % url)


class TransactionalSessionMaker(object):
    """Provide a transactional scope around a series of operations."""
    def __init__(self, engine):
        self.engine = engine

    @contextmanager
    def __call__(self):
        Session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
        Session.configure(bind=self.engine)
        session = Session()
        transaction.begin()
        try:
            yield session
            transaction.commit()
        except:
            transaction.abort()
            raise
        finally:
            session.close()


transactional_session_maker = TransactionalSessionMaker


def sort_severity(value):
    """ Sorts UpdateSeverity by severity importance"""
    value_map = {
        'unspecified': 1,
        'low': 2,
        'medium': 3,
        'high': 4,
        'urgent': 5
    }

    return value_map.get(value, 99)
