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

import os
import platform
import subprocess
import sys
import traceback

import click

from bodhi.client import bindings


def _warn_if_url_and_staging_set(ctx, param, value):
    """
    This function will print a warning to stderr if the user has set both the --url and --staging
    flags, so that the user is aware that --staging supercedes --url.

    Args:
        ctx (click.core.Context): The Click context, used to find out if the --staging flag is set.
        param (click.core.Option): The option being handled. Unused.
        value (unicode): The value of the --url flag.

    Returns:
        unicode: The value of the --url flag.
    """
    if ctx.params.get('staging', False):
        click.echo('\nWarning: url and staging flags are both set. url will be ignored.\n',
                   err=True)
    return value


url_option = click.option('--url', envvar='BODHI_URL', default=bindings.BASE_URL,
                          help=('URL of a Bodhi server. Ignored if --staging is set. Can be set '
                                'with BODHI_URL environment variable'),
                          callback=_warn_if_url_and_staging_set)


@click.group()
@click.version_option(message='%(version)s')
def cli():
    """
    Create the main CLI group.
    """
    pass


@cli.group()
def updates():
    """
    Create the updates group.
    """
    pass


@updates.command()
@click.argument('builds')
@click.option('--user', envvar='USERNAME')
@click.option('--password', prompt=True, hide_input=True)
@click.option('--type', default='bugfix', help='Update type', required=True,
              type=click.Choice(['security', 'bugfix',
                                 'enhancement', 'newpackage']))
@click.option('--notes', help='Update description')
@click.option('--notes-file', help='Update description from a file')
@click.option('--bugs', help='Comma-seperated list of bug numbers', default='')
@click.option('--close-bugs', default=True, is_flag=True, help='Automatically close bugs')
@click.option('--request', help='Requested repository',
              type=click.Choice(['testing', 'stable', 'unpush']))
@click.option('--autokarma', default=True, is_flag=True, help='Enable karma automatism')
@click.option('--stable-karma', type=click.INT, help='Stable karma threshold')
@click.option('--unstable-karma', type=click.INT, help='Unstable karma threshold')
@click.option('--suggest', help='Post-update user suggestion',
              type=click.Choice(['logout', 'reboot']))
@click.option('--file', help='A text file containing all the update details')
@click.option('--staging', help='Use the staging bodhi instance',
              is_flag=True, default=False)
@url_option
def new(user, password, url, **kwargs):
    """
    Create a new update.

    Args:
        user (unicode): The username to authenticate as.
        password (unicode): The user's password.
        url (unicode): The URL of a Bodhi server to create the update on. Ignored if staging is
                       True.
        kwargs (dict): Other keyword arguments passed to us by click.
    """
    client = bindings.BodhiClient(base_url=url, username=user, password=password,
                                  staging=kwargs['staging'])

    if kwargs['file'] is None:
        updates = [kwargs]

    else:
        updates = client.parse_file(os.path.abspath(kwargs['file']))

    if kwargs['notes_file'] is not None:
        if kwargs['notes'] is None:
            with open(kwargs['notes_file'], 'r') as fin:
                kwargs['notes'] = fin.read()

        else:
            click.echo("ERROR: Cannot specify --notes and --notes-file")
            sys.exit(1)

    for update in updates:
        try:
            resp = client.save(**update)
            print_resp(resp, client)
        except bindings.BodhiClientException as e:
            click.echo(str(e))
        except Exception as e:
            traceback.print_exc()


@updates.command()
@click.option('--updateid', help='Query by update ID (eg: FEDORA-2015-0001)')
@click.option('--approved-since', help='Approved after a specific timestamp')
@click.option('--modified-since', help='Modified after a specific timestamp')
@click.option('--builds', help='Query updates based on builds')
@click.option('--bugs', help='A list of bug numbers')
@click.option('--critpath', is_flag=True, default=None,
              help='Query only critical path packages')
@click.option('--cves', help='Query by CVE id')
@click.option('--packages', help='Query by package name(s)')
@click.option('--pushed', is_flag=True, default=None,
              help='Filter by pushed updates')
@click.option('--pushed-since',
              help='Updates that have been pushed after a certain time')
@click.option('--releases', help='Updates for specific releases')
@click.option('--locked', help='Updates that are in a locked state')
@click.option('--request', help='Updates with a specific request',
              type=click.Choice(['testing', 'stable', 'unpush']))
@click.option('--submitted-since',
              help='Updates that have been submitted since a certain time')
@click.option('--status', help='Filter by update status',
              type=click.Choice(['pending', 'testing', 'stable', 'obsolete',
                                 'unpushed', 'processing']))
@click.option('--suggest', help='Filter by post-update user suggestion',
              type=click.Choice(['logout', 'reboot']))
@click.option('--type', default=None, help='Filter by update type',
              type=click.Choice(['newpackage', 'security', 'bugfix', 'enhancement']))
@click.option('--user', help='Updates submitted by a specific user')
@click.option('--staging', help='Use the staging bodhi instance',
              is_flag=True, default=False)
@url_option
def query(url, **kwargs):
    """
    Query updates based on flags.

    Args:
        url (unicode): The URL of a Bodhi server to create the update on. Ignored if staging is
                       True.
        kwargs (dict): Other keyword arguments passed to us by click.
    """
    client = bindings.BodhiClient(base_url=url, staging=kwargs['staging'])
    resp = client.query(**kwargs)
    print_resp(resp, client)


@updates.command()
@click.argument('update')
@click.argument('state')
@click.option('--user', envvar='USERNAME')
@click.option('--password', prompt=True, hide_input=True)
@click.option('--staging', help='Use the staging bodhi instance',
              is_flag=True, default=False)
@url_option
def request(update, state, user, password, url, **kwargs):
    """
    Change an update's request to the given state.

    Args:
        update (unicode): The update you wish to modify.
        state (unicode): The state you wish to change the update's request to. Valid options are
                         testing, stable, obsolete, unpush, and revoke.
        user (unicode): The username to authenticate as.
        password (unicode): The user's password.
        staging (bool): Whether to use the staging server or not.
        url (unicode): The URL of a Bodhi server to create the update on. Ignored if staging is
                       True.
        kwargs (dict): Other keyword arguments passed to us by click.
    """
    client = bindings.BodhiClient(base_url=url, username=user, password=password,
                                  staging=kwargs['staging'])

    try:
        resp = client.request(update, state)
    except bindings.UpdateNotFound as exc:
        raise click.BadParameter(unicode(exc), param_hint='UPDATE')

    print_resp(resp, client)


@updates.command()
@click.argument('update')
@click.argument('text')
@click.option('--karma', default=0, type=click.INT, help='The karma for this comment (+1/0/-1)')
@click.option('--user', envvar='USERNAME')
@click.option('--password', prompt=True, hide_input=True)
@click.option('--staging', help='Use the staging bodhi instance',
              is_flag=True, default=False)
@url_option
def comment(update, text, karma, user, password, url, **kwargs):
    """
    Comment on an update.

    Args:
        update (unicode): The update you wish to modify.
        text (unicode): The text of the comment you wish to leave on the update.
        karma (int): The karma you wish to leave on the update. Must be +1, 0, or -1.
        user (unicode): The username to authenticate as.
        password (unicode): The user's password.
        staging (bool): Whether to use the staging server or not.
        url (unicode): The URL of a Bodhi server to create the update on. Ignored if staging is
                       True.
        kwargs (dict): Other keyword arguments passed to us by click.
    """
    client = bindings.BodhiClient(base_url=url, username=user, password=password,
                                  staging=kwargs['staging'])
    resp = client.comment(update, text, karma)
    print_resp(resp, client)


@updates.command()
@click.option('--staging', help='Use the staging bodhi instance',
              is_flag=True, default=False)
@click.option('--cves', help='Download update(s) by CVE(s) (comma-separated list)')
@click.option('--updateid', help='Download update(s) by ID(s) (comma-separated list)')
@click.option('--builds', help='Download update(s) by build NVR(s) (comma-separated list)')
@url_option
def download(url, **kwargs):
    """
    Download the builds for an update.

    Args:
        staging (bool): Whether to use the staging server or not.
        url (unicode): The URL of a Bodhi server to create the update on. Ignored if staging is
                       True.
        kwargs (dict): Other keyword arguments passed to us by click.
    """
    client = bindings.BodhiClient(base_url=url, staging=kwargs['staging'])
    del(kwargs['staging'])
    # At this point we need to have reduced the kwargs dict to only our
    # query options (cves, updateid, builds)
    if not any(kwargs.values()):
        click.echo("ERROR: must specify at least one of --cves, --updateid, --builds")
        sys.exit(1)

    # As the query method doesn't let us construct OR queries, we're
    # gonna run one query for each option that was passed. The syntax
    # for this is a bit ugly, sorry.
    for (attr, value) in kwargs.items():
        if value:
            expecteds = len(value.split(','))
            resp = client.query(**{attr: value})
            if len(resp.updates) == 0:
                click.echo("WARNING: No {0} found!".format(attr))
            elif len(resp.updates) < expecteds:
                click.echo("WARNING: Some {0} not found!".format(attr))
            # Not sure if we need a check for > expecteds, I don't
            # *think* that should ever be possible for these opts.

            for update in resp.updates:
                click.echo("Downloading packages from {0}".format(update['title']))
                for build in update['builds']:
                    # subprocess is icky, but koji module doesn't
                    # expose this in any usable way, and we don't want
                    # to rewrite it here.
                    args = ('koji', 'download-build', '--arch=noarch',
                            '--arch={0}'.format(platform.machine()), build['nvr'])
                    ret = subprocess.call(args)
                    if ret:
                        click.echo("WARNING: download of {0} failed!".format(build['nvr']))


@cli.group()
def overrides():
    """
    Create the overrides CLI group.
    """
    pass


@overrides.command('query')
@click.option('--user', default=None,
              help='Updates submitted by a specific user')
@click.option('--staging', help='Use the staging bodhi instance',
              is_flag=True, default=False)
@url_option
def query_buildroot_overrides(url, user=None, **kwargs):
    """
    Query the buildroot overrides.

    Args:
        user (unicode): If supplied, overrides for this user will be queried.
        staging (bool): Whether to use the staging server or not.
        url (unicode): The URL of a Bodhi server to create the update on. Ignored if staging is
                       True.
        kwargs (dict): Other keyword arguments passed to us by click.
    """
    client = bindings.BodhiClient(base_url=url, staging=kwargs['staging'])
    resp = client.list_overrides(user=user)
    print_resp(resp, client)


@overrides.command('save')
@click.argument('nvr')
@click.option('--duration', default=7, type=click.INT,
              help='Number of days the override should exist.')
@click.option('--notes', default="No explanation given...",
              help='Notes on why this override is in place.')
@click.option('--user', envvar='USERNAME')
@click.option('--password', prompt=True, hide_input=True)
@click.option('--staging', help='Use the staging bodhi instance',
              is_flag=True, default=False)
@url_option
def save_buildroot_overrides(nvr, duration, notes, user, password, staging, url):
    """
    Create or modify a buildroot override.

    Args:
        nvr (unicode): The NVR of the update you wish to submit as a buildroot override.
        duration (int): The number of days you wish the override to be active for.
        notes (unicode): Notes to leave on the override.
        user (unicode): The username to authenticate as.
        password (unicode): The user's password.
        staging (bool): Whether to use the staging server or not.
        url (unicode): The URL of a Bodhi server to create the update on. Ignored if staging is
                       True.
        kwargs (dict): Other keyword arguments passed to us by click.
    """
    client = bindings.BodhiClient(base_url=url, username=user, password=password, staging=staging)
    resp = client.save_override(nvr=nvr, duration=duration, notes=notes)
    print_resp(resp, client)


def print_resp(resp, client):
    if 'updates' in resp:
        if len(resp.updates) == 1:
            click.echo(client.update_str(resp.updates[0]))
        else:
            for update in resp.updates:
                click.echo(client.update_str(update, minimal=True).strip())
        if 'total' in resp:
            click.echo('%s updates found (%d shown)' % (
                resp.total, len(resp.updates)))
    elif resp.get('update'):
        click.echo(client.update_str(resp['update']))
    elif 'title' in resp:
        click.echo(client.update_str(resp))
    elif 'overrides' in resp:
        if len(resp.overrides) == 1:
            click.echo(client.override_str(resp.overrides[0]))
        else:
            for override in resp.overrides:
                click.echo(client.override_str(override).strip())
        click.echo(
            '%s overrides found (%d shown)' % (resp.total, len(resp.overrides)))
    elif 'build' in resp:
        click.echo(client.override_str(resp))
    elif 'comment' in resp:
        click.echo('The following comment was added to %s' % resp.comment['update'].title)
        click.echo(resp.comment.text)
    elif 'errors' in resp:
        for error in resp['errors']:
            click.echo("ERROR: %s" % error['description'])
        sys.exit(1)
    else:
        click.echo(resp)

    if resp.get('caveats', None):
        click.echo('Caveats:')
        for caveat in resp.caveats:
            click.echo(caveat.description)


if __name__ == '__main__':
    cli()
