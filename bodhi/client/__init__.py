# Copyright © 2014-2019 Red Hat, Inc. and others.
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
"""The bodhi CLI client."""

import logging
import os
import platform
import subprocess
import sys
import traceback
import re
import functools

from fedora.client import AuthError, openidproxyclient
import click
import munch

from bodhi.client import bindings


log = logging.getLogger(__name__)


def _warn_if_url_or_openid_and_staging_set(ctx, param, value):
    """
    Print a warning to stderr if the user has set both the --url/--openid-api and --staging flags.

    This ensures that the user is aware that --staging supersedes --url/--openid-api.

    Args:
        ctx (click.core.Context): The Click context, used to find out if the --staging flag is set.
        param (click.core.Option): The option being handled.
        value (unicode): The value of the option being handled.
    Returns:
        unicode: The value of the option being handled.
    """
    if ctx.params.get('staging', False) and (param.name in ['url', 'openid_api']) and \
            value is not None:
        click.echo(f'\nWarning: {param.name} and staging flags are '
                   f'both set. {param.name} will be ignored.\n',
                   err=True)
    if param.name == 'staging' and value:
        if ctx.params.get('url', False):
            click.echo(f'\nWarning: url and staging flags are both set. url will be ignored.\n',
                       err=True)
        if ctx.params.get('openid_api', False):
            click.echo('\nWarning: openid_api and staging flags '
                       'are both set. openid_api will be ignored.\n',
                       err=True)
    return value


def _set_logging_debug(ctx, param, value):
    """
    Set up the logging level to "debug".

    This allows us to print more information on the user's screen and thus helps following what is
    going on.

    Args:
        ctx (click.core.Context): The Click context. Unused.
        param (click.core.Option): The option being handled. Unused.
        value (bool): The value of the --debug flag.
    Returns:
        bool: The value of the --debug flag.
    """
    if value:
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        log.addHandler(ch)
        log.setLevel(logging.DEBUG)
    return value


url_option = click.option('--url', envvar='BODHI_URL', default=bindings.BASE_URL,
                          help=('URL of a Bodhi server. Ignored if --staging is set. Can be set '
                                'with BODHI_URL environment variable'),
                          callback=_warn_if_url_or_openid_and_staging_set)
openid_option = click.option(
    '--openid-api', envvar='BODHI_OPENID_API',
    default=openidproxyclient.FEDORA_OPENID_API,
    help=('URL of an OpenID API to use to authenticate to Bodhi. Ignored if --staging is set. Can '
          'be set with BODHI_OPENID_API environment variable'),
    callback=_warn_if_url_or_openid_and_staging_set)
staging_option = click.option('--staging', help='Use the staging bodhi instance',
                              is_flag=True, default=False,
                              callback=_warn_if_url_or_openid_and_staging_set)
debug_option = click.option('--debug', help='Display debugging information.',
                            is_flag=True, default=False,
                            callback=_set_logging_debug)


new_edit_options = [
    click.option('--user'),
    click.option('--password', hide_input=True),
    click.option('--severity', help='Update severity',
                 type=click.Choice(['unspecified', 'low', 'medium', 'high', 'urgent']),
                 is_eager=True),
    click.option('--notes', help='Update description'),
    click.option('--notes-file', help='Update description from a file'),
    click.option('--bugs', help='Comma-separated list of bug numbers', default=''),
    click.option('--close-bugs', is_flag=True, help='Automatically close bugs'),
    click.option('--request', help='Requested repository',
                 type=click.Choice(['testing', 'stable', 'unpush'])),
    click.option('--autokarma', is_flag=True, help='Enable karma automatism'),
    click.option('--stable-karma', type=click.INT, help='Stable karma threshold'),
    click.option('--unstable-karma', type=click.INT, help='Unstable karma threshold'),
    click.option('--requirements',
                 help='Space or comma-separated list of required Taskotron tasks'),
    click.option('--suggest', help='Post-update user suggestion',
                 type=click.Choice(['logout', 'reboot'])),
    click.option('--display-name',
                 help='The name of the update'),
    staging_option]


# Common options for the overrides save and edit command
save_edit_options = [
    click.argument('nvr'),
    click.option('--duration', default=7, type=click.INT,
                 help='Number of days the override should exist.'),
    click.option('--notes', default="No explanation given...",
                 help='Notes on why this override is in place.'),
    click.option('--user'),
    click.option('--password', hide_input=True),
    click.option('--wait/--no-wait', is_flag=True, default=True,
                 help='Wait and ensure that the override is active'),
    openid_option,
    staging_option,
    url_option,
    debug_option]


# Basic options for pagination of query result
pagination_options = [
    click.option('--rows', default=None,
                 type=click.IntRange(1, 100, clamp=False),
                 help='Limits number of results shown per page'),
    click.option('--page', default=None,
                 type=click.IntRange(1, clamp=False),
                 help='Go to page number')]


# Common releases options
release_options = [
    click.option('--user'),
    click.option('--password', hide_input=True),
    click.option('--name', help='Release name (eg: F20)'),
    click.option('--long-name', help='Long release name (eg: "Fedora 20")'),
    click.option('--id-prefix', help='Release prefix (eg: FEDORA)'),
    click.option('--version', help='Release version number (eg: 20)'),
    click.option('--branch', help='Git branch name (eg: f20)'),
    click.option('--dist-tag', help='Koji dist tag (eg: f20)'),
    click.option('--stable-tag', help='Koji stable tag (eg: f20-updates)'),
    click.option('--testing-tag',
                 help='Koji testing tag (eg: f20-updates-testing)'),
    click.option('--candidate-tag',
                 help='Koji candidate tag (eg: f20-updates-candidate)'),
    click.option('--pending-stable-tag',
                 help='Koji pending tag (eg: f20-updates-pending)'),
    click.option('--pending-testing-tag',
                 help='Koji pending testing tag (eg: f20-updates-pending-testing)'),
    click.option('--pending-signing-tag',
                 help='Koji pending signing tag (eg: f20-updates-pending-signing)'),
    click.option('--override-tag', help='Koji override tag (eg: f20-override)'),
    click.option('--state', type=click.Choice(['disabled', 'pending', 'current',
                                               'archived']),
                 help='The state of the release'),
    click.option('--mail-template', help='Name of the email template for this release'),
    click.option('--composed-by-bodhi/--not-composed-by-bodhi', is_flag=True, default=True,
                 help='The flag that indicates whether the release is composed by Bodhi or not'),
    click.option('--package-manager', type=click.Choice(['unspecified', 'dnf', 'yum']),
                 help='The package manager used by this release'),
    click.option('--testing-repository',
                 help='The name of the testing repository used to test updates'),
    click.option(
        '--create-automatic-updates/--no-create-automatic-updates',
        help=('Configure for this release, whether or not automatic updates are '
              'created for builds which are tagged into its Koji candidate tag.'),
        is_flag=True, default=False),
    openid_option,
    staging_option,
    url_option,
    debug_option]


def add_options(options):
    """
    Generate a click.option decorator with the given options.

    Given a list of click options this creates a decorator that
    will return a function used to add the options to a click command.

    Args:
        options (list): A list of click.options decorators.
    Returns:
        callable: A decorator that applies the given options to it decorated function.
    """
    def _add_options(func):
        """
        Decorate func with the given click options.

        Given a click command and a list of click options this will
        return the click command decorated with all the options in the list.

        Args:
            func (callable): A click command function.
        Returns:
            callable: A wrapped version of func with added options.
        """
        for option in reversed(options):
            func = option(func)
        return func
    return _add_options


def handle_errors(method):
    """
    Echo neat error messages on AuthError or BodhiClientException.

    This is intended to be used as a decorator on method.

    Args:
        method (callable): The method we wish to handle errors from.
    Returns:
        callable: A wrapped version of method that handles errors.
    """
    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        """
        Call method with given args and kwargs, handling errors and exit if any are raised.

        AuthErrors will cause an exit code of 1. BodhiClientExceptions will result in 2.
        Args:
            args: Positional arguments to pass to method.
            kwargs: Keyword arguments to pass to method.
        """
        try:
            method(*args, **kwargs)
        except AuthError as e:
            click.secho(f"{e}: Check your FAS username & password", fg='red', bold=True)
            sys.exit(1)
        except bindings.BodhiClientException as e:
            click.secho(str(e), fg='red', bold=True)
            sys.exit(2)
    return wrapper


def _save_override(url, user, password, staging, edit=False, openid_api=None, **kwargs):
    """
    Create or edit a buildroot override.

    Args:
        url (unicode): The URL of a Bodhi server. Ignored if staging is True.
        user (unicode): The username to authenticate as.
        password (unicode): The user's password.
        staging (bool): Whether to use the staging server or not.
        edit (bool): Set to True to edit an existing buildroot override.
        kwargs (dict): Other keyword arguments passed to us by click.
    """
    client = bindings.BodhiClient(base_url=url, username=user, password=password, staging=staging,
                                  openid_api=openid_api)
    resp = client.save_override(nvr=kwargs['nvr'],
                                duration=kwargs['duration'],
                                notes=kwargs['notes'],
                                edit=edit,
                                expired=kwargs.get('expire', False))

    if kwargs['wait']:
        print_resp(resp, client, override_hint=False)
        command = _generate_wait_repo_command(resp, client)
        if command:
            click.echo(f"\n\nRunning {' '.join(command)}\n")
            ret = subprocess.call(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if ret:
                click.echo(f"WARNING: ensuring active override failed for {resp.build.nvr}")
                sys.exit(ret)
    else:
        print_resp(resp, client, override_hint=True)


@click.group()
@click.version_option(message='%(version)s')
def cli():
    # Docs that show in the --help
    """Command line tool for interacting with Bodhi."""
    # Developer Docs
    """Create the main CLI group."""
    pass  # pragma: no cover


@cli.group()
def composes():
    # Docs that show in the --help
    """Interact with composes."""
    # Developer Docs
    """Create the composes group."""
    pass  # pragma: no cover


@composes.command(name='info')
@handle_errors
@click.argument('release')
@click.argument('request')
@url_option
@debug_option
@staging_option
def info_compose(release, request, url, **kwargs):
    """Retrieve and print info about a compose."""
    client = bindings.BodhiClient(base_url=url, staging=kwargs['staging'])

    try:
        resp = client.get_compose(release, request)
    except bindings.ComposeNotFound as exc:
        raise click.BadParameter(str(exc), param_hint='RELEASE/REQUEST')

    print_resp(resp, client)


@composes.command(name='list')
@handle_errors
@staging_option
@click.option('-v', '--verbose', is_flag=True, default=False, help='Display more information.')
@url_option
@debug_option
def list_composes(url, staging, verbose, debug):
    # User docs for the CLI
    """
    List composes.

    Asterisks next to composes indicate that they contain security updates.
    """
    # developer docs
    """
    Args:
        url (unicode): The URL of a Bodhi server. Ignored if staging is True.
        staging (bool): Whether to use the staging server or not.
        verbose (bool): Whether to show verbose output or not.
        debug (bool): If the --debug flag was set
    """
    client = bindings.BodhiClient(base_url=url, staging=staging)
    print_resp(client.list_composes(), client, verbose)


@cli.group()
def updates():
    # Docs that show in the --help
    """Interact with updates on Bodhi."""
    # Developer Docs
    """Create the updates group."""
    pass  # pragma: no cover


def require_severity_for_security_update(type, severity):
    """
    Print an error message if the user did not provide severity for a security update.

    Args:
        type (unicode): The value of the update 'type'.
        severity (unicode): The value of the update 'severity'.
    """
    if type == 'security' and severity not in ('low', 'medium', 'high', 'urgent'):
        raise click.BadParameter('must specify severity for a security update',
                                 param_hint='severity')


@updates.command()
@click.option('--type', default='bugfix', help='Update type', required=True,
              type=click.Choice(['security', 'bugfix', 'enhancement', 'newpackage']))
@add_options(new_edit_options)
@click.argument('builds')
@click.option('--file', help='A text file containing all the update details')
@handle_errors
@openid_option
@url_option
@debug_option
def new(user, password, url, debug, openid_api, **kwargs):
    # User Docs that show in the --help
    """
    Create a new update.

    BUILDS: a comma separated list of Builds to be added to the update
    (e.g. 0ad-0.0.21-4.fc26,2ping-3.2.1-4.fc26)
    """
    # Developer Docs
    """
    Args:
        user (unicode): The username to authenticate as.
        password (unicode): The user's password.
        url (unicode): The URL of a Bodhi server. Ignored if staging is True.
        debug (bool): If the --debug flag was set
        openid_api (str): A URL for an OpenID API to use to authenticate to Bodhi.
        kwargs (dict): Other keyword arguments passed to us by click.
    """

    client = bindings.BodhiClient(base_url=url, username=user, password=password,
                                  staging=kwargs['staging'], openid_api=openid_api)

    if kwargs['file'] is None:
        updates = [kwargs]

    else:
        updates = client.parse_file(os.path.abspath(kwargs['file']))

    kwargs['notes'] = _get_notes(**kwargs)

    if not kwargs['notes'] and not kwargs['file']:
        click.echo("ERROR: must specify at least one of --file, --notes, or --notes-file")
        sys.exit(1)

    for update in updates:
        require_severity_for_security_update(type=update['type'], severity=update['severity'])
        try:
            resp = client.save(**update)
            print_resp(resp, client)
        except bindings.BodhiClientException as e:
            click.echo(str(e))
        except Exception:
            traceback.print_exc()


def _validate_edit_update(ctx, param, value):
    """
    Validate the update argument given to the updates edit command.

    The update argument can only be an update id.

    Args:
        param (basestring): The name of the parameter being validated. Unused.
        value (basestring): The value of the value being validated.
    Returns:
        basestring: The value if it passes validation.
    Raises:
        click.BadParameter: If the value is invalid.
    """
    if re.search(bindings.UPDATE_ID_RE, value):
        return value
    else:
        raise click.BadParameter("Please provide an Update ID")


@updates.command()
@click.option('--type', help='Update type',
              type=click.Choice(['security', 'bugfix', 'enhancement', 'newpackage']))
@click.option('--addbuilds', help='Add Comma-separated list of build nvr')
@click.option('--removebuilds', help='Remove Comma-separated list of build nvr')
@add_options(new_edit_options)
@click.argument('update', callback=_validate_edit_update)
@openid_option
@url_option
@debug_option
@handle_errors
def edit(user, password, url, debug, openid_api, **kwargs):
    # User Docs that show in the --help
    """
    Edit an existing update.

    UPDATE: The alias of the update (e.g. FEDORA-2017-f8e0ef2850)
    """
    # Developer Docs
    """
    The update argument must be an update id.

    Args:
        user (unicode): The username to authenticate as.
        password (unicode): The user's password.
        url (unicode): The URL of a Bodhi server. Ignored if staging is True.
        debug (bool): If the --debug flag was set
        openid_api (str): A URL for an OpenID API to use to authenticate to Bodhi.
        kwargs (dict): Other keyword arguments passed to us by click.
    """
    client = bindings.BodhiClient(base_url=url, username=user, password=password,
                                  staging=kwargs['staging'], openid_api=openid_api)

    kwargs['notes'] = _get_notes(**kwargs)

    try:
        query_param = {'updateid': kwargs['update']}
        resp = client.query(**query_param)
        del(kwargs['update'])

        # Convert list of 'Bug' instances in DB to comma separated bug_ids for parsing.
        former_update = resp['updates'][0].copy()
        if not kwargs['bugs']:
            kwargs['bugs'] = ",".join([str(bug['bug_id']) for bug in former_update['bugs']])
            former_update.pop('bugs', None)

        kwargs['builds'] = [b['nvr'] for b in former_update['builds']]
        kwargs['edited'] = former_update['alias']
        if kwargs['addbuilds']:
            for build in kwargs['addbuilds'].split(','):
                if build not in kwargs['builds']:
                    kwargs['builds'].append(build)
        if kwargs['removebuilds']:
            for build in kwargs['removebuilds'].split(','):
                kwargs['builds'].remove(build)
        del kwargs['addbuilds']
        del kwargs['removebuilds']

        # Replace empty fields with former values from database.
        for field in kwargs:
            if kwargs[field] in (None, '') and field in former_update:
                kwargs[field] = former_update[field]

        require_severity_for_security_update(type=kwargs['type'], severity=kwargs['severity'])

        resp = client.save(**kwargs)
        print_resp(resp, client)
    except bindings.BodhiClientException as e:
        click.echo(str(e))


@updates.command()
@click.option('--updateid', help='Query by update ID (eg: FEDORA-2015-0001)')
@click.option('--alias', help='Query by alias')
@click.option('--approved-since', help='Approved after a specific timestamp')
@click.option('--approved-before', help='Approved before a specific timestamp')
@click.option('--modified-since', help='Modified after a specific timestamp')
@click.option('--modified-before', help='Modified before a specific timestamp')
@click.option('--builds', help='Query updates based on builds')
@click.option('--bugs', help='A list of bug numbers')
@click.option('--critpath', is_flag=True, default=None,
              help='Query only critical path packages')
@click.option('--packages', help='Query by package name(s)')
@click.option('--content-type', help='Query updates based on content type',
              type=click.Choice(['rpm', 'module']))  # And someday, container.
@click.option('--pushed', is_flag=True, default=None,
              help='Filter by pushed updates')
@click.option('--pushed-since',
              help='Updates that have been pushed after a certain time')
@click.option('--pushed-before',
              help='Updates that have been pushed before a certain time')
@click.option('--releases', help='Updates for specific releases')
@click.option('--locked', help='Updates that are in a locked state')
@click.option('--request', help='Updates with a specific request',
              type=click.Choice(['testing', 'stable', 'unpush']))
@click.option('--severity', help='Updates with a specific severity',
              type=click.Choice(['unspecified', 'urgent', 'high', 'medium', 'low']))
@click.option('--submitted-since',
              help='Updates that have been submitted since a certain time')
@click.option('--submitted-before',
              help='Updates that have been submitted before a certain time')
@click.option('--status', help='Filter by update status',
              type=click.Choice(['pending', 'testing', 'stable', 'obsolete',
                                 'unpushed']))
@click.option('--suggest', help='Filter by post-update user suggestion',
              type=click.Choice(['logout', 'reboot']))
@click.option('--type', default=None, help='Filter by update type',
              type=click.Choice(['newpackage', 'security', 'bugfix', 'enhancement']))
@click.option('--user', help='Updates submitted by a specific user')
@click.option('--mine', is_flag=True, help='Show only your updates')
@staging_option
@url_option
@debug_option
@add_options(pagination_options)
@handle_errors
def query(url, debug, mine=False, rows=None, **kwargs):
    # User Docs that show in the --help
    """Query updates on Bodhi.

    A leading '*' means that this is a 'security' update.

    The number between brackets next to the date indicates the number of days
    the update is in the current state.
    """
    # Developer Docs
    """
    Query updates based on flags.

    Args:
        url (unicode): The URL of a Bodhi server. Ignored if staging is True.
        mine (Boolean): If the --mine flag was set
        debug (Boolean): If the --debug flag was set
        kwargs (dict): Other keyword arguments passed to us by click.
    """
    client = bindings.BodhiClient(base_url=url, staging=kwargs['staging'])
    if mine:
        client.init_username()
        kwargs['user'] = client.username
    resp = client.query(rows_per_page=rows, **kwargs)
    print_resp(resp, client)


@updates.command()
@click.argument('update')
@click.argument('state')
@click.option('--user')
@click.option('--password', hide_input=True)
@openid_option
@staging_option
@url_option
@debug_option
@handle_errors
def request(update, state, user, password, url, openid_api, **kwargs):
    # User Docs that show in the --help
    """
    Change an update's request status.

    UPDATE: The alias of the update (e.g. FEDORA-2017-f8e0ef2850)

    STATE: The state you wish to change the update's request to. Valid options are
    testing, stable, obsolete, unpush, and revoke.
    """
    # Developer Docs
    """
    Change an update's request to the given state.

    Args:
        update (unicode): The update you wish to modify.
        state (unicode): The state you wish to change the update's request to. Valid options are
                         testing, stable, obsolete, unpush, and revoke.
        user (unicode): The username to authenticate as.
        password (unicode): The user's password.
        staging (bool): Whether to use the staging server or not.
        url (unicode): The URL of a Bodhi server. Ignored if staging is True.
        openid_api (str): The URL for an OpenID API to use to authenticate to Bodhi.
        kwargs (dict): Other keyword arguments passed to us by click.
    """
    client = bindings.BodhiClient(base_url=url, username=user, password=password,
                                  staging=kwargs['staging'], openid_api=openid_api)

    try:
        resp = client.request(update, state)
    except bindings.UpdateNotFound as exc:
        raise click.BadParameter(str(exc), param_hint='UPDATE')

    print_resp(resp, client)


@updates.command()
@click.argument('update')
@click.argument('text')
@click.option('--karma', default=0, type=click.INT, help='The karma for this comment (+1/0/-1)')
@click.option('--user')
@click.option('--password', hide_input=True)
@openid_option
@staging_option
@url_option
@debug_option
@handle_errors
def comment(update, text, karma, user, password, url, openid_api, **kwargs):
    # User Docs that show in the --help
    """
    Comment on an update.

    UPDATE: The alias of the update (e.g. FEDORA-2017-f8e0ef2850)

    TEXT: the comment to be added to the update
    """
    # Developer Docs
    """
    Comment on an update.

    Args:
        update (unicode): The update you wish to modify.
        text (unicode): The text of the comment you wish to leave on the update.
        karma (int): The karma you wish to leave on the update. Must be +1, 0, or -1.
        user (unicode): The username to authenticate as.
        password (unicode): The user's password.
        staging (bool): Whether to use the staging server or not.
        url (unicode): The URL of a Bodhi server. Ignored if staging is True.
        openid_api (str): The URL for an OpenID API to use to authenticate to Bodhi.
        kwargs (dict): Other keyword arguments passed to us by click.
    """

    client = bindings.BodhiClient(base_url=url, username=user, password=password,
                                  staging=kwargs['staging'], openid_api=openid_api)
    resp = client.comment(update, text, karma)
    print_resp(resp, client)


@updates.command()
@staging_option
@click.option('--arch',
              help=('Specify arch of packages to download, "all" will retrieve packages from all '
                    'architectures'))
@click.option('--debuginfo', is_flag=True, default=False,
              help=('Include debuginfo packages'))
@click.option('--updateid', help='Download update(s) by ID(s) (comma-separated list)')
@click.option('--builds', help='Download update(s) by build NVR(s) (comma-separated list)')
@url_option
@debug_option
@handle_errors
def download(url, **kwargs):
    # User Docs that show in the --help
    """Download the builds in one or more updates."""
    # Developer Docs
    """
    Download the builds for an update.

    Args:
        staging (bool):   Whether to use the staging server or not.
        arch (unicode):   Requested architecture of packages to download.
                          "all" will retrieve packages from all architectures.
        debuginfo (bool): Whether to include debuginfo packages.
        url (unicode):    The URL of a Bodhi server. Ignored if staging is True.
        kwargs (dict):    Other keyword arguments passed to us by click.
    """
    client = bindings.BodhiClient(base_url=url, staging=kwargs['staging'])
    requested_arch = kwargs['arch']
    debuginfo = kwargs['debuginfo']

    del(kwargs['staging'])
    del(kwargs['arch'])
    del(kwargs['debuginfo'])
    # At this point we need to have reduced the kwargs dict to only our
    # query options (updateid or builds)
    if not any(kwargs.values()):
        click.echo("ERROR: must specify at least one of --updateid or --builds")
        sys.exit(1)

    # As the query method doesn't let us construct OR queries, we're
    # gonna run one query for each option that was passed. The syntax
    # for this is a bit ugly, sorry.
    for (attr, value) in kwargs.items():
        if value:
            expecteds = len(value.split(','))
            resp = client.query(**{attr: value})
            if len(resp.updates) == 0:
                click.echo(f"WARNING: No {attr} found!")
            elif len(resp.updates) < expecteds:
                click.echo(f"WARNING: Some {attr} not found!")
            # Not sure if we need a check for > expecteds, I don't
            # *think* that should ever be possible for these opts.

            args = ['koji', 'download-build']
            if debuginfo:
                args.append('--debuginfo')
            for update in resp.updates:
                click.echo(f"Downloading packages from {update['alias']}")
                for build in update['builds']:
                    # subprocess is icky, but koji module doesn't
                    # expose this in any usable way, and we don't want
                    # to rewrite it here.
                    if requested_arch is None:
                        args.extend(['--arch=noarch',
                                     f'--arch={platform.machine()}', build['nvr']])
                    else:
                        if 'all' in requested_arch:
                            args.append(build['nvr'])
                        if 'all' not in requested_arch:
                            args.extend(['--arch=noarch',
                                         f'--arch={requested_arch}', build['nvr']])
                    ret = subprocess.call(args)
                    if ret:
                        click.echo(f"WARNING: download of {build['nvr']} failed!")


def _get_notes(**kwargs):
    """
    Return notes for the update.

    If the user provides a --notes-file, _get_notes processes the contents of the notes-file.
    If the user does not provide a --notes-file, _get_notes() returns the notes from the kwargs.
    One cannot specify both --notes and --notesfile. Doing so will result in an error.

    Args:
        kwargs (dict): Keyword arguments passed to us by click.

    :returns: the contents of the notes file or the notes from kwargs
    :rtype: string
    """
    if kwargs['notes_file'] is not None:
        if kwargs['notes'] is None:
            with open(kwargs['notes_file'], 'r') as fin:
                return fin.read()
        else:
            click.echo("ERROR: Cannot specify --notes and --notes-file")
            sys.exit(1)
    else:
        return kwargs['notes']


@updates.command()
@click.argument('update')
@click.argument('comment', required=False)
@click.option(
    '--show', is_flag=True, default=None,
    help="List all the required unsatisfied requirements")
@click.option(
    '--test', multiple=True,
    help="Waive the specific test(s), to automatically waive all unsatisfied "
    "requirements, specify --test=all")
@openid_option
@staging_option
@url_option
@debug_option
@handle_errors
def waive(update, show, test, comment, url, openid_api, **kwargs):
    # User Docs that show in the --help
    """
    Show or waive unsatified requirements (ie: missing or failing tests) on an existing update.

    UPDATE: The alias of the update (e.g. FEDORA-2017-f8e0ef2850)

    COMMENT: A comment explaining why the requirements were waived (mandatory with --test)
    """
    # Developer Docs
    """
    The update argument must be an update id..

    Args:
        update (unicode): The update who unsatisfied requirements wish to waive.
        show (boolean): Whether to show all missing required tests of the specified update.
        test (tuple(unicode)): Waive those specified tests or all of them if 'all' is specified.
        comment (unicode): A comment explaining the waiver.
        url (unicode): The URL of a Bodhi server. Ignored if staging is True.
        openid_api (str): The URL for an OpenID API to use to authenticate to Bodhi.
        kwargs (dict): Other keyword arguments passed to us by click.
    """
    client = bindings.BodhiClient(base_url=url, staging=kwargs['staging'], openid_api=openid_api)

    if show and test:
        click.echo(
            'ERROR: You can not list the unsatisfied requirements and waive them '
            'at the same time, please use either --show or --test=... but not both.')
        sys.exit(1)

    if show:
        test_status = client.get_test_status(update)
        if 'errors' in test_status:
            click.echo('One or more error occured while retrieving the unsatisfied requirements:')
            for el in test_status.errors:
                click.echo(f'  - {el.description}')
        elif 'decision' not in test_status:
            click.echo('Could not retrieve the unsatisfied requirements from bodhi.')
        else:
            click.echo(f'CI status: {test_status.decision.summary}')
            if test_status.decision.unsatisfied_requirements:
                click.echo('Missing tests:')
                for req in test_status.decision.unsatisfied_requirements:
                    click.echo(f'  - {req.testcase}')
            else:
                click.echo('Missing tests: None')
    else:
        if not comment:
            click.echo('ERROR: Comment are mandatory when waiving unsatisfied requirements')
            sys.exit(1)

        if 'all' in test:
            click.echo('Waiving all unsatisfied requirements')
            resp = client.waive(update, comment)
        else:
            click.echo(f"Waiving unsatisfied requirements: {', '.join(test)}")
            resp = client.waive(update, comment, test)
        print_resp(resp, client)


@cli.group()
def overrides():
    # Docs that show in the --help
    """Interact with overrides on Bodhi."""
    # Developer Docs
    """Create the overrides CLI group."""
    pass  # pragma: no cover


@overrides.command('query')
@click.option('--user', default=None,
              help='Overrides submitted by a specific user')
@staging_option
@click.option('--mine', is_flag=True,
              help='Show only your overrides.')
@click.option('--packages', default=None,
              help='Query by comma-separated package name(s)')
@click.option('--expired/--active', default=None,
              help='show only expired or active overrides')
@click.option('--releases', default=None,
              help='Query by release shortname(s). e.g. F26')
@click.option('--builds', default=None,
              help='Query by comma-separated build id(s)')
@url_option
@debug_option
@add_options(pagination_options)
@handle_errors
def query_buildroot_overrides(url, user=None, mine=False, packages=None,
                              expired=None, releases=None, builds=None,
                              rows=None, page=None, **kwargs):
    # Docs that show in the --help
    """Query the buildroot overrides."""
    # Developer Docs
    """
    Query the buildroot overrides.

    Args:
        user (unicode): If supplied, overrides for this user will be queried.
        staging (bool): Whether to use the staging server or not.
        mine (bool): Whether to use the --mine flag was given.
        url (unicode): The URL of a Bodhi server. Ignored if staging is True.
        packages (unicode): If supplied, the overrides for these package are queried
        expired (bool): If supplied, True returns only expired overrides, False only active.
        releases (unicode): If supplied, the overrides for these releases are queried.
        builds (unicode): If supplied, the overrides for these builds are queried.
        rows (unicode): The limit of rows displayed per page for query result.
        page (unicode): If supplied, returns the results for a specific page number.
        kwargs (dict): Other keyword arguments passed to us by click.
    """
    client = bindings.BodhiClient(base_url=url, staging=kwargs['staging'])
    if mine:
        client.init_username()
        user = client.username
    resp = client.list_overrides(user=user, packages=packages,
                                 expired=expired, releases=releases, builds=builds,
                                 rows_per_page=rows, page=page)
    print_resp(resp, client)


@overrides.command('save')
@add_options(save_edit_options)
@handle_errors
def save_buildroot_overrides(user, password, url, staging, openid_api, **kwargs):
    # Docs that show in the --help
    """
    Create a buildroot override.

    NVR: the NVR (name-version-release) of the buildroot override to create
    """
    # Developer Docs
    """
    Create a buildroot override.

    Args:
        user (unicode): The username to authenticate as.
        password (unicode): The user's password.
        url (unicode): The URL of a Bodhi server. Ignored if staging is True.
        staging (bool): Whether to use the staging server or not.
        openid_api (str): A URL for the OpenID API to authenticate with Bodhi.
        kwargs (dict): Other keyword arguments passed to us by click.
    """
    _save_override(url=url, user=user, password=password, staging=staging, openid_api=openid_api,
                   **kwargs)


@overrides.command('edit')
@add_options(save_edit_options)
@click.option('--expire', help='Expire the override', is_flag=True, default=False)
@handle_errors
def edit_buildroot_overrides(user, password, url, staging, openid_api, **kwargs):
    # Docs that show in the --help
    """
    Edit a buildroot override.

    NVR: the NVR (name-version-release) of the buildroot override to edit
    """
    # Developer Docs
    """
    Edit a buildroot override.

    Args:
        user (unicode): The username to authenticate as.
        password (unicode): The user's password.
        url (unicode): The URL of a Bodhi server. Ignored if staging is True.
        staging (bool): Whether to use the staging server or not.
        openid_api (str): A URL for the OpenID API to authenticate with Bodhi.
        kwargs (dict): Other keyword arguments passed to us by click.
    """
    _save_override(url=url, user=user, password=password, staging=staging, edit=True,
                   openid_api=openid_api, **kwargs)


def _generate_wait_repo_command(override, client):
    """
    Generate and return a koji wait-repo command for the given override, if possible.

    Args:
        override (munch.Munch): A Munch of the Override we want to print a hint about.
        client (bodhi.client.bindings.BodhiClient): A BodhiClient that we can use to query the
            server for Releases.
    Returns:
        tuple or None: If we know the release for the override's build, we return a tuple suitable
            for passing to subprocess.Popen for a koji command that will wait on the repo. If we
            can't we return None.
    """
    if 'release_id' in override.build:
        release = client.get_releases(ids=[override.build.release_id])['releases'][0]
        return ('koji', 'wait-repo', f'{release.dist_tag}-build',
                f'--build={override.build.nvr}')


def _print_override_koji_hint(override, client):
    """
    Print a human readable hint about how to use koji wait-repo to monitor an override, if possible.

    Note: The hint can only be generated if the server provides a 'release_id' on the
    override.build property. Older versions of the server did not include the release_id on
    Build objects during serialization, and those server versions also did not allow querying
    for releases by id. If override.build.release_id is not found, None will be returned.

    Args:
        override (munch.Munch): A Munch of the Override we want to print a hint about.
        client (bodhi.client.bindings.BodhiClient): A BodhiClient that we can use to query the
            server for Releases.
    """
    command = _generate_wait_repo_command(override, client)
    if command:
        click.echo(
            '\n\nUse the following to ensure the override is active:\n\n'
            f"\t$ {' '.join(command)}\n")


def print_resp(resp, client, verbose=False, override_hint=True):
    """
    Print a human readable rendering of the given server response to the terminal.

    Args:
        resp (munch.Munch): The response from the server.
        client (bodhi.client.bindings.BodhiClient): A BodhiClient.
        verbose (bool): If True, show more detailed output. Defaults to False.
        override_hint (bool): If True, show a hint to the user about how to wait on a buildroot
            override. Defaults to True.
    """
    if 'updates' in resp:
        if len(resp.updates) == 1:
            click.echo(client.update_str(resp.updates[0]))
        else:
            for update in resp.updates:
                click.echo(client.update_str(update, minimal=True))
        if 'total' in resp:
            click.echo(f'{resp.total} updates found ({len(resp.updates)} shown)')
    elif resp.get('update'):
        click.echo(client.update_str(resp['update']))
    elif resp.get('alias'):
        click.echo(client.update_str(resp))
    elif 'overrides' in resp:
        if len(resp.overrides) == 1:
            click.echo(client.override_str(resp.overrides[0], minimal=False))
            if override_hint:
                _print_override_koji_hint(resp.overrides[0], client)
        else:
            for override in resp.overrides:
                click.echo(client.override_str(override).strip())
        if 'total' in resp:
            click.echo(
                f'{resp.total} overrides found ({len(resp.overrides)} shown)')
    elif 'build' in resp:
        click.echo(client.override_str(resp, minimal=False))
        if override_hint:
            _print_override_koji_hint(resp, client)
    elif 'comment' in resp:
        click.echo(f"The following comment was added to {resp.comment['update'].alias}")
        click.echo(resp.comment.text)
    elif 'compose' in resp:
        click.echo(client.compose_str(resp['compose'], minimal=False))
    elif 'composes' in resp:
        if len(resp['composes']) == 1:
            click.echo(client.compose_str(resp['composes'][0], minimal=(not verbose)))
        else:
            for compose in resp['composes']:
                click.echo(client.compose_str(compose, minimal=(not verbose)))
                if verbose:
                    # Let's add a little more spacing
                    click.echo()
    else:
        click.echo(resp)
    if resp.get('caveats', None):
        click.echo('Caveats:')
        for caveat in resp.caveats:
            click.echo(caveat.description)


@cli.group()
def releases():
    # Docs that show in the --help
    """Interact with releases."""
    # Developer Docs
    """Manage the releases."""
    pass  # pragma: no cover


@releases.command(name='create')
@handle_errors
@add_options(release_options)
def create_release(user, password, url, debug, composed_by_bodhi, openid_api, **kwargs):
    """Create a release."""
    client = bindings.BodhiClient(base_url=url, username=user, password=password,
                                  staging=kwargs['staging'], openid_api=openid_api)
    kwargs['csrf_token'] = client.csrf()
    kwargs['composed_by_bodhi'] = composed_by_bodhi

    save(client, **kwargs)


@releases.command(name='edit')
@handle_errors
@add_options(release_options)
@click.option('--new-name', help='New release name (eg: F20)')
def edit_release(user, password, url, debug, composed_by_bodhi, openid_api, **kwargs):
    """Edit an existing release."""
    client = bindings.BodhiClient(base_url=url, username=user, password=password,
                                  staging=kwargs['staging'], openid_api=openid_api)
    csrf = client.csrf()

    edited = kwargs.pop('name')

    if edited is None:
        click.echo("ERROR: Please specify the name of the release to edit")
        return

    res = client.send_request(f'releases/{edited}', verb='GET', auth=True)

    data = munch.unmunchify(res)

    if 'errors' in data:
        print_errors(data)

    data['edited'] = edited
    data['csrf_token'] = csrf
    data['composed_by_bodhi'] = composed_by_bodhi

    new_name = kwargs.pop('new_name')

    if new_name is not None:
        data['name'] = new_name

    for k, v in kwargs.items():
        if v is not None:
            data[k] = v

    save(client, **data)


@releases.command(name='info')
@handle_errors
@click.argument('name')
@url_option
@debug_option
@staging_option
def info_release(name, url, **kwargs):
    """Retrieve and print info about a named release."""
    client = bindings.BodhiClient(base_url=url, staging=kwargs['staging'])

    res = client.send_request(f'releases/{name}', verb='GET', auth=False)

    if 'errors' in res:
        print_errors(res)

    else:
        click.echo('Release:')
        print_release(res)


@releases.command(name='list')
@handle_errors
@click.option('--display-archived', is_flag=True, default=False,
              help='Display full list, including archived releases.')
@url_option
@debug_option
@add_options(pagination_options)
@staging_option
def list_releases(display_archived, url, rows=None, page=None, **kwargs):
    """Retrieve and print list of releases."""
    exclude_archived = True
    if display_archived:
        exclude_archived = False

    client = bindings.BodhiClient(base_url=url, staging=kwargs['staging'])

    res = client.get_releases(rows_per_page=rows, page=page, exclude_archived=exclude_archived)

    print_releases_list(res['releases'])


def save(client, **kwargs):
    """
    Save a new or edited release.

    Args:
        client (bodhi.client.bindings.BodhiClient): The Bodhi client to use for the request.
        kwargs (dict): The parameters to send with the request.
    """
    res = client.send_request('releases/', verb='POST', auth=True,
                              data=kwargs)

    if 'errors' in res:
        print_errors(res)

    else:
        click.echo("Saved release:")
        print_release(res)


def print_releases_list(releases):
    """
    Print a list of releases to the terminal.

    Args:
        releases (munch.Munch): The releases to be printed.
    """
    pending = [release for release in releases if release['state'] == 'pending']
    archived = [release for release in releases if release['state'] == 'archived']
    current = [release for release in releases if release['state'] == 'current']

    if pending:
        click.echo('pending:')
        for release in pending:
            click.echo(f"  Name:                {release['name']}")

    if archived:
        click.echo('\narchived:')
        for release in archived:
            click.echo(f"  Name:                {release['name']}")

    if current:
        click.echo('\ncurrent:')
        for release in current:
            click.echo(f"  Name:                {release['name']}")


def print_release(release):
    """
    Print a given release to the terminal.

    Args:
        release (munch.Munch): The release to be printed.
    """
    click.echo(f"  Name:                     {release['name']}")
    click.echo(f"  Long Name:                {release['long_name']}")
    click.echo(f"  Version:                  {release['version']}")
    click.echo(f"  Branch:                   {release['branch']}")
    click.echo(f"  ID Prefix:                {release['id_prefix']}")
    click.echo(f"  Dist Tag:                 {release['dist_tag']}")
    click.echo(f"  Stable Tag:               {release['stable_tag']}")
    click.echo(f"  Testing Tag:              {release['testing_tag']}")
    click.echo(f"  Candidate Tag:            {release['candidate_tag']}")
    click.echo(f"  Pending Signing Tag:      {release['pending_signing_tag']}")
    click.echo(f"  Pending Testing Tag:      {release['pending_testing_tag']}")
    click.echo(f"  Pending Stable Tag:       {release['pending_stable_tag']}")
    click.echo(f"  Override Tag:             {release['override_tag']}")
    click.echo(f"  State:                    {release['state']}")
    click.echo(f"  Email Template:           {release['mail_template']}")
    click.echo(f"  Composed by Bodhi:        {release['composed_by_bodhi']}")
    click.echo(f"  Create Automatic Updates: {release['create_automatic_updates']}")
    click.echo(f"  Package Manager:          {release['package_manager']}")
    click.echo(f"  Testing Repository:       {release['testing_repository']}")


def print_errors(data):
    """
    Print errors to the terminal and exit with code 1.

    Args:
        errors (munch.Munch): The errors to be formatted and printed.
    """
    for error in data['errors']:
        click.echo(f"ERROR: {error['description']}")

    sys.exit(1)


if __name__ == '__main__':
    cli()
