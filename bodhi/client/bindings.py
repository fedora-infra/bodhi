# Copyright © 2007-2019 Red Hat, Inc. and others.
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

import configparser
import datetime
import functools
import getpass
import itertools
import json
import logging
import os
import re
import textwrap
import typing

from fedora.client import AuthError, OpenIdBaseClient, FedoraClientError, ServerError
try:
    import dnf
except ImportError:  # pragma: no cover
    # dnf is not available on EL 7.
    dnf = None  # pragma: no cover
import fedora.client.openidproxyclient
import koji
import requests.exceptions

if typing.TYPE_CHECKING:  # pragma: no cover
    import munch  # noqa: 401


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

    def __init__(self, update: str):
        """
        Initialize the Exception.

        Args:
            update: The alias of the update that was not found.
        """
        self.update = update

    def __str__(self) -> str:
        """
        Return a human readable error message.

        Returns:
            An error message.
        """
        return f'Update not found: {self.update}'


class ComposeNotFound(BodhiClientException):
    """Used to indicate that a referenced Compose is not found on the server."""

    def __init__(self, release: str, request: str):
        """
        Initialize the Exception.

        Args:
            release: The release component of the compose that was not found.
            request: The request component of the compose that was not found.
        """
        self.release = release
        self.request = request

    def __str__(self) -> str:
        """
        Return a human readable error message.

        Returns:
            An error message.
        """
        return f'Compose with request "{self.request}" not found for release "{self.release}"'


def errorhandled(method: typing.Callable) -> typing.Callable:
    """Raise exceptions on failure. Used as a decorator for BodhiClient methods."""
    @functools.wraps(method)
    def wrapper(*args, **kwargs) -> typing.Any:
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


def _days_since(data_str: str) -> int:
    """
    Return number of days since the datetime passed as input in the form '%Y-%m-%d %H:%M:%S'.

    This can be used to calculate how many days an update is in current state by passing
    directly the 'date_pushed' or 'date_submitted' from the Update object.
    This is also useful to easily mock the output, since datetime.datetime.utcnow()
    cannot be mocked.

    Args:
        data_str: The 'date_pushed' or 'date_submitted' from the Update object.

    Returns:
        Number of days since the date in input.
    """
    update_time = datetime.datetime.strptime(data_str, '%Y-%m-%d %H:%M:%S')
    return (datetime.datetime.utcnow() - update_time).days


class BodhiClient(OpenIdBaseClient):
    """Python bindings to the Bodhi server REST API."""

    def __init__(self, base_url: str = BASE_URL, username: typing.Optional[str] = None,
                 password: typing.Optional[str] = None, staging: bool = False,
                 openid_api: typing.Optional[str] = None, **kwargs):
        """
        Initialize the Bodhi client.

        Args:
            base_url: The URL of the Bodhi server to connect to. Ignored if
                      ```staging``` is True.
            username: The username to use to authenticate with the server.
            password: The password to use to authenticate with the server.
            staging: If True, use the staging server. If False, use base_url.
            openid_api: If not None, the URL to an OpenID API to use to authenticate
                to Bodhi. Ignored if staging is True.
            kwargs: Other keyword arguments to pass on to
                    :class:`fedora.client.OpenIdBaseClient`
        """
        if openid_api:
            fedora.client.openidproxyclient.FEDORA_OPENID_API = openid_api

        if staging:
            fedora.client.openidproxyclient.FEDORA_OPENID_API = STG_OPENID_API
            base_url = STG_BASE_URL

        if base_url[-1] != '/':
            base_url = base_url + '/'

        super(BodhiClient, self).__init__(base_url, login_url=base_url + 'login', username=username,
                                          **kwargs)

        self._password = password
        self.csrf_token = ''

    @property
    def password(self) -> str:
        """
        Return the user's password.

        If the user's password is not known, prompt the user for their password.

        Returns:
            The user's password.
        """
        if not self._password:
            self._password = getpass.getpass()
        return self._password

    @errorhandled
    def save(self, **kwargs) -> 'munch.Munch':
        """
        Save an update.

        This entails either creating a new update, or editing an existing one.
        To edit an existing update, you must specify the update alias in
        the ``edited`` keyword argument.

        Args:
            display_name (str): The name of the update.
            builds (str): A list of koji builds for this update.
            type (str): The type of this update: ``security``, ``bugfix``,
                ``enhancement``, and ``newpackage``.
            bugs (str): A list of Red Hat Bugzilla ID's associated with this
                update.
            notes (str): Details as to why this update exists.
            request (str): Request for this update to change state, either to
                ``testing``, ``stable``, ``unpush``, ``obsolete`` or None.
            close_bugs (bool): Close bugs when update is stable.
            suggest (str): Suggest that the user reboot or logout after update.
                (``reboot``, ``logout``).
            autotime (bool): Allow bodhi to automatically change the state of this
                update based on the time spent in testing by this update. It
                will push your update to ``stable`` once it reaches the ``stable_days``.
            stable_days (int): The minimun amount of time an update has to spend in
                ``testing`` before being automatically pushed to ``stable``.
            autokarma (bool): Allow bodhi to automatically change the state of this
                update based on the ``karma`` from user feedback.  It will
                push your update to ``stable`` once it reaches the ``stable_karma``
                and unpush your update when reaching ``unstable_karma``.
            stable_karma (int): The upper threshold for marking an update as
                ``stable``.
            unstable_karma (int): The lower threshold for unpushing an update.
            edited (str): The update alias of the existing update that we are
                editing.
            severity (str): The severity of this update (``urgent``, ``high``,
                ``medium``, ``low``).
            requirements (str): A list of required Taskotron tests that must pass
                for this update to reach stable. (e.g. ``dist.rpmdeplint``,
                ``dist.upgradepath``, ``dist.rpmlint``, etc).
            require_bugs (bool): A boolean to require that all of the bugs in your
                update have been confirmed by testers.
            require_testcases (bool): A boolean to require that this update passes
                all test cases before reaching stable.
            from_tag (str): The name of a Koji tag from which to pull builds
                instead of providing them manually in `builds`.
        Returns:
            The Bodhi server's response to the request.
        """
        kwargs['csrf_token'] = self.csrf()
        if 'type_' in kwargs:
            # backwards compat
            kwargs['type'] = kwargs['type_']
        return self.send_request('updates/', verb='POST', auth=True,
                                 data=kwargs)

    @errorhandled
    def request(self, update: str, request: str) -> 'munch.Munch':
        """
        Request an update state change.

        Args:
            update: The alias of the update.
            request: The request (``testing``, ``stable``, ``obsolete``, ``unpush``, ``revoke``).
        Returns:
            The response from Bodhi to the request.
        Raises:
            UpdateNotFound: If the server returns a 404 error code.
        """
        try:
            return self.send_request(f'updates/{update}/request',
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
    def waive(self, update: str, comment: str,
              tests: typing.Optional[typing.Iterable[str]] = None) -> 'munch.Munch':
        """
        Waive unsatisfied requirements on an update.

        Args:
            update: The alias of the update.
            comment: A comment explaining the waiver.
            tests: The list of unsatisfied requirements to waive. If not specified, all unsatisfied
                   requirements of this update will be waived.
        Returns:
            The response from Bodhi to the request.
        Raises:
            UpdateNotFound: If the server returns a 404 error code.
        """
        data = {'update': update, 'tests': tests, 'comment': comment, 'csrf_token': self.csrf()}
        try:
            return self.send_request(f'updates/{update}/waive-test-results',
                                     verb='POST', auth=True, data=data)
        except fedora.client.ServerError as exc:
            if exc.code == 404:
                # The Bodhi server gave us a 404 on the resource, so let's raise an UpdateNotFound.
                raise UpdateNotFound(update)
            else:
                raise

    @errorhandled
    def trigger_tests(self, update: str) -> 'munch.Munch':
        """
        Trigger tests for update.

        Args:
            update: The alias of the update to run tests for.
        Returns:
            The response from the post to trigger_tests/.
        """
        try:
            return self.send_request(
                f'updates/{update}/trigger-tests', verb='POST', auth=True,
                data={'update': update, 'csrf_token': self.csrf()})
        except fedora.client.ServerError as exc:
            if exc.code == 404:
                # The Bodhi server gave us a 404 on the resource, so let's raise an UpdateNotFound.
                raise UpdateNotFound(update)
            else:
                raise

    @errorhandled
    def query(self, **kwargs) -> 'munch.Munch':
        """
        Query bodhi for a list of updates.

        Args:
            alias (str): The update alias.
            updateid (str): The update ID (eg: FEDORA-2015-0001).
            content_type (str): A content type (rpm, module) to limit the query to.
            releases (str): A comma separated list of releases that you wish to query updates
                for.
            status (str): The update status (``pending``, ``testing``, ``stable``,
                ``obsolete``, ``unpushed``)
            type (str): The type of the update: ``security``, ``bugfix``,
                ``enhancement``, and ``newpackage``.
            bugs (str): A comma separated list of Red Hat Bugzilla IDs.
            request (str): An update request to query for
                ``testing``, ``stable``, ``unpush``, ``obsolete`` or None.
            mine (bool): If True, only query the users updates. Default: False.
            packages (str): A space or comma delimited list of package names.
            limit (int): A deprecated argument, sets ``rows_per_page``. See its docstring for more
                info.
            approved_before (str): A datetime string.
            approved_since (str): A datetime string.
            builds (str): A space or comma delimited string of build nvrs.
            critpath (bool): A boolean to query only critical path updates.
            locked (bool): A boolean to filter only locked updates.
            modified_before (str): A datetime string to query updates that have been modified
                before a certain time.
            modified_since (str): A datetime string to query updates that have been modified
                since a certain time.
            pushed (bool): A boolean to filter only pushed updates.
            pushed_before (str): A datetime string to filter updates pushed before a certain
                time.
            pushed_since (str): A datetime string to filter updates pushed since a
                certain time.
            severity (str): A severity type to filter by (``unspecified``,
                ``urgent``, ``high``, ``medium``, ``low``).
            submitted_before (str): A datetime string to filter updates submitted
                before a certain time.
            submitted_since (str): A datetime string to filter updates submitted
                after a certain time.
            suggest (str): Query for updates that suggest a user restart
                (``logout``, ``reboot``).
            user (str): Query for updates submitted by a specific user.
            rows_per_page (int): Limit the results to a certain number of rows per page
                (min:1 max: 100 default: 20).
            page (int): Return a specific page of results.
        Returns:
            The response from Bodhi describing the query results.
        """
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

    def get_test_status(self, update: str) -> 'munch.Munch':
        """
        Query bodhi for the test status of the specified update..

        Args:
            update: The alias of the update to retrieve the test status of.
        Returns:
            The response from Bodhi describing the query results.
        """
        return self.send_request(f'updates/{update}/get-test-results', verb='GET')

    @errorhandled
    def comment(self, update: str, comment: str, karma: int = 0) -> 'munch.Munch':
        """
        Add a comment to an update.

        Args:
            update: The alias of the update comment on.
            comment: The text of the comment to add to the update.
            karma: The amount of karma to leave. May be -1, 0, or 1. Defaults to 0.
        Returns:
            The response from the post to comments/.
        """
        return self.send_request(
            'comments/', verb='POST', auth=True,
            data={'update': update, 'text': comment, 'karma': karma, 'csrf_token': self.csrf()})

    @errorhandled
    def save_override(self, nvr: str, duration: int, notes: str, edit: bool = False,
                      expired: bool = False) -> 'munch.Munch':
        """
        Save a buildroot override.

        This entails either creating a new buildroot override, or editing an
        existing one.

        Args:
            nvr: The nvr of a koji build.
            duration: Number of days from now that this override should expire.
            notes: Notes about why this override is in place.
            edit: True if we are editing an existing override, False otherwise. Defaults to False.
            expired: Set to True to expire an override. Defaults to False.
        Returns:
            A dictionary-like representation of the saved override.
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
    def get_compose(self, release: str, request: str) -> 'munch.Munch':
        """
        Get information about compose.

        Args:
            release: The name of the release.
            request: The request (``testing``, ``stable``).
        Returns:
            The response from Bodhi to the request.
        Raises:
            ComposeNotFound: If the server returns a 404 error code.
        """
        try:
            return self.send_request(f'composes/{release}/{request}', verb='GET')
        except fedora.client.ServerError as exc:
            if exc.code == 404:
                # The Bodhi server gave us a 404 on the resource, so let's raise an ComposeNotFound.
                raise ComposeNotFound(release, request)
            else:
                raise

    @errorhandled
    def list_composes(self) -> 'munch.Munch':
        """
        List composes.

        Returns:
            A dictionary-like representation of the Composes.
        """
        return self.send_request('composes/', verb='GET')

    @errorhandled
    def list_overrides(
            self, user: typing.Optional[str] = None, packages: typing.Optional[str] = None,
            expired: typing.Optional[bool] = None, releases: typing.Optional[str] = None,
            builds: typing.Optional[str] = None, rows_per_page: typing.Optional[int] = None,
            page: typing.Optional[int] = None) -> 'munch.Munch':
        """
        List buildroot overrides.

        Args:
            user: A username whose buildroot overrides you want returned.
            packages: Comma separated package names to filter buildroot overrides by.
            expired: If True, only return expired overrides. If False, only return active
                overrides.
            releases: Comma separated Release shortnames to filter buildroot overrides by.
            builds: Comma separated build NVRs to filter overrides by.
            rows_per_page: Limit the results to a certain number of rows per page.
            page: Return a specific page of results.
        Returns:
            A dictionary-like representation of the Overrides.
        """
        params: typing.MutableMapping[str, typing.Union[int, str, None]] = {}
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
                        self.username = key.split(f'{self.base_url}:')[1]
                        break

            if not self.username:
                self.username = input('Username: ')

            self._load_cookies()

    @errorhandled
    def csrf(self) -> str:
        """
        Return CSRF token if already acquired, otherwise login, get a CSRF, cache it, and return.

        If there is already a CSRF token, this method returns it.

        If there is not, this method ensures that we know the username, logs in if we aren't already
        logged in acquires and caches a CSRF token, and returns it.

        Returns:
            The CSRF token.
        """
        if not self.csrf_token:
            self.init_username()
            if not self.has_cookies():
                self.login(self.username, self.password)
            self.csrf_token = self.send_request(
                'csrf', verb='GET', auth=True)['csrf_token']
        return self.csrf_token

    def parse_file(self, input_file: str) -> typing.List[typing.Dict[str, typing.Any]]:
        """
        Parse an update template file.

        Args:
            input_file: The filename of the update template.
        Returns:
            A list of dictionaries of parsed update values which
                can be directly passed to the ``save`` method.
        Raises:
            ValueError: If the ``input_file`` does not exist, or if it cannot be parsed.
        """
        if not os.path.exists(input_file):
            raise ValueError(f"No such file or directory: {input_file}")

        defaults = dict(severity='unspecified', suggest='unspecified')
        config = configparser.ConfigParser(defaults=defaults)
        read = config.read(input_file)

        if len(read) != 1 or read[0] != input_file:
            raise ValueError(f"Invalid input file: {input_file}")

        updates = []

        for section in config.sections():
            update = {
                'builds': section,
                'bugs': config.get(section, 'bugs', raw=True),
                'close_bugs': config.getboolean(section, 'close_bugs'),
                'display_name': config.get(section, 'display_name', raw=True, fallback=None),
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
    def latest_builds(self, package: str) -> 'munch.Munch':
        """
        Get the latest builds for a package.

        Args:
            package: The package name, for example "kernel".
        Returns:
            A dict-like object of the release dist tag to the latest build.
        """
        return self.send_request('latest_builds', params={'package': package})

    def testable(self) -> typing.Iterator[dict]:
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
        tag = f'f{fedora}-updates-testing'
        builds = self.get_koji_session().listTagged(tag, latest=True)
        for build in builds:
            pkgs = installed.filter(name=build['name'], version=build['version'],
                                    release=build['release']).run()
            if len(pkgs):
                update_list = self.query(builds=build['nvr'])['updates']
                for update in update_list:
                    yield update

    @staticmethod
    def compose_str(compose: dict, minimal: bool = True) -> str:
        """
        Return a string representation of a compose.

        Args:
            compose: A dictionary representation of a Compose.
            minimal: If True, return a minimal one-line representation of the compose.
                Otherwise, return a more verbose string. Defaults to True.
        Returns:
            A human readable string describing the compose.
        """
        line_formatter = '{0:<16}: {1}'
        security = '*' if compose['security'] else ' '
        title = f"{security}{compose['release']['name']}-{compose['request']}"
        details = f"{len(compose['update_summary']):3d} updates ({compose['state']}) "
        minimal_repr = line_formatter.format(title, details)

        if minimal:
            return minimal_repr

        line_formatter = '{0:>12}: {1}\n'

        compose_lines = [f'{"=":=^80}\n', f'     {minimal_repr}\n', f'{"=":=^80}\n']

        compose_lines += [
            line_formatter.format('Content Type', compose['content_type']),
            line_formatter.format('Started', compose['date_created']),
            line_formatter.format('Updated', compose['state_date']),
        ]

        if 'error_message' in compose and compose['error_message']:
            compose_lines.append(line_formatter.format('Error', compose['error_message']))

        compose_lines += ['\nUpdates:\n\n']
        line_formatter = f'\t{line_formatter}'
        for s in compose['update_summary']:
            compose_lines.append(line_formatter.format(s['alias'], s['title']))

        return ''.join(compose_lines)

    @staticmethod
    def override_str(override: dict, minimal: bool = True) -> str:
        """
        Return a string representation of a given override dictionary.

        Args:
            override: An override dictionary.
            minimal: If True, return a minimal one-line representation of the override.
                Otherwise, return a more verbose string. Defaults to True.
        Returns:
            A human readable string describing the given override.
        """
        if isinstance(override, str):
            return override

        if minimal:
            return (f"{override['submitter']['name']}'s {override['build']['nvr']} override "
                    f"(expires {override['expiration_date']})")

        divider = '=' * 60
        nvr = '\n'.join(textwrap.wrap(override['build']['nvr'].replace(',', ', '), width=60,
                        initial_indent=' ' * 5, subsequent_indent=' ' * 5))
        val = f"{divider}\n{nvr}\n{divider}\n"
        val += f"  Submitter: {override['submitter']['name']}\n"
        val += f"  Expiration Date: {override['expiration_date']}\n"
        val += f"  Notes: {override['notes']}\n"
        val += f"  Expired: {override['expired_date'] is not None}"

        return val

    def update_str(self, update: dict, minimal: bool = False) -> str:
        """
        Return a string representation of a given update dictionary.

        Args:
            update: An update dictionary, acquired by the ``list`` method.
            minimal: If True, return a minimal one-line representation of the update.
                Otherwise, return a more verbose representation. Defaults to False.
        Returns:
            A human readable string describing the given update.
        """
        if isinstance(update, str):
            return update
        if minimal:
            val = ""
            security = '*' if update['type'] == 'security' else ' '
            date = update['date_pushed'] and update['date_pushed'].split()[0] \
                or update['date_submitted'].split()[0]
            days_in_status = _days_since(update['date_pushed']) if update['date_pushed'] \
                else _days_since(update['date_submitted'])
            if update['builds']:
                title = update['builds'][0]['nvr']
            else:
                title = update['title'] or update['alias']
            content_type = update['content_type'] or 'unspecified'
            val += (f"{security}{title:40} {content_type:9}  "
                    f"{update['status']:8}  {date:>10} ({days_in_status})")
            for build in update['builds'][1:]:
                val += f"\n  {build['nvr']}"
            return val

        # Content will be formatted as wrapped lines, each line is in format
        #    indent            content wrap width
        #  |--> 12 <--|  |-->        66       .... <--|
        # "            : wrapped line ...              "
        #  |-->          80 chars in total         <--|
        wrap_width = 66
        wrap_line = functools.partial(textwrap.wrap, width=wrap_width)
        line_formatter = '{0:>12}: {1}\n'

        update_lines = [f'{"=":=^80}\n']
        update_lines += [
            line + '\n' for line in textwrap.wrap(
                update['title'],
                width=80,
                initial_indent=' ' * 5,
                subsequent_indent=' ' * 5)
        ]
        update_lines.append(f'{"=":=^80}\n')

        update_lines.append(
            line_formatter.format('Update ID', update['alias']))

        update_lines += [
            line_formatter.format('Content Type', update['content_type']),
            line_formatter.format('Release', update['release']['long_name']),
            line_formatter.format('Status', update['status']),
            line_formatter.format('Type', update['type']),
            line_formatter.format('Severity', update['severity']),
            line_formatter.format('Karma', update['karma']),
            line_formatter.format(
                'Autokarma',
                f"{update['autokarma']}  [{update['unstable_karma']}, {update['stable_karma']}]")
        ]

        try:
            test_status = self.get_test_status(update['alias'])
        except (ServerError, requests.exceptions.RequestException) as err:
            log.debug('ERROR while retrieving CI status: %s', err)
            test_status = None

        if test_status:
            info = None
            waivers = None
            if 'errors' in test_status:
                info = '\n'.join([el.description for el in test_status.errors])
            elif 'decision' in test_status:
                info = test_status.decision.summary
                waivers = test_status.decision.waivers
            else:
                log.debug('No `errors` nor `decision` in the data returned')
            if info:
                update_lines.append(line_formatter.format('CI Status', info))
            if waivers:
                waivers_lines = []
                for waiver in waivers:
                    dt = datetime.datetime.strptime(waiver['timestamp'], '%Y-%m-%dT%H:%M:%S.%f')
                    waivers_lines.append(
                        f"{waiver['username']} - {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                    waivers_lines += wrap_line(waiver['comment'])
                    waivers_lines.append(f"build: {waiver['subject_identifier']}")
                    waivers_lines.append(f"testcase: {waiver['testcase']}")

                update_lines.append(line_formatter.format('Waivers', waivers_lines[0]))
                waiver_line_formatter = line_formatter.replace(': ', '  ')
                update_lines += [
                    waiver_line_formatter.format(indent, line)
                    for indent, line in zip(
                        itertools.repeat(' ', len(waivers_lines) - 1),
                        waivers_lines[1:])
                ]

        if update['request'] is not None:
            update_lines.append(line_formatter.format('Request', update['request']))

        if len(update['bugs']):
            bugs = list(itertools.chain(*[
                wrap_line(f"{bug['bug_id']} - {bug['title']}")
                for bug in update['bugs']
            ]))
            indent_lines = ['Bugs'] + [' '] * (len(bugs) - 1)
            update_lines += [
                line_formatter.format(indent, line)
                for indent, line in zip(indent_lines, bugs)
            ]

        if update['notes']:
            notes_lines = list(itertools.chain(
                *[wrap_line(line) for line in update['notes'].splitlines()]
            ))
            indent_lines = ['Notes'] + [' '] * (len(notes_lines) - 1)
            for indent, line in zip(indent_lines, notes_lines):
                update_lines.append(line_formatter.format(indent, line))

        update_lines += [
            line_formatter.format('Submitter', update['user']['name']),
            line_formatter.format('Submitted', update['date_submitted']),
        ]

        if len(update['comments']):
            comments_lines = []
            for comment in update['comments']:
                comments_lines.append(
                    f"{comment['user']['name']} - {comment['timestamp']} "
                    f"(karma {comment['karma']})")
                comments_lines += wrap_line(comment['text'])

            update_lines.append(line_formatter.format('Comments', comments_lines[0]))
            comment_line_formatter = line_formatter.replace(': ', '  ')
            update_lines += [
                comment_line_formatter.format(indent, line)
                for indent, line in zip(
                    itertools.repeat(' ', len(comments_lines) - 1),
                    comments_lines[1:])
            ]

        update_lines.append(
            f"\n  {self.base_url}updates/{update['alias']}\n")

        return ''.join(update_lines)

    @errorhandled
    def get_releases(self, **kwargs) -> 'munch.Munch':
        """
        Return a list of bodhi releases.

        This method returns a dictionary in the following format::

            {"releases": [
                {"dist_tag": "dist-f12", "id_prefix": "FEDORA",
                 "locked": false, "name": "F12", "long_name": "Fedora 12"}]}

        Args:
            kwargs: A dictionary of extra parameters to pass along with the request.
        Returns:
            A dictionary describing Bodhi's release objects.
        """
        return self.send_request('releases/', verb='GET', params=kwargs)

    def get_koji_session(self) -> koji.ClientSession:
        """
        Return an authenticated koji session.

        Returns:
            An initialized authenticated koji client.
        """
        config = configparser.ConfigParser()
        if os.path.exists(os.path.join(os.path.expanduser('~'), '.koji', 'config')):
            config.readfp(open(os.path.join(os.path.expanduser('~'), '.koji', 'config')))
        else:
            config.readfp(open('/etc/koji.conf'))
        session = koji.ClientSession(config.get('koji', 'server'))
        return session

    koji_session = property(fget=get_koji_session)

    def candidates(self) -> typing.Iterable[dict]:
        """
        Get a list list of update candidates.

        Returns:
            A list of koji builds (dictionaries returned by koji.listTagged()) that are tagged
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
                log.exception('Unable to query candidate builds for %s', release)
        return builds
