# -*- coding: utf-8 -*-
#
# Copyright © 2007-2018 Red Hat, Inc. and others.
#
# This file is part of bodhi.
#
# This software is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this software; if not, see <http://www.gnu.org/licenses/>
"""
This module provides Python bindings to the Bodhi REST API.

.. moduleauthor:: Luke Macken <lmacken@redhat.com>
.. moduleauthor:: Toshio Kuratomi <tkuratom@redhat.com>
.. moduleauthor:: Ralph Bean <rbean@redhat.com>
.. moduleauthor:: Randy Barlow <bowlofeggs@fedoraproject.org>
"""

import datetime
import functools
import getpass
import itertools
import json
import logging
import os
import re
import textwrap

from iniparse.compat import ConfigParser
from six.moves import configparser
from six.moves import input
try:
    import dnf
except ImportError:  # pragma: no cover
    # dnf is not available on EL 7.
    dnf = None  # pragma: no cover
import koji
import requests.exceptions
import six

from fedora.client import AuthError, OpenIdBaseClient, FedoraClientError, ServerError
import fedora.client.openidproxyclient


log = logging.getLogger(__name__)

BASE_URL = 'https://bodhi.fedoraproject.org/'
STG_BASE_URL = 'https://bodhi.stg.fedoraproject.org/'
STG_OPENID_API = 'https://id.stg.fedoraproject.org/api/v1/'

UPDATE_ID_RE = r'FEDORA-(EPEL-)?\d{4,4}'
UPDATE_TITLE_RE = r'(\.el|\.fc)\d\d?'


class BodhiClientException(FedoraClientError):
    """Used to indicate there was an error in the client."""


class UpdateNotFound(BodhiClientException):
    """Used to indicate that a referenced Update is not found on the server."""

    def __init__(self, update):
        """Initialize the Exception."""
        self.update = six.text_type(update)

    def __unicode__(self):
        """
        Return a human readable error message.

        Returns:
            unicode: An error message.
        """
        return u'Update not found: {}'.format(self.update)

    # Use __unicode__ method under __str__ name for Python 3
    __str__ = __unicode__


class ComposeNotFound(BodhiClientException):
    """Used to indicate that a referenced Compose is not found on the server."""

    def __init__(self, release, request):
        """Initialize the Exception."""
        self.release = six.text_type(release)
        self.request = six.text_type(request)

    def __unicode__(self):
        """
        Return a human readable error message.

        Returns:
            unicode: An error message.
        """
        return u'Compose with request "{1}" not found for release "{0}"'.format(
            self.release, self.request
        )

    # Use __unicode__ method under __str__ name for Python 3
    __str__ = __unicode__


def errorhandled(method):
    """Raise exceptions on failure. Used as a decorator for BodhiClient methods."""
    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        try:
            result = method(*args, **kwargs)
            # Bodhi allows comments to be written by unauthenticated users if they solve a Captcha.
            # Due to this, an authentication error is not raised by the server if the client fails
            # to authenticate for any reason, and instead an error about needing a captcha key is
            # presented instead. If we see that error, we can just raise an AuthError to trigger the
            # retry logic in the exception handler below.
            if 'errors' in result:
                for error in result['errors']:
                    if 'name' in error and error['name'] == 'captcha_key':
                        raise AuthError('Captcha key needed.')
        except AuthError:
            # An AuthError can be raised for four different reasons:
            #
            # 0) The password is wrong.
            # 1) The session cookies are expired. fedora.python does not handle this automatically.
            # 2) The session cookies are not expired, but are no longer valid (for example, this can
            #    happen if the server's auth secret has changed.)
            # 3) The client received a captcha_key error, as described in the try block above.
            #
            # We don't know the difference between the cases here, but case #1 is fairly common and
            # we can work around it and case #2 by removing the session cookies and csrf token and
            # retrying the request. If the password is wrong, the second attempt will also fail but
            # we won't guard it and the AuthError will still be raised.
            args[0]._session.cookies.clear()
            args[0].csrf_token = None
            result = method(*args, **kwargs)

        if 'errors' not in result:
            return result

        # Otherwise, there was a problem...
        problems = 'An unhandled error occurred in the BodhiClient'
        try:
            problems = "\n".join([e['description'] for e in result['errors']])
        except Exception:
            pass
        raise BodhiClientException(problems)
    return wrapper


def _days_since(data_str):
    """
    Return number of days since the datetime passed as input in the form '%Y-%m-%d %H:%M:%S'.

    This can be used to calculate how many days an update is in current state by passing
    directly the 'date_pushed' or 'date_submitted' from the Update object.
    This is also useful to easily mock the output, since datetime.datetime.utcnow()
    cannot be mocked.

    Args:
        data_str (basestring): The 'date_pushed' or 'date_submitted' from the Update object.

    Returns:
        int: Number of days since the date in input.
    """
    update_time = datetime.datetime.strptime(data_str, '%Y-%m-%d %H:%M:%S')
    return (datetime.datetime.utcnow() - update_time).days


class BodhiClient(OpenIdBaseClient):
    """Python bindings to the Bodhi server REST API."""

    def __init__(self, base_url=BASE_URL, username=None, password=None, staging=False, **kwargs):
        """
        Initialize the Bodhi client.

        Args:
            base_url (basestring): The URL of the Bodhi server to connect to. Ignored if
                                   ```staging``` is True.
            username (basestring): The username to use to authenticate with the server.
            password (basestring): The password to use to authenticate with the server.
            staging (bool): If True, use the staging server. If False, use base_url.
            kwargs (dict): Other keyword arguments to pass on to
                           :class:`fedora.client.OpenIdBaseClient`
        """
        if staging:
            fedora.client.openidproxyclient.FEDORA_OPENID_API = STG_OPENID_API
            base_url = STG_BASE_URL

        if base_url[-1] != '/':
            base_url = base_url + '/'

        super(BodhiClient, self).__init__(base_url, login_url=base_url + 'login', username=username,
                                          **kwargs)

        self._password = password
        self.csrf_token = None

    @property
    def password(self):
        """
        Return the user's password.

        If the user's password is not known, prompt the user for their password.

        Returns:
            basestring: The user's password.
        """
        if not self._password:
            self._password = getpass.getpass()
        return self._password

    @errorhandled
    def save(self, **kwargs):
        """
        Save an update.

        This entails either creating a new update, or editing an existing one.
        To edit an existing update, you must specify the update title in
        the ``edited`` keyword argument.

        Args:
            builds (basestring): A list of koji builds for this update.
            type (basestring): The type of this update: ``security``, ``bugfix``,
                ``enhancement``, and ``newpackage``.
            bugs (basestring): A list of Red Hat Bugzilla ID's associated with this
                update.
            notes (basestring): Details as to why this update exists.
            request (basestring): Request for this update to change state, either to
                ``testing``, ``stable``, ``unpush``, ``obsolete`` or None.
            close_bugs (bool): Close bugs when update is stable.
            suggest (basestring): Suggest that the user reboot or logout after update.
                (``reboot``, ``logout``).
            inheritance (bool): Follow koji build inheritance, which may result in
                this update being pushed out to additional releases.
            autokarma (bool): Allow bodhi to automatically change the state of this
                update based on the ``karma`` from user feedback.  It will
                push your update to ``stable`` once it reaches the ``stable_karma``
                and unpush your update when reaching ``unstable_karma``.
            stable_karma (int): The upper threshold for marking an update as
                ``stable``.
            unstable_karma (int): The lower threshold for unpushing an update.
            edited (basestring): The update title of the existing update that we are
                editing.
            severity (basestring): The severity of this update (``urgent``, ``high``,
                ``medium``, ``low``).
            requirements (basestring): A list of required Taskotron tests that must pass
                for this update to reach stable. (e.g. ``dist.rpmdeplint``,
                ``dist.upgradepath``, ``dist.rpmlint``, etc).
            require_bugs (bool): A boolean to require that all of the bugs in your
                update have been confirmed by testers.
            require_testcases (bool): A boolean to require that this update passes
                all test cases before reaching stable.
        Returns:
            munch.Munch: The Bodhi server's response to the request.
        """
        kwargs['csrf_token'] = self.csrf()
        if 'type_' in kwargs:
            # backwards compat
            kwargs['type'] = kwargs['type_']
        return self.send_request('updates/', verb='POST', auth=True,
                                 data=kwargs)

    @errorhandled
    def request(self, update, request):
        """
        Request an update state change.

        Args:
            update (basestring): The title of the update.
            request (basestring): The request (``testing``, ``batched``, ``stable``, ``obsolete``,
                ``unpush``, ``revoke``).
        Returns:
            munch.Munch: The response from Bodhi to the request.
        Raises:
            UpdateNotFound: If the server returns a 404 error code.
        """
        try:
            return self.send_request('updates/{0}/request'.format(update),
                                     verb='POST', auth=True,
                                     data={'update': update, 'request': request,
                                           'csrf_token': self.csrf()})
        except fedora.client.ServerError as exc:
            if exc.code == 404:
                # The Bodhi server gave us a 404 on the resource, so let's raise an UpdateNotFound.
                raise UpdateNotFound(update)
            else:
                raise

    @errorhandled
    def waive(self, update, comment, tests=None):
        """
        Waive unsatisfied requirements on an update.

        Args:
            update (basestring): The title of the update.
            comment (basestring): A comment explaining the waiver.
            tests (tuple(basestring) or None): The list of unsatisfied requirements
                to waive. If not specified, all unsatisfied requirements of this
                update will be waived.
        Returns:
            munch.Munch: The response from Bodhi to the request.
        Raises:
            UpdateNotFound: If the server returns a 404 error code.
        """
        data = {'update': update, 'tests': tests, 'comment': comment, 'csrf_token': self.csrf()}
        try:
            return self.send_request('updates/{0}/waive-test-results'.format(update),
                                     verb='POST', auth=True, data=data)
        except fedora.client.ServerError as exc:
            if exc.code == 404:
                # The Bodhi server gave us a 404 on the resource, so let's raise an UpdateNotFound.
                raise UpdateNotFound(update)
            else:
                raise

    @errorhandled
    def query(self, **kwargs):
        """
        Query bodhi for a list of updates.

        Args:
            title (basestring): The update title.
            alias (basestring): The update alias.
            updateid (basestring): The update ID (eg: FEDORA-2015-0001).
            content_type (basestring): A content type (rpm, module) to limit the query to.
            releases (basestring): A comma separated list of releases that you wish to query updates
                for.
            active_releases (bool): A boolean to filter only updates for active releases.
            status (basestring): The update status (``pending``, ``testing``, ``stable``,
                ``obsolete``, ``unpushed``, ``processing``)
            type (basestring): The type of the update: ``security``, ``bugfix``,
                ``enhancement``, and ``newpackage``.
            bugs (basestring): A comma separated list of Red Hat Bugzilla IDs.
            request (basestring): An update request to query for
                ``testing``, ``stable``, ``unpush``, ``obsolete`` or None.
            mine (bool): If True, only query the users updates. Default: False.
            packages (basestring): A space or comma delimited list of package names.
            limit (int): A deprecated argument, sets ``rows_per_page``. See its docstring for more
                info.
            approved_before (basestring): A datetime string.
            approved_since (basestring): A datetime string.
            builds (basestring): A space or comma delimited string of build nvrs.
            critpath (bool): A boolean to query only critical path updates.
            cves (basestring): Filter by CVE IDs.
            locked (bool): A boolean to filter only locked updates.
            modified_before (basestring): A datetime string to query updates that have been modified
                before a certain time.
            modified_since (basestring): A datetime string to query updates that have been modified
                since a certain time.
            pushed (bool): A boolean to filter only pushed updates.
            pushed_before (basestring): A datetime string to filter updates pushed before a certain
                time.
            pushed_since (basestring): A datetime string to filter updates pushed since a
                certain time.
            severity (basestring): A severity type to filter by (``unspecified``,
                ``urgent``, ``high``, ``medium``, ``low``).
            submitted_before (basestring): A datetime string to filter updates submitted
                before a certain time.
            submitted_since (basestring): A datetime string to filter updates submitted
                after a certain time.
            suggest (basestring): Query for updates that suggest a user restart
                (``logout``, ``reboot``).
            user (basestring): Query for updates submitted by a specific user.
            rows_per_page (int): Limit the results to a certain number of rows per page
                (min:1 max: 100 default: 20).
            page (int): Return a specific page of results.
        Returns:
            munch.Munch: The response from Bodhi describing the query results.
        """
        if 'title' in kwargs:
            kwargs['like'] = kwargs['title']
            del kwargs['title']
        # bodhi1 compat
        if 'limit' in kwargs:
            kwargs['rows_per_page'] = kwargs['limit']
            del(kwargs['limit'])
        # 'mine' may be in kwargs, but set False
        if kwargs.get('mine'):
            kwargs['user'] = self.username
        if 'package' in kwargs:
            # for Bodhi 1, 'package' could be a package name, build, or
            # update ID, so try and figure it out
            if re.search(UPDATE_TITLE_RE, kwargs['package']):
                kwargs['builds'] = kwargs['package']
            elif re.search(UPDATE_ID_RE, kwargs['package']):
                kwargs['updateid'] = kwargs['package']
            else:
                kwargs['packages'] = kwargs['package']
            del(kwargs['package'])
        if 'release' in kwargs:
            if isinstance(kwargs['release'], list):
                kwargs['releases'] = kwargs['release']
            else:
                kwargs['releases'] = [kwargs['release']]
            del(kwargs['release'])
        if 'type_' in kwargs:
            kwargs['type'] = kwargs['type_']
            del(kwargs['type_'])
        # Old Bodhi CLI set bugs default to "", but new Bodhi API
        # checks for 'if bugs is not None', not 'if not bugs'
        if 'bugs' in kwargs and kwargs['bugs'] == '':
            kwargs['bugs'] = None
        return self.send_request('updates/', verb='GET', params=kwargs)

    def get_test_status(self, update):
        """
        Query bodhi for the test status of the specified update..

        Args:
            update (basestring): The title or identifier of the update to
                retrieve the test status of.
        Returns:
            munch.Munch: The response from Bodhi describing the query results.
        """
        return self.send_request('updates/%s/get-test-results' % update, verb='GET')

    @errorhandled
    def comment(self, update, comment, karma=0, email=None):
        """
        Add a comment to an update.

        Args:
            update (basestring): The title of the update comment on.
            comment (basestring): The text of the comment to add to the update.
            karma (int): The amount of karma to leave. May be -1, 0, or 1. Defaults to 0.
            email (basestring or None): Email address for an anonymous user. If an email address is
                supplied here, the comment is added as anonymous (i.e. not a logged in user).
        Returns:
            munch.Munch: The response from the post to comments/.
        """
        return self.send_request(
            'comments/', verb='POST', auth=True,
            data={'update': update, 'text': comment, 'karma': karma, 'email': email,
                  'csrf_token': self.csrf()})

    @errorhandled
    def save_override(self, nvr, duration, notes, edit=False, expired=False):
        """
        Save a buildroot override.

        This entails either creating a new buildroot override, or editing an
        existing one.

        Args:
            nvr (basestring): The nvr of a koji build.
            duration (int): Number of days from now that this override should
                expire.
            notes (basestring): Notes about why this override is in place.
            edit (bool): True if we are editing an existing override, False otherwise. Defaults to
                False.
            expired (bool): Set to True to expire an override. Defaults to False.
        Returns:
            munch.Munch: A dictionary-like representation of the saved override.
        """
        expiration_date = datetime.datetime.utcnow() + \
            datetime.timedelta(days=duration)
        data = {'nvr': nvr,
                'expiration_date': expiration_date,
                'notes': notes,
                'csrf_token': self.csrf()}
        if edit:
            data['edited'] = nvr
        if expired:
            data['expired'] = expired
        return self.send_request(
            'overrides/', verb='POST', auth=True, data=data)

    @errorhandled
    def get_compose(self, release, request):
        """
        Get information about compose.

        Args:
            release (basestring): The name of the release.
            request (basestring): The request (``testing``, ``stable``).
        Returns:
            munch.Munch: The response from Bodhi to the request.
        Raises:
            ComposeNotFound: If the server returns a 404 error code.
        """
        try:
            return self.send_request('composes/{}/{}'.format(release, request), verb='GET')
        except fedora.client.ServerError as exc:
            if exc.code == 404:
                # The Bodhi server gave us a 404 on the resource, so let's raise an ComposeNotFound.
                raise ComposeNotFound(release, request)
            else:
                raise

    @errorhandled
    def list_composes(self):
        """
        List composes.

        Returns:
            munch.Munch: A dictionary-like representation of the Composes.
        """
        return self.send_request('composes/', verb='GET')

    @errorhandled
    def list_overrides(self, user=None, packages=None,
                       expired=None, releases=None, builds=None,
                       rows_per_page=None, page=None):
        """
        List buildroot overrides.

        Args:
            user (basestring): A username whose buildroot overrides you want returned.
            packages (basestring): Comma separated package names to filter buildroot overrides by.
            expired (bool): If True, only return expired overrides. If False, only return active
                overrides.
            releases (basestring): Comma separated Release shortnames to filter buildroot overrides
                by.
            builds (basestring): Comma separated build NVRs to filter overrides by.
            rows_per_page (int): Limit the results to a certain number of rows per page.
                (default:None)
            page (int): Return a specific page of results.
                (default:None)
        """
        params = {}
        if user:
            params['user'] = user
        if packages:
            params['packages'] = packages
        if expired is not None:
            params['expired'] = expired
        if releases:
            params['releases'] = releases
        if builds:
            params['builds'] = builds
        if rows_per_page:
            params['rows_per_page'] = rows_per_page
        if page:
            params['page'] = page
        return self.send_request('overrides/', verb='GET', params=params)

    def init_username(self):
        """
        Check to see if the username attribute on self is set, and set if if it is not.

        If the username is already set on self, return.

        If the username is not already set on self, attempt to find if there is a username that has
        successfully authenticated in the Fedora session file. If that doesn't work, fall back to
        prompting the terminal for a username. Once the username has been set, re-run
        self._load_cookies() so we can re-use the user's last session.
        """
        if not self.username:
            if os.path.exists(fedora.client.openidbaseclient.b_SESSION_FILE):
                with open(fedora.client.openidbaseclient.b_SESSION_FILE) as session_cache:
                    try:
                        sc = json.loads(session_cache.read())
                    except ValueError:
                        # If the session cache can't be decoded as JSON, it could be corrupt or
                        # empty. Either way we can't use it, so let's just pretend it's empty.
                        sc = {}
                for key in sc.keys():
                    if key.startswith(self.base_url) and sc[key]:
                        self.username = key.split('{}:'.format(self.base_url))[1]
                        break

            if not self.username:
                self.username = input('Username: ')

            self._load_cookies()

    @errorhandled
    def csrf(self):
        """
        Return the CSRF token if alread aquired, otherwise login, get a CSRF, cache it, and return.

        If there is already a CSRF token, this method returns it.

        If there is not, this method ensures that we know the username, logs in if we aren't already
        logged in aquires and caches a CSRF token, and returns it.
        """
        if not self.csrf_token:
            self.init_username()
            if not self.has_cookies():
                self.login(self.username, self.password)
            self.csrf_token = self.send_request(
                'csrf', verb='GET', auth=True)['csrf_token']
        return self.csrf_token

    def parse_file(self, input_file):
        """
        Parse an update template file.

        Args:
            input_file (basestring): The filename of the update template.
        Returns:
            list: A list of dictionaries of parsed update values which
                can be directly passed to the ``save`` method.
        Raises:
            ValueError: If the ``input_file`` does not exist, or if it cannot be parsed.
        """
        if not os.path.exists(input_file):
            raise ValueError("No such file or directory: %s" % input_file)

        defaults = dict(severity='unspecified', suggest='unspecified')
        config = configparser.ConfigParser(defaults=defaults)
        read = config.read(input_file)

        if len(read) != 1 or read[0] != input_file:
            raise ValueError("Invalid input file: %s" % input_file)

        updates = []

        for section in config.sections():
            update = {
                'builds': section,
                'bugs': config.get(section, 'bugs', raw=True),
                'close_bugs': config.getboolean(section, 'close_bugs'),
                'type': config.get(section, 'type', raw=True),
                'type_': config.get(section, 'type', raw=True),
                'request': config.get(section, 'request', raw=True),
                'severity': config.get(section, 'severity', raw=True),
                'notes': config.get(section, 'notes', raw=True),
                'autokarma': config.get(section, 'autokarma', raw=True),
                'stable_karma': config.get(section, 'stable_karma', raw=True),
                'unstable_karma': config.get(
                    section, 'unstable_karma', raw=True),
                'suggest': config.get(section, 'suggest', raw=True)}

            updates.append(update)

        return updates

    @errorhandled
    def latest_builds(self, package):
        """
        Get the latest builds for a package.

        Args:
            package (basestring): The package name, for example "kernel".
        Returns:
            munch.Munch: A dict-like object of the release dist tag to the
                latest build.
        """
        return self.send_request('latest_builds', params={'package': package})

    def testable(self):
        """
        Return a generator that iterates installed testing updates.

        This method is a generator that yields packages that you currently
        have installed that you have yet to test and provide feedback for.

        Only works on systems with dnf.

        Returns:
            generator: An iterable of dictionaries describing updates that match builds installed on
                the local system.
        Raises:
            RuntimeError: If the dnf Python bindings are not installed.
        """
        if dnf is None:
            raise RuntimeError('dnf is required by this method and is not installed.')

        base = dnf.Base()
        sack = base.fill_sack(load_system_repo=True)
        query = sack.query()
        installed = query.installed()
        with open('/etc/fedora-release', 'r') as f:
            fedora = f.readlines()[0].split()[2]
        tag = 'f%s-updates-testing' % fedora
        builds = self.get_koji_session().listTagged(tag, latest=True)
        for build in builds:
            pkgs = installed.filter(name=build['name'], version=build['version'],
                                    release=build['release']).run()
            if len(pkgs):
                update_list = self.query(builds=build['nvr'])['updates']
                for update in update_list:
                    yield update

    @staticmethod
    def compose_str(compose, minimal=True):
        """
        Return a string representation of a compose.

        Args:
            compose (dict): A dictionary representation of a Compose.
            minimal (bool): If True, return a minimal one-line representation of the compose.
                Otherwise, return a more verbose string. Defaults to True.
        Returns:
            basestring: A human readable string describing the compose.
        """
        line_formatter = '{0:<16}: {1}'
        security = '*' if compose['security'] else ' '
        title = "{security}{release}-{request}".format(
            security=security,
            release=compose['release']['name'], request=compose['request'])
        details = "{count:3d} updates ({state}) ".format(state=compose['state'],
                                                         count=len(compose['update_summary']))
        minimal_repr = line_formatter.format(title, details)

        if minimal:
            return minimal_repr

        line_formatter = '{0:>12}: {1}\n'

        compose_lines = ['{:=^80}\n'.format('='), '     {}\n'.format(minimal_repr)]
        compose_lines.append('{:=^80}\n'.format('='))

        compose_lines += [
            line_formatter.format('Content Type', compose['content_type']),
            line_formatter.format('Started', compose['date_created']),
            line_formatter.format('Updated', compose['state_date']),
        ]

        if 'error_message' in compose and compose['error_message']:
            compose_lines.append(line_formatter.format('Error', compose['error_message']))

        compose_lines += ['\nUpdates:\n\n']
        line_formatter = '\t{}'.format(line_formatter)
        for s in compose['update_summary']:
            compose_lines.append(line_formatter.format(s['alias'], s['title']))

        return ''.join(compose_lines)

    @staticmethod
    def override_str(override, minimal=True):
        """
        Return a string representation of a given override dictionary.

        Args:
            override (dict): An override dictionary.
            minimal (bool): If True, return a minimal one-line representation of the override.
                Otherwise, return a more verbose string. Defaults to True.
        Returns:
            basestring: A human readable string describing the given override.
        """
        if isinstance(override, six.string_types):
            return override

        if minimal:
            return "{submitter}'s {build} override (expires {expiry})".format(
                submitter=override['submitter']['name'],
                build=override['build']['nvr'],
                expiry=override['expiration_date'],
            )

        val = "%s\n%s\n%s\n" % ('=' * 60, '\n'.join(
            textwrap.wrap(override['build']['nvr'].replace(',', ', '), width=60,
                          initial_indent=' ' * 5, subsequent_indent=' ' * 5)), '=' * 60)
        val += "  Submitter: {}\n".format(override['submitter']['name'])
        val += "  Expiration Date: {}\n".format(override['expiration_date'])
        val += "  Notes: {}\n".format(override['notes'])
        val += "  Expired: {}".format(override['expired_date'] is not None)

        return val

    def update_str(self, update, minimal=False):
        """
        Return a string representation of a given update dictionary.

        Args:
            update (dict): An update dictionary, acquired by the ``list`` method.
            minimal (bool): If True, return a minimal one-line representation of the update.
                Otherwise, return a more verbose representation. Defaults to False.
        Returns:
            basestring: A human readable string describing the given update.
        """
        if isinstance(update, six.string_types):
            return update
        if minimal:
            val = ""
            security = '*' if update['type'] == u'security' else ' '
            date = update['date_pushed'] and update['date_pushed'].split()[0] \
                or update['date_submitted'].split()[0]
            days_in_status = _days_since(update['date_pushed']) if update['date_pushed'] \
                else _days_since(update['date_submitted'])
            val += '%s%-40s %-9s  %-8s  %10s (%d)' % (
                security, update['builds'][0]['nvr'], update['content_type'],
                update['status'], date, days_in_status)
            for build in update['builds'][1:]:
                val += '\n  %s' % build['nvr']
            return val

        # Content will be formatted as wrapped lines, each line is in format
        #    indent            content wrap width
        #  |--> 12 <--|  |-->        66       .... <--|
        # "            : wrapped line ...              "
        #  |-->          80 chars in total         <--|
        wrap_width = 66
        wrap_line = functools.partial(textwrap.wrap, width=wrap_width)
        line_formatter = u'{0:>12}: {1}\n'

        update_lines = ['{:=^80}\n'.format('=')]
        update_lines += [
            line + '\n' for line in textwrap.wrap(
                update['title'].replace(',', ', '),
                width=80,
                initial_indent=' ' * 5,
                subsequent_indent=' ' * 5)
        ]
        update_lines.append('{:=^80}\n'.format('='))

        if update['alias']:
            update_lines.append(
                line_formatter.format('Update ID', update['alias']))

        update_lines += [
            line_formatter.format('Content Type', update['content_type']),
            line_formatter.format('Release', update['release']['long_name']),
            line_formatter.format('Status', update['status']),
            line_formatter.format('Type', update['type']),
            line_formatter.format('Severity', update['severity']),
            line_formatter.format('Karma', update['karma']),
            line_formatter.format('Autokarma', '{0}  [{1}, {2}]'.format(
                update['autokarma'], update['unstable_karma'], update['stable_karma']))
        ]

        try:
            test_status = self.get_test_status(update['alias'])
        except (ServerError, requests.exceptions.RequestException) as err:
            log.debug('ERROR while retrieving CI status: %s', err)
            test_status = None

        if test_status:
            info = None
            if 'errors' in test_status:
                info = '\n'.join([el.description for el in test_status.errors])
            elif 'decision' in test_status:
                info = test_status.decision.summary
            else:
                log.debug('No `errors` nor `decision` in the data returned')
            if info:
                update_lines.append(line_formatter.format('CI Status', info))

        if update['request'] is not None:
            update_lines.append(line_formatter.format('Request', update['request']))

        if len(update['bugs']):
            bugs = list(itertools.chain(*[
                wrap_line('{0} - {1}'.format(bug['bug_id'], bug['title']))
                for bug in update['bugs']
            ]))
            indent_lines = ['Bugs'] + [' '] * (len(bugs) - 1)
            update_lines += [
                line_formatter.format(indent, line)
                for indent, line in six.moves.zip(indent_lines, bugs)
            ]

        if update['notes']:
            notes_lines = list(itertools.chain(
                *[wrap_line(update['notes'])]
            ))
            indent_lines = ['Notes'] + [' '] * (len(notes_lines) - 1)
            for indent, line in six.moves.zip(indent_lines, notes_lines):
                update_lines.append(line_formatter.format(indent, line))

        update_lines += [
            line_formatter.format('Submitter', update['user']['name']),
            line_formatter.format('Submitted', update['date_submitted']),
        ]

        if len(update['comments']):
            comments_lines = []
            for comment in update['comments']:
                anonymous = " (unauthenticated)" if comment['anonymous'] else ''
                comments_lines.append('{0}{1} - {2} (karma {3})'.format(
                    comment['user']['name'], anonymous,
                    comment['timestamp'], comment['karma']))
                comments_lines += wrap_line(comment['text'])

            update_lines.append(line_formatter.format('Comments', comments_lines[0]))
            comment_line_formatter = line_formatter.replace(': ', '  ')
            update_lines += [
                comment_line_formatter.format(indent, line)
                for indent, line in six.moves.zip(
                    itertools.repeat(' ', len(comments_lines) - 1),
                    comments_lines[1:])
            ]

        if update['alias']:
            update_lines.append(
                '\n  {0}updates/{1}\n'.format(self.base_url, update['alias']))
        else:
            update_lines.append(
                '\n  {0}updates/{1}\n'.format(self.base_url, update['title']))

        return ''.join(update_lines)

    @errorhandled
    def get_releases(self, **kwargs):
        """
        Return a list of bodhi releases.

        This method returns a dictionary in the following format::

            {"releases": [
                {"dist_tag": "dist-f12", "id_prefix": "FEDORA",
                 "locked": false, "name": "F12", "long_name": "Fedora 12"}]}

        Args:
            kwargs (dict): A dictionary of extra parameters to pass along with the request.
        Returns:
            dict: A dictionary describing Bodhi's release objects.
        """
        return self.send_request('releases/', verb='GET', params=kwargs)

    def get_koji_session(self):
        """
        Return an authenticated koji session.

        Returns:
            koji.ClientSession: An intialized authenticated koji client.
        """
        config = ConfigParser()
        if os.path.exists(os.path.join(os.path.expanduser('~'), '.koji', 'config')):
            config.readfp(open(os.path.join(os.path.expanduser('~'), '.koji', 'config')))
        else:
            config.readfp(open('/etc/koji.conf'))
        session = koji.ClientSession(config.get('koji', 'server'))
        return session

    koji_session = property(fget=get_koji_session)

    def candidates(self):
        """
        Get a list list of update candidates.

        Returns:
            list: A list of koji builds (dictionaries returned by koji.listTagged()) that are tagged
            as candidate builds and are owned by the current user.
        """
        self.init_username()
        builds = []
        data = self.get_releases()
        koji = self.get_koji_session()
        for release in data['releases']:
            try:
                for build in koji.listTagged(release['candidate_tag'], latest=True):
                    if build['owner_name'] == self.username:
                        builds.append(build)
            except Exception:
                log.exception('Unable to query candidate builds for %s' % release)
        return builds
