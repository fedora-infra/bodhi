# -*- coding: utf-8 -*-
# Copyright © 2007-2018 Red Hat, Inc. and others.
#
# This file is part of Bodhi.
#
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
"""Random functions that don't fit elsewhere."""

from collections import defaultdict, OrderedDict
from contextlib import contextmanager
import functools
import hashlib
import json
import os
import pkg_resources
import re
import socket
import subprocess
import tempfile
import time

from kitchen.iterutils import iterate
from pyramid.i18n import TranslationStringFactory
import arrow
import bleach
import colander
import hawkey
import libcomps
import libravatar
import librepo
import markdown
import requests
import rpm
from six.moves import map
from six.moves.urllib.parse import urlencode
import six

from bodhi.server import ffmarkdown, log, buildsys, Session
from bodhi.server.config import config
from bodhi.server.exceptions import RepodataException


_ = TranslationStringFactory('bodhi')

http_session = requests.Session()


def header(x):
    """Display a given message as a heading."""
    return u"%s\n     %s\n%s\n" % ('=' * 80, x, '=' * 80)


def get_rpm_header(nvr, tries=0):
    """
    Get the rpm header for a given build.

    Args:
        nvr (basestring): The name-version-release string of the build you want headers for.
        tries (int): The number of attempts that have been made to retrieve the nvr so far. Defaults
            to 0.
    Returns:
        dict: A dictionary mapping RPM header names to their values, as returned by the Koji client.
    """
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


def flash_log(msg):
    """
    Log the given message at debug level.

    Args:
        msg (basestring): The message to log.
    """
    log.debug(msg)


def build_evr(build):
    """
    Return a tuple of strings of the given build's epoch, version, and release.

    Args:
        build (dict): A dictionary representing a Koji build with keys 'epoch', 'version', and
            'release'.
    Returns:
        tuple: A 3-tuple of strings representing the given build's epoch, version, and release,
            respectively.
    """
    if not build['epoch']:
        build['epoch'] = 0
    return tuple(map(str, (build['epoch'], build['version'], build['release'])))


def link(href, text):
    """
    Return an HTML anchor tag for the given href using the given text.

    Args:
        href (basestring): The URL to link.
        text (basestring): The text to render for the link.
    Returns:
        basestring: The requested anchor tag.
    """
    return '<a href="%s">%s</a>' % (href, text)


class memoized(object):
    """Decorator that permanently caches a function's return value each time it is called.

    If the function is called later with the same arguments, the cached value is returned (not
    reevaluated).

    http://wiki.python.org/moin/PythonDecoratorLibrary#Memoize

    Attributes:
        func (callable): The wrapped function.
        cache (dict): The cache, mapping arguments to the cached response.
    """

    def __init__(self, func):
        """
        Initialize the memoized object.

        Args:
            func: The function the memoized object is wrapping.
        """
        self.func = func
        self.cache = {}

    def __call__(self, *args):
        """
        If the args are cached, return the cached value. If not, call the wrapped function.

        If the wrapped function is called, it's response is only cached if the args are hashable.

        Args:
            args (list): The list of arguments passed to the wrapped function.
        Returns:
            object: The reponse from the wrapped function, or the cached response, if available.
        """
        try:
            hash(args)
        except TypeError:
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
        """
        Return the function's docstring.

        Returns:
            basestring: The wrapped function's docstring.
        """
        return self.func.__doc__

    def __get__(self, obj, objtype):
        """
        Support instance methods.

        Args:
            obj (object): The instance of the object the wrapped method is bound to.
            objtype (type): The type of the instance of the object the wrapped method is bound to.
        Returns:
            callable: A functools.partial response with the wrapped method's instance passed to it.
        """
        return functools.partial(self.__call__, obj)


@memoized
def get_critpath_components(collection='master', component_type='rpm', components=None):
    """
    Return a list of critical path packages for a given collection, filtered by components.

    Args:
        collection (basestring): The collection/branch to search. Defaults to 'master'.
        component_type (basestring): The component type to search for. This only affects PDC
            queries. Defaults to 'rpm'.
        components (frozenset or None): The list of components we are interested in. If None (the
            default), all components for the given collection and type are returned.
    Returns:
        list: The critpath components for the given collection and type.
    """
    critpath_components = []
    critpath_type = config.get('critpath.type')
    if critpath_type != 'pdc' and component_type != 'rpm':
        log.warning('The critpath.type of "{0}" does not support searching for'
                    ' non-RPM components'.format(component_type))

    if critpath_type == 'pkgdb':
        from pkgdb2client import PkgDB
        pkgdb = PkgDB(config.get('pkgdb_url'))
        results = pkgdb.get_critpath_packages(branches=collection)
        if collection in results['pkgs']:
            critpath_components = results['pkgs'][collection]
    elif critpath_type == 'pdc':
        critpath_components = get_critpath_components_from_pdc(
            collection, component_type, components)
    else:
        critpath_components = config.get('critpath_pkgs')

    # Filter the list of components down to what was requested, in case the specific path did
    # not take our request into account.
    if components is not None:
        critpath_components = [c for c in critpath_components if c in components]

    return critpath_components


def sanity_check_repodata(myurl, repo_type):
    """
    Sanity check the repodata for a given repository.

    Args:
        myurl (basestring): A path to a repodata directory.
        repo_type (str): This should be set to 'yum' for Yum repositories, 'module' for module
            repositories, or 'source' for source repositories.
    Raises:
        Exception: If the repodata is not valid or does not exist.
        ValueError: If repo_type is not an acceptable value.
    """
    if repo_type not in ('module', 'source', 'yum'):
        raise ValueError('repo_type must be one of module, source, or yum.')

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
    h.setopt(librepo.LRO_IGNOREMISSING, False)
    r = librepo.Result()
    try:
        h.perform(r)
    except librepo.LibrepoException as e:
        rc, msg, general_msg = e.args
        raise RepodataException(msg)

    repo_info = r.getinfo(librepo.LRR_YUM_REPO)
    primary_sack = hawkey.Sack()
    hk_repo = hawkey.Repo(myurl)
    try:
        hk_repo.filelists_fn = repo_info['filelists']
        # Source and module repos don't have DRPMs.
        if repo_type == 'yum':
            hk_repo.presto_fn = repo_info['prestodelta']
        elif repo_type == 'module':
            hk_repo.presto_fn = repo_info['modules']
        hk_repo.primary_fn = repo_info['primary']
        hk_repo.repomd_fn = repo_info['repomd']
        hk_repo.updateinfo_fn = repo_info['updateinfo']
    except KeyError as e:
        raise RepodataException('Required part not in repomd.xml: {}'.format(e.args[0]))
    primary_sack.load_repo(hk_repo,
                           build_cache=False,
                           load_filelists=True,
                           load_presto=True,
                           load_updateinfo=True)

    # Only yum repos have comps
    if repo_type == 'yum':
        # Test comps
        comps = libcomps.Comps()
        try:
            ret = comps.fromxml_f(repo_info['group'])
        except Exception:
            raise RepodataException('Comps file unable to be parsed')
        if len(comps.groups) < 1:
            raise RepodataException('Comps file empty')

    # Test updateinfo
    ret = subprocess.call(['zgrep', '<id/>', repo_info['updateinfo']])
    if not ret:
        raise RepodataException('updateinfo.xml.gz contains empty ID tags')


def age(context, date, nuke_ago=False):
    """
    Return a human readable age since the given date.

    Args:
        context (mako.runtime.Context): The current template rendering context.
        date (datetime.datetime): A date you wish a human readable age since.
        nuke_ago (bool): If True, remove " ago" from the age. Defaults to False.
    Returns:
        basestring: A human readable age since the given date.
    """
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
    """
    Return a URL of an avatar for the given username of the given size.

    Args:
        context (mako.runtime.Context): The current template rendering context.
        username (basestring): The username to return an avatar URL for.
        size (int): The size of the avatar you wish to retrieve, in unknown libravatar units.
    Returns:
        basestring: A URL to an avatar for the given username.
    """
    # Handle some system users
    # https://github.com/fedora-infra/bodhi/issues/308
    if username in hardcoded_avatars:
        return hardcoded_avatars[username].format(size=size)

    # context is a mako context object
    request = context['request']
    https = request.registry.settings.get('prefer_ssl')

    @request.cache.cache_on_arguments()
    def get_libravatar_url(openid, https, size):
        return libravatar.libravatar_url(
            openid=openid,
            https=https,
            size=size,
            default='retro',
        )

    def work(username, size):
        openid = "http://%s.id.fedoraproject.org/" % username
        if config.get('libravatar_enabled'):
            if config.get('libravatar_dns'):
                return get_libravatar_url(openid, https, size)
            else:
                query = urlencode({'s': size, 'd': 'retro'})
                hash = hashlib.sha256(openid.encode('utf-8')).hexdigest()
                template = "https://seccdn.libravatar.org/avatar/%s?%s"
                return template % (hash, query)

        return 'libravatar.org'

    return work(username, size)


def splitter(value):
    """
    Parse a string or list of comma or space delimited builds, returning a list of the values.

    Examples:
        >>> util.splitter('one,two,,three,')
        ['one', 'two', 'three']
        >>> util.splitter(['one,two,,three,,', 'four'])
        ['one', 'two', 'three', 'four']

    Args:
        value (basestring, colander.null, or iterable): The value to interpret as a list.
    Returns:
        list: A list of strings.
    """
    if value == colander.null:
        return

    items = []
    for v in iterate(value):
        if isinstance(v, six.string_types):
            for item in v.replace(',', ' ').split():
                items.append(item)

        elif v is not None:
            items.append(v)

    return items


def version(context=None):
    """
    Return the Bodhi server's version.

    Args:
        context (mako.runtime.Context or None): Unused. Defaults to None.
    Returns:
        basestring: The Bodhi server's version.
    """
    return pkg_resources.get_distribution('bodhi').version


def hostname(context=None):
    """
    Return the Bodhi server's hostname.

    Args:
        context (mako.runtime.Context or None): Unused. Defaults to None.
    Returns:
        basestring: The Bodhi server's hostname.
    """
    return socket.gethostname()


def markup(context, text):
    """
    Return HTML from a markdown string.

    Args:
        context (mako.runtime.Context): Unused.
        text (basestring): Markdown text to be converted to HTML.
    Returns:
        basestring: HTML representation of the markdown text.
    """
    # determine the major component of the bleach version installed.
    # this is similar to the approach that Pagure uses to determine the bleach version
    # https://pagure.io/pagure/pull-request/2269#request_diff
    bleach_major_v = int(bleach.__version__.split('.')[0])

    # the only difference in the bleach API that we use between v1 and v2 is
    # the formatting of the attributes parameter. Bleach 1 only allowed you
    # to specify attributes to be whitelisted for all whitelisted tags.
    # Bleach 2 requires you to specify the list of attributes whitelisted for
    # specific tags.
    if bleach_major_v >= 2:
        markdown_attrs = {
            "img": ["src", "alt", "title"],
            "a": ["href", "alt", "title"],
            "div": ["class"],
        }
    else:
        markdown_attrs = [
            "src", "href", "alt", "title", "class"
        ]

    markdown_tags = [
        "h1", "h2", "h3", "h4", "h5", "h6",
        "b", "i", "strong", "em", "tt",
        "p", "br",
        "span", "div", "blockquote", "code", "hr", "pre",
        "ul", "ol", "li", "dd", "dt",
        "img",
        "a",
    ]

    markdown_text = markdown.markdown(text, extensions=['markdown.extensions.fenced_code',
                                                        ffmarkdown.BodhiExtension()])

    # previously, we linkified text in ffmarkdown.py, but this was causing issues like #1721
    # so now we use the bleach linkifier to do this for us.
    markdown_text = bleach.linkify(markdown_text, parse_email=True)

    # previously, we used the Safe Mode in python-markdown to strip all HTML
    # tags. Safe Mode is deprecated, so we now use Bleach to sanitize all HTML
    # tags after running it through the markdown parser
    return bleach.clean(markdown_text, tags=markdown_tags, attributes=markdown_attrs)


def composestate2html(context, state):
    """
    Render the given UpdateStatus as a span containing text.

    Args:
        context (mako.runtime.Context): Unused.
        state (bodhi.server.models.ComposeState): The ComposeState to render as a span
            tag.
    Returns:
        basestring: An HTML span tag representing the ComposeState.
    """
    cls = {
        'requested': 'primary',
        'pending': 'primary',
        'initializing': 'warning',
        'updateinfo': 'warning',
        'punging': 'warning',
        'notifying': 'warning',
        'cleaning': 'warning',
        'success': 'success',
        'failed': 'danger',
    }[state.value]
    return "<span class='label label-%s'>%s</span>" % (cls, state.description)


def status2html(context, status):
    """
    Render the given UpdateStatus as a span containing text.

    Args:
        context (mako.runtime.Context): Unused.
        severity (bodhi.server.models.UpdateStatus): The UpdateStatus to render as a span
            tag.
    Returns:
        basestring: An HTML span tag representing the UpdateStatus.
    """
    status = six.text_type(status)
    cls = {
        'pending': 'primary',
        'testing': 'warning',
        'stable': 'success',
        'unpushed': 'danger',
        'obsolete': 'default',
        'processing': 'info',
    }[status]
    status_desc = {
        'pending': 'The update has not yet been pushed to the testing or stable repositories.',
        'testing': 'The package is in the testing repository for people to test.',
        'stable': 'The package has been released to the stable repository.',
        'unpushed': 'The update has been removed from testing.',
        'obsolete': 'The package has been obsoleted by a different update.',
        'processing': 'Unused.',
    }[status]

    return "<span class='text-muted' data-toggle='tooltip' title='%s'>" % (status_desc) \
        + "<span class='label label-%s'>%s</span>" % (cls, status) \
        + "</span>"


def greenwave_unsatisfied_requirements_html(context, update):
    """
    Return an html representation of the given update's greenwave_unsatisfied_requirements field.

    This function collates the unsatisfied requirements into a heirarchy of requirement type, then
    test name, and then a list of builds that fail to satisfy that requirement type for that test
    name.

    Args:
        context (mako.runtime.Context): Unused.
        update (bodhi.server.models.Update): The update to render unsatisfied requirements for.
    Returns:
        str: A human readable representation of the update's unsatisfied requirements.
    """
    if not update.greenwave_unsatisfied_requirements:
        return ''

    # The Greenwave data is in a list of dictionaries that describe unsatisfied requirements. Let's
    # collate that data into type of requirement (such as missing test, failed test, etc.) --> test
    # name --> list of nvrs that fail that test name. To do this, we'll build a dictionary of
    # dictionaries of lists, like this:
    #
    # {'test-result-missing': {'dist.rpmdeplint': ['bodhi-3.6.1-fc28']}}
    reqs = defaultdict(lambda: defaultdict(list))
    for r in json.loads(update.greenwave_unsatisfied_requirements):
        # The Greenwave response contains a lot of duplicate information. For now, let's ignore
        # anything that isn't a koji build. https://pagure.io/greenwave/issue/169
        if r['item'].get('type') == 'koji_build':
            reqs[r['type']][r['testcase']].append(r['item']['item'])
    # Now that we've built our data structure, let's render it into an HTML snippet that can be
    # included in the update page.
    html = '<div>Unsatisfied requirements:'
    for t in reqs.keys():
        html = html + '<div>{}: {}</div>'.format(
            t,
            ', '.join([' {} ({})'.format(testcase, ', '.join(reqs[t][testcase]))
                      for testcase in reqs[t].keys()]))
    html = html + '</div>'
    return html


def state2class(context, state):
    """
    Classify the given ReleaseState value.

    Args:
        context (mako.runtime.Context): Unused.
        state (bodhi.server.models.ReleaseState): The ReleaseState value you wish to classify.
    Returns:
        basestring: A string representing the classification of the given ReleaseState. Can return
            'danger', 'warning', 'success', or 'default active'.
    """
    state = six.text_type(state)
    cls = {
        'disabled': 'default active',
        'pending': 'warning',
        'current': 'success',
        'archived': 'danger'
    }
    return cls[state] if state in cls.keys() else 'default'


def type2color(context, t):
    """
    Return a color to render the given UpdateType with.

    Args:
        context (mako.runtime.Context): The current template rendering context.
        t (bodhi.server.models.UpdateType): The UpdateType you wish to choose a color for.
    Returns:
        basestring: A string in the format rgba(RED, GREEN, BLUE, ALPHA), where RED, GREEN, BLUE,
            and ALPHA are replaced with numerical values to represent a color.
    """
    t = six.text_type(t)
    cls = {
        'bugfix': 'rgba(150,180,205,0.5)',
        'security': 'rgba(205,150,180,0.5)',
        'newpackage': 'rgba(150,205,180,0.5)',
        'default': 'rgba(200,200,200,0.5)'
    }
    return cls[t] if t in cls.keys() else cls['default']


def state2html(context, state):
    """
    Render the given ReleaseState as an HTML span tag.

    Args:
        context (mako.runtime.Context): The current template rendering context.
        state (bodhi.server.models.ReleaseState): The ReleaseState you wish to render as HTML.
    Returns:
        basestring: An HTML rendering of the given ReleaseState.
    """
    state_class = state2class(context, state)
    return "<span class='label label-%s'>%s</span>" % (state_class, state)


def karma2class(context, karma, default='default'):
    """
    Classify the given karma value if possible, or return the default value.

    Args:
        context (mako.runtime.Context): Unused.
        karma (int): The karma value you wish to classify.
        default (basestring): The default value if karma is not within the range -2 <= karma <= 2.
    Returns:
        basestring: A string representing the classification of the given karma. Can return
            'danger', 'info', 'success', or the default value.
    """
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
    """
    Render the given karma as a span labeled for rendering, or as a list of td tags of the same.

    Args:
        context (mako.runtime.Context): The current template rendering context.
        karma (int or tuple): The karma value or values you wish to render a span tag or td tags
            for.
    Returns:
        basestring: An HTML span tag or a list of td tags representing the karma or karma tuple.
    """
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
    """
    Render the given UpdateType as a span containing text.

    Args:
        context (mako.runtime.Context): Unused.
        severity (bodhi.server.models.UpdateType): The UpdateType to render as a span
            tag.
    Returns:
        basestring: An HTML span tag representing the UpdateType.
    """
    kind = six.text_type(kind)
    cls = {
        'security': 'danger',
        'bugfix': 'warning',
        'newpackage': 'primary',
        'enhancement': 'success',
    }.get(kind)

    return "<span class='label label-%s'>%s</span>" % (cls, kind)


def type2icon(context, kind):
    """
    Render the given UpdateType as a span containing an icon.

    Args:
        context (mako.runtime.Context): Unused.
        severity (bodhi.server.models.UpdateType): The UpdateType to render as a span
            tag.
    Returns:
        basestring: An HTML span tag representing the UpdateType.
    """
    kind = six.text_type(kind)
    cls = {
        'security': 'danger',
        'bugfix': 'warning',
        'newpackage': 'primary',
        'enhancement': 'success',
    }.get(kind)

    if kind[0].lower() in 'aeiou':
        kind_article = 'an'
    else:
        kind_article = 'a'

    fontawesome = {
        'security': 'fa-shield',
        'bugfix': 'fa-bug',
        'newpackage': 'fa-archive',
        'enhancement': 'fa-bolt',
    }.get(kind)

    span = ("<span class='label label-%s' data-toggle='tooltip' "
            "title='This is %s %s update'><i class='fa fa-fw %s'></i></span>")
    return span % (cls, kind_article, kind, fontawesome)


def severity2html(context, severity):
    """
    Render the given UpdateSeverity as an HTML span tag.

    Args:
        context (mako.runtime.Context): Unused.
        severity (bodhi.server.models.UpdateSeverity): The UpdateSeverity to render as a span
            tag.
    Returns:
        basestring: An HTML span tag representing the UpdateSeverity.
    """
    severity = six.text_type(severity)
    cls = {
        'urgent': 'danger',
        'high': 'warning',
        'medium': 'primary',
        'low': 'success',
        'unspecified': 'default',
    }.get(severity)

    return "<span class='label label-%s'>%s</span>" % (cls, severity)


def request2html(context, request):
    """
    Render the given UpdateRequest as an HTML span tag.

    Args:
        context (mako.runtime.Context): Unused.
        request (bodhi.server.models.UpdateRequest): The UpdateRequest to render as a span tag.
    Returns:
        basestring: An HTML span tag representing the UpdateRequest.
    """
    request = six.text_type(request)
    cls = {
        'unpush': 'danger',
        'obsolete': 'default',
        'testing': 'warning',
        'stable': 'success',
        'batched': 'success',
    }.get(request)

    return "<span class='label label-%s'>%s</span>" % (cls, request)


def update2html(context, update):
    """
    Return an HTML anchor tag for the given update.

    Args:
        context (mako.runtime.Context): The current template rendering context.
        update (bodhi.server.models.Update or dict): The Update or dictionary serialization of an
            Update that you wish to receive an HTML anchor tag for.
    Returns:
        basestring: An HTML anchor tag linking the Update.
    """
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
    max_length = settings.get('max_update_length_for_ui')
    if len(title) > max_length:
        title = title[:max_length] + "..."
    return link(url, title)


def pages_list(context, page, pages):
    """
    Return a list of page numbers to display in pagination lists.

    Args:
        context (mako.runtime.Context): Unused.
        page (int): The current page number.
        pages (int): The total number of pages.
    Returns:
        list: A list of page numbers that should be displayed to the user.
    """
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
    """
    Return a paginated version of the request URL with the given page.

    Args:
        context (mako.runtime.Context): The current template context, used to get the current path
            URL.
        page (basestring): The requested page number.
    Returns:
        basestring: The current path appended with a GET query for the requested page.
    """
    request = context.get('request')
    params = dict(request.params)
    params['page'] = page
    return request.path_url + "?" + urlencode(params)


def bug_link(context, bug, short=False):
    """
    Form a URL to a given bugzilla bug.

    Args:
        context: Unused.
        short (bool): If False, includes the title of the bug in the response, or a spinner if the
            title is unknown. If True, only returns the anchor tag. Defaults to False.
    Returns:
        basestring: The requested link.
    """
    url = "https://bugzilla.redhat.com/show_bug.cgi?id=" + str(bug.bug_id)
    display = "#%i" % bug.bug_id
    link = "<a target='_blank' href='%s'>%s</a>" % (url, display)
    if not short:
        if bug.title:
            # We're good, but we do need to clean the bug title in case it contains malicious
            # tags. See CVE-2017-1002152: https://github.com/fedora-infra/bodhi/issues/1740
            link = link + " " + bleach.clean(bug.title, tags=[], attributes=[])
        else:
            # Otherwise, the backend is async grabbing the title from rhbz, so
            link = link + " <img class='spinner' src='static/img/spinner.gif'>"

    return link


def push_to_batched_or_stable_button(context, update):
    """
    Form the push to batched or push to stable button, as appropriate.

    Args:
        context (mako.runtime.Context): The current template rendering context. Unused.
        update (bodhi.server.models.Update): The Update we are rendering a button about.
    Returns:
        basestring: HTML for a button that will draw the push to stable or push to batched button,
            as appropriate.
    """
    if getattr(update.request, 'description', None) == 'batched' or \
            getattr(update.severity, 'description', None) == 'urgent':
        button = ('stable', 'Stable')
    elif getattr(update.request, 'description', None) in ('stable', None):
        button = ('batched', 'Batched')
    else:
        return ''

    return ('<a id="{}" class="btn btn-sm btn-success">'
            '<span class="fa fa-fw fa-arrow-circle-right"></span> Push to {}</a>').format(*button)


def testcase_link(context, test, short=False):
    """
    Form a URL to a given test description.

    Args:
        context: Unused.
        test (bodhi.server.models.TestCase): The test case you wish to have a link to.
        short (bool): If False, returns "Test Case " then the HTML anchor tag with the link. If
            True, only returns the anchor tag. Defaults to False.
    Returns:
        basestring: The requested link.
    """
    url = config.get('test_case_base_url') + test.name
    display = test.name.replace('QA:Testcase ', '')
    link = "<a target='_blank' href='%s'>%s</a>" % (url, display)
    if not short:
        link = "Test Case " + link
    return link


def can_waive_test_results(context, update):
    """
    Return True or False if the test results can be waived on an update.

    Args:
        context (mako.runtime.Context): The current template rendering context. Unused.
        update (bodhi.server.models.Update): The Update on which we are going to waive test results.
    Returns:
        bool: Indicating if the test results can be waived on the given update.
    """
    return config.get('test_gating.required') and not update.test_gating_passed \
        and config.get('waiverdb.access_token') and update.status.description != 'stable'


def sorted_builds(builds):
    """
    Sort the given builds by their NVRs.

    Args:
        builds (iterable): The builds you wish to sort by NVR.
    Returns:
        list: A list of Builds sorted by NVR.
    """
    key_function = functools.cmp_to_key(rpm.labelCompare)
    return sorted(builds,
                  key=lambda x: key_function(x.get_n_v_r()),
                  reverse=True)


def sorted_updates(updates):
    """
    Sort the given iterable of Updates so the highest version appears last.

    Order our updates so that the highest version gets tagged last so that
    it appears as the 'latest' in koji.

    Args:
        updates (iterable): An iterable of bodhi.server.models.Update objects to be sorted.
    Returns:
        tuple: A 2-tuple of lists. The first list contains builds that should be tagged
            synchronously in a specific order. The second list can be tagged asynchronously in koji
            with a multicall.
    """
    builds = defaultdict(set)
    sync, async_ = [], []
    for update in updates:
        for build in update.builds:
            builds[build.nvr_name].add(build)
    # The sorted here is so we actually have a way to test this
    # Otherwise, we would be depending on the way Python orders dict keys
    for package in sorted(builds.keys()):
        if len(builds[package]) > 1:
            log.debug(builds[package])
            for build in sorted_builds(builds[package])[::-1]:
                if build.update not in sync:
                    sync.append(build.update)
                if build.update in async_:
                    async_.remove(build.update)
        else:
            build = list(builds[package])[0]
            if build.update not in async_ and build.update not in sync:
                async_.append(build.update)
    log.info('sync = %s' % ([up.title for up in sync],))
    log.info('async_ = %s' % ([up.title for up in async_],))
    if not (len(set(sync) & set(async_)) == 0 and len(set(sync) | set(async_)) == len(updates)):
        # There should be absolutely no way to hit this code path, but let's be paranoid, and check
        # every run, to make sure no update gets left behind.
        # It makes sure that there is no update in sync AND async, and that the combination of
        # sync OR async_ is the full set of updates.
        raise Exception('ERROR! SYNC+ASYNC != UPDATES! sorted_updates failed')  # pragma: no cover
    return sync, async_


def cmd(cmd, cwd=None, raise_on_error=False):
    """
    Run the given command in a subprocess.

    Args:
        cmd (list): The command to be run. This is expressed as a list to be
            passed directly to subprocess.Popen().
        cwd (basestring or None): The current working directory to use when launching the
            subprocess.
        raise_on_error (bool): If True, raise a RuntimeError if the command's exit code is non-0.
            Defaults to False.
    Returns:
        tuple: A 3-tuple of the standard output (basestring), standard error (basestring), and the
            process's return code (int).
    Raises:
        RuntimeError: If exception is True and the command's exit code is non-0.
    """
    log.debug('Running {}'.format(' '.join(cmd)))
    p = subprocess.Popen(cmd, cwd=cwd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    output = '{}\n{}'.format(out, err)
    if p.returncode != 0:
        msg = '{} returned a non-0 exit code: {}'.format(' '.join(cmd), p.returncode)
        log.error(msg)
        log.error(output)
        if raise_on_error:
            raise RuntimeError(msg)
    elif out or err:
        log.debug(output)
    return out, err, p.returncode


def tokenize(string):
    """
    Interpret the given string as a space or comma separated ordered iterable of strings.

    For example, Given something like "a b, c d" return a generator equivalent of
    ['a', 'b', 'c', 'd'].

    Args:
        string (basestring): The string to be interpreted as an iterable.
    Yields:
        basestring: The individual tokens found in the comma or space separated string.
    """
    for substring in string.split(','):
        substring = substring.strip()
        if substring:
            for token in substring.split():
                token = token.strip()
                if token:
                    yield token


def taskotron_results(settings, entity='results/latest', max_queries=10, **kwargs):
    """
    Yield resultsdb results using query arguments.

    Args:
        entity (basestring): The API endpoint to use (see resultsdb documentation).
        max_queries (int): The maximum number of queries to perform (pages to retrieve). ``1`` means
            just a single page. ``None`` or ``0`` means no limit. Please note some tests might have
            thousands of results in the database and it's very reasonable to limit queries (thus the
            default value).
        kwargs (dict): Args that will be passed to resultsdb to specify what results to retrieve.
    Returns:
        generator or None: Yields Python objects loaded from ResultsDB's "data" field in its JSON
            response, or None if there was an Exception while performing the query.
    """
    max_queries = max_queries or 0
    url = settings['resultsdb_api_url'] + "/api/v2.0/" + entity
    if kwargs:
        url = url + "?" + urlencode(kwargs)
    data = True
    queries = 0

    try:
        while data and url:
            log.debug("Grabbing %r" % url)
            response = requests.get(url, timeout=60)
            if response.status_code != 200:
                raise IOError("status code was %r" % response.status_code)
            json = response.json()
            for datum in json['data']:
                yield datum

            url = json.get('next')
            queries += 1
            if max_queries and queries >= max_queries and url:
                log.debug('Too many result pages, aborting at: %r' % url)
                break
    except Exception as e:
        log.exception("Problem talking to %r : %r" % (url, str(e)))


class TransactionalSessionMaker(object):
    """Provide a transactional database scope around a series of operations."""

    @contextmanager
    def __call__(self):
        """
        Manage a database Session object for the life of the context.

        Yields a database Session object, then either commits the tranaction if there were no
        Exceptions or rolls back the transaction. In either case, it also will close and remove the
        Session.
        """
        session = Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            # It is possible for session.rolback() to raise Exceptions, so we will wrap it in an
            # Exception handler as well so we can log the rollback failure and still raise the
            # original Exception.
            try:
                session.rollback()
            except Exception:
                log.exception('An Exception was raised while rolling back a transaction.')
            raise e
        finally:
            session.close()
            Session.remove()


transactional_session_maker = TransactionalSessionMaker


def sort_severity(value):
    """
    Map a given UpdateSeverity string representation to a numerical severity value.

    This is used to sort severities from low to high.

    Args:
        value (basestring): The human readable UpdateSeverity string.
    Returns:
        int: A number representing the sorting order of the given UpdateSeverity string, or 99 if an
            unknown value is given.
    """
    value_map = {
        'unspecified': 1,
        'low': 2,
        'medium': 3,
        'high': 4,
        'urgent': 5
    }

    return value_map.get(value, 99)


def severity_updateinfo_str(value):
    """
    Convert a severity level into one apt for inclusion in the updateinfo XML.

    These values are compatible with RHEL repodata to make it easier to write
    portable clients.

    Args:
        value (basestring): The Bodhi severity to be mapped to a repodata severity string.
    Returns:
        basestring: A severity string to be included in repodata.
    """
    severity_map = {
        'unspecified': "None",
        'low': "Low",
        'medium': "Moderate",
        'high': "Important",
        'urgent': "Critical",
    }
    return severity_map.get(value, "None")


# If we need to know about more components than this constant, we will just get the full
# list, rather than a query per package. This is because at some point, just going through
# paging becomes more performant than getting the page for every component.
PDC_CRITPATH_COMPONENTS_GETALL_LIMIT = 10


def get_critpath_components_from_pdc(branch, component_type='rpm', components=None):
    """
    Search PDC for critical path packages based on the specified branch.

    Args:
        branch (basestring): The branch name to search by.
        component_type (basestring): The component type to search by. Defaults to ``rpm``.
        components (frozenset or None): The list of components we are interested in. If None (the
            default), all components for the given branch and type are returned.
    Returns:
        list: Critical path package names.
    """
    pdc_api_url = '{}/rest_api/v1/component-branches/'.format(
        config.get('pdc_url').rstrip('/'))
    query_args = {
        'active': 'true',
        'critical_path': 'true',
        'name': branch,
        'page_size': 100,
        'type': component_type,
        'fields': 'global_component'
    }
    # Create ordered dictionary with sorted query args to be able to compare URLs
    query_args = OrderedDict(sorted(query_args.items(), key=lambda x: x[0]))

    critpath_pkgs_set = set()
    if components and len(components) < PDC_CRITPATH_COMPONENTS_GETALL_LIMIT:
        # Do a query for every single component
        for component in components:
            query_args['global_component'] = component
            pdc_api_url_with_args = '{0}?{1}'.format(pdc_api_url, urlencode(query_args))
            pdc_request_json = pdc_api_get(pdc_api_url_with_args)
            for branch_rv in pdc_request_json['results']:
                critpath_pkgs_set.add(branch_rv['global_component'])
            if pdc_request_json['next']:
                raise Exception('We got paging when requesting a single component?!')
    else:
        pdc_api_url_with_args = '{0}?{1}'.format(pdc_api_url, urlencode(query_args))
        while True:
            pdc_request_json = pdc_api_get(pdc_api_url_with_args)

            for branch_rv in pdc_request_json['results']:
                critpath_pkgs_set.add(branch_rv['global_component'])

            if pdc_request_json['next']:
                pdc_api_url_with_args = pdc_request_json['next']
            else:
                # There are no more results to iterate through
                break
    return list(critpath_pkgs_set)


def call_api(api_url, service_name, error_key=None, method='GET', data=None, headers=None,
             retries=0):
    """
    Perform an HTTP request with response type and error handling.

    Args:
        api_url (basestring): The URL to query.
        service_name (basestring): The service name being queried (used to form human friendly error
            messages).
        error_key (basestring): The key that indexes error messages in the JSON body for the given
            service. If this is set to None, the JSON response will be used as the error message.
        method (basestring): The HTTP method to use for the request. Defaults to ``GET``.
        data (dict): Query string parameters that will be sent along with the request to the server.
        retries (int): The number of times to retry, each after a 1 second sleep, if we get a
            non-200 HTTP code. Defaults to 3.
    Returns:
        dict: A dictionary representing the JSON response from the remote service.
    Raises:
        RuntimeError: If the server did not give us a 200 code.
    """
    if data is None:
        data = dict()
    if method == 'POST':
        if headers is None:
            headers = {'Content-Type': 'application/json'}
        base_error_msg = (
            'Bodhi failed to send POST request to {0} at the following URL '
            '"{1}". The status code was "{2}".')
        rv = http_session.post(api_url,
                               headers=headers,
                               data=json.dumps(data),
                               timeout=60)
    else:
        base_error_msg = (
            'Bodhi failed to get a resource from {0} at the following URL '
            '"{1}". The status code was "{2}".')
        rv = http_session.get(api_url, timeout=60)

    if rv.status_code >= 200 and rv.status_code < 300:
        return rv.json()
    elif retries:
        time.sleep(1)
        return call_api(api_url, service_name, error_key, method, data, headers, retries - 1)
    elif rv.status_code == 500:
        # There will be no JSON with an error message here
        error_msg = base_error_msg.format(
            service_name, api_url, rv.status_code)
        log.error(error_msg)
        raise RuntimeError(error_msg)
    else:
        # If it's not a 500 error, we can assume that the API returned an error
        # message in JSON that we can log
        try:
            rv_error = rv.json()
            if error_key is not None:
                rv_error = rv_error.get(error_key)
        except ValueError:
            rv_error = ''
        error_msg = base_error_msg.format(
            service_name, api_url, rv.status_code)
        error_msg = '{0} The error was "{1}".'.format(error_msg, rv_error)
        log.error(error_msg)
        raise RuntimeError(error_msg)


def pagure_api_get(pagure_api_url):
    """
    Perform a GET request against Pagure.

    Args:
        pagure_api_url (basestring): The URL to GET, including query parameters.
    Returns:
        dict: A dictionary response representing the API response's JSON.
    Raises:
        RuntimeError: If the server did not give us a 200 code.
    """
    return call_api(pagure_api_url, service_name='Pagure', error_key='error', retries=3)


def pdc_api_get(pdc_api_url):
    """
    Perform a GET request against PDC.

    Args:
        pdc_api_url (basestring): The URL to GET, including query parameters.
    Returns:
        dict: A dictionary response representing the API response's JSON.
    Raises:
        RuntimeError: If the server did not give us a 200 code.
    """
    # There is no error_key specified because the error key is not consistent
    # based on the error message
    return call_api(pdc_api_url, service_name='PDC', retries=3)


def greenwave_api_post(greenwave_api_url, data):
    """
    Post a request to Greenwave.

    Args:
        greenwave_api_url (basestring): The URL to query.
        data (dict): The parameters to send along with the request.
    Returns:
        dict: A dictionary response representing the API response's JSON.
    Raises:
        RuntimeError: If the server did not give us a 200 code.
    """
    # There is no error_key specified because the error key is not consistent
    # based on the error message
    return call_api(greenwave_api_url, service_name='Greenwave', method='POST',
                    data=data, retries=3)


def waiverdb_api_post(waiverdb_api_url, data):
    """
    Post a request to WaiverDB.

    Args:
        waiverdb_api_url (basestring): The URL to query.
        data (dict): The parameters to send along with the request.
    Returns:
        dict: A dictionary response representing the API response's JSON.
    Raises:
        RuntimeError: If the server did not give us a 200 code.
    """
    # There is no error_key specified because the error key is not consistent
    # based on the error message
    return call_api(waiverdb_api_url, service_name='WaiverDB', method='POST',
                    data=data, headers={
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer %s' % config.get('waiverdb.access_token')
                    })


class no_autoflush(object):
    """
    A content manager that disables sqlalchemy's autoflush, restoring it afterwards.

    Adapted from https://bitbucket.org/zzzeek/sqlalchemy/wiki/UsageRecipes/DisableAutoflush
    """

    def __init__(self, session):
        """
        Store the session and remember its entrant state.

        Args:
            session (sqlalchemy.orm.session.Session): The session to disable autoflush on.
        """
        self.session = session
        self.autoflush = session.autoflush

    def __enter__(self):
        """Disable autoflush."""
        self.session.autoflush = False

    def __exit__(self, *args, **kwargs):
        """Restore autoflush to its entrant state. Args unused."""
        self.session.autoflush = self.autoflush


def _get_build_repository(build):
    """
    Return the registry repository name for the given Build from the container's pull string.

    Examples -
    'candidate-registry.fedoraproject.org/f29/cockpit:176-5.fc28' => 'f29/cockpit'.
    'candidate-registry.fedoraproject.org/myrepo@sha256:<hash>' => 'myrepo'.

    Args:
        build (bodhi.server.models.Build): A Build representing a container or flatpak.
    Returns:
        str: The registry repository name for the build.
    """
    koji = buildsys.get_session()
    koji_build = koji.getBuild(build.nvr)

    pull_specs = koji_build['extra']['image']['index']['pull']
    # All the pull specs should have the same repository, so which one we use is arbitrary
    base, tag = re.compile(r'[:@]').split(pull_specs[0], 1)
    server, repository = base.split('/', 1)

    return repository


def copy_container(build, destination_registry=None, destination_tag=None):
    """
    Copy a ContainerBuild from the source registry to a destination registry under the given tag.

    Args:
        build (bodhi.server.models.ContainerBuild): The build you wish to copy from the source tag
            to the destination tag.
        destination_registry (str or None): The registry to copy the build into. If None (the
            default), the container.destination_registry setting is used.
        destination_tag (str or None): The destination tag you wish to copy the source image to. If
            None (the default), the build's version and release are used to form the destination
            tag.
    Raises:
        RuntimeError: If skopeo returns a non-0 exit code.
    """
    source_registry = config['container.source_registry']
    source_tag = '{}-{}'.format(build.nvr_version, build.nvr_release)

    if destination_tag is None:
        destination_tag = source_tag
    if destination_registry is None:
        destination_registry = config['container.destination_registry']

    repository = _get_build_repository(build)

    source_url = _container_image_url(source_registry, repository, source_tag)
    destination_url = _container_image_url(destination_registry, repository, destination_tag)

    skopeo_cmd = [
        config.get('skopeo.cmd'), 'copy', source_url, destination_url]
    if config.get('skopeo.extra_copy_flags'):
        for flag in reversed(config.get('skopeo.extra_copy_flags').split(',')):
            skopeo_cmd.insert(2, flag)
    cmd(skopeo_cmd, raise_on_error=True)


def _container_image_url(registry, repository, tag=None):
    """
    Return a URL suitable for use in Skopeo for copying or deleting container images.

    For example, this can return a URL like
    docker://registry.fedoraproject.org/f27/httpd:0-3.f27container if tag is None, or
    docker://registry.fedoraproject.org/f27/httpd:build is tag is 'build'.

    Args:
        repository (str): the repository name in the registry, extracted from Koji metadata
        registry (str): The registry you want a URL for.
        tag (str or None): The tag in the registry you want to reference.
    Returns:
        str: A URL referencing the given build and tag in the given registry.
    """
    return 'docker://{}/{}:{}'.format(registry, repository, tag)


def get_absolute_path(location):
    """
    Return an absolute path in filesystem for a relative path value.

    For example, location 'bodhi:server/templates' can return something like:
        /home/bodhi/bodhi/server/templates/

    Args:
        location (str): The relative path you want to convert.
    Returns:
        str: An absolute path in the filesystem referencing to the given directory.
    """
    module, final = location.split(':')
    base = os.path.dirname(__import__(module).__file__)
    return base + "/" + final
