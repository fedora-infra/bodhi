# Copyright © 2007-2019 Red Hat, Inc.
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
"""The CLI tool for triggering update pushes."""
import sys

from sqlalchemy.sql import or_
import click

from bodhi.server import (buildsys, initialize_db, get_koji)
from bodhi.server.config import config
from bodhi.server.models import (Compose, ComposeState, Release, ReleaseState, Build, Update,
                                 UpdateRequest)
from bodhi.server.util import transactional_session_maker
from bodhi.server.tasks import compose as compose_task


_koji = None


def update_sig_status(update):
    """Update build signature status for builds in update."""
    global _koji
    if _koji is None:
        # We don't want to authenticate to the buildsystem, because this script is often mistakenly
        # run as root and this can cause the ticket cache to become root owned with 0600 perms,
        # which will cause the compose to fail when it tries to use it to authenticate to Koji.
        buildsys.setup_buildsystem(config, authenticate=False)
        _koji = get_koji(None)
    for build in update.builds:
        if not build.signed:
            build_tags = build.get_tags(_koji)
            if update.release.pending_signing_tag not in build_tags:
                click.echo('Build %s was refreshed as signed' % build.nvr)
                build.signed = True
            else:
                click.echo('Build %s still unsigned' % build.nvr)


def check_if_updates_and_builds_set(
        ctx: click.core.Context, param: click.core.Option, value: str) -> str:
    """
    Print an error to stderr if the user has set both the --updates and --builds flags.

    Args:
        ctx: The Click context, used to find out if the other flags are set.
        param: The option being handled.
        value: The value of the param flag.
    Returns:
        The value of the param flag.
    """
    if value is not None and ((param.name == 'builds' and ctx.params.get('updates', False))
                              or (param.name == 'updates' and ctx.params.get('builds', False))):
        click.echo('ERROR: Must specify only one of --updates or --builds', err=True)
        sys.exit(1)
    return value


@click.command()
@click.option('--builds', help='Push updates for a comma-separated list of builds',
              callback=check_if_updates_and_builds_set)
@click.option('--updates', help='Push updates for a comma-separated list of update aliases',
              callback=check_if_updates_and_builds_set)
@click.option('--releases', help=('Push updates for a comma-separated list of releases (default: '
                                  'current and pending releases)'))
@click.option('--request', default='testing,stable',
              help='Push updates with a specific request (default: testing,stable)')
@click.option('--resume', help='Resume one or more previously failed pushes',
              is_flag=True, default=False)
@click.option('--username', prompt=True)
@click.option('--yes', '-y', is_flag=True, default=False,
              help='Answers yes to the various questions')
@click.version_option(message='%(version)s')
def push(username, yes, **kwargs):
    """Push builds out to the repositories."""
    resume = kwargs.pop('resume')
    resume_all = False

    initialize_db(config)
    db_factory = transactional_session_maker()

    composes = []
    with db_factory() as session:
        if not resume and session.query(Compose).count():
            if yes:
                click.echo('Existing composes detected: {}. Resuming all.'.format(
                    ', '.join([str(c) for c in session.query(Compose).all()])))
            else:
                click.confirm(
                    'Existing composes detected: {}. Do you wish to resume them all?'.format(
                        ', '.join([str(c) for c in session.query(Compose).all()])),
                    abort=True)
            resume = True
            resume_all = True

        # If we're resuming a push
        if resume:
            for compose in session.query(Compose).all():
                if len(compose.updates) == 0:
                    # Compose objects can end up with 0 updates in them if the composer ejects all
                    # the updates in a compose for some reason. Composes with no updates cannot be
                    # serialized because their content_type property uses the content_type of the
                    # first update in the Compose. Additionally, it doesn't really make sense to go
                    # forward with running an empty Compose. It makes the most sense to delete them.
                    click.echo("{} has no updates. It is being removed.".format(compose))
                    session.delete(compose)
                    continue

                if not resume_all:
                    if yes:
                        click.echo('Resuming {}.'.format(compose))
                    elif not click.confirm('Resume {}?'.format(compose)):
                        continue

                # Reset the Compose's state and error message.
                compose.state = ComposeState.requested
                compose.error_message = ''

                composes.append(compose)
        else:
            updates = []
            # Accept both comma and space separated request list
            requests = kwargs['request'].replace(',', ' ').split(' ')
            requests = [UpdateRequest.from_string(val) for val in requests]

            query = session.query(Update).filter(Update.request.in_(requests))

            if kwargs.get('builds'):
                query = query.join(Update.builds)
                query = query.filter(
                    or_(*[Build.nvr == build for build in kwargs['builds'].split(',')]))

            if kwargs.get('updates'):
                query = query.filter(
                    or_(*[Update.alias == alias for alias in kwargs['updates'].split(',')]))

            query = _filter_releases(session, query, kwargs.get('releases'))

            for update in query.all():
                # Skip unsigned updates (this checks that all builds in the update are signed)
                update_sig_status(update)

                if not update.signed:
                    click.echo(
                        f'Warning: {update.get_title()} has unsigned builds and has been skipped',
                        err=True)
                    continue

                updates.append(update)

            composes = Compose.from_updates(updates)
            for c in composes:
                session.add(c)

            # We need to flush so the database knows about the new Compose objects, so the
            # Compose.updates relationship will work properly. This is due to us overriding the
            # primaryjoin on the relationship between Composes and Updates.
            session.flush()

            # Now we need to refresh the composes so their updates property will not be empty.
            for compose in composes:
                session.refresh(compose)

        # Now we need to sort the composes so their security property can be used to prioritize
        # security updates. The security property relies on the updates property being
        # non-empty, so this must happen after the refresh above.
        composes = sorted(composes)

        for compose in composes:
            click.echo('\n\n===== {} =====\n'.format(compose))
            for update in compose.updates:
                click.echo(update.get_title())

        if composes:
            if yes:
                click.echo('\n\nPushing {:d} updates.'.format(
                    sum([len(c.updates) for c in composes])))
            else:
                click.confirm('\n\nPush these {:d} updates?'.format(
                    sum([len(c.updates) for c in composes])), abort=True)
            click.echo('\nLocking updates...')
        else:
            click.echo('\nThere are no updates to push.')

        composes = [c.__json__(composer=True) for c in composes]

    if composes:
        click.echo('\nRequesting a compose')
        compose_task.delay(api_version=2, composes=composes, resume=resume, agent=username)


def _filter_releases(session, query, releases=None):
    """
    Filter the given query by releases.

    Apply a filter() transformation to the given query on Updates to filter updates that match the
    given releases argument. If releases evaluates "Falsey", this function will filter for Updates
    that are part of a current Release.

    :param session:  The database session
    :param query:    An Update query that we want to modify by filtering based on Releases
    :param releases: A comma-separated string of release names

    :returns:        A filtered version of query with an additional filter based on releases.
    """
    # We will store models.Release object here that we want to filter by
    _releases = []

    # Filter only releases composed by Bodhi.
    releases_query = session.query(Release).filter(Release.composed_by_bodhi == True)

    # Filter only releases that are current or pending.
    releases_query = releases_query.filter(or_(Release.state == ReleaseState.current,
                                               Release.state == ReleaseState.pending))

    if releases:
        for r in releases.split(','):
            release = releases_query.filter(
                or_(Release.name == r,
                    Release.name == r.upper(),
                    Release.version == r)).first()
            if not release:
                raise click.BadParameter(
                    'Unknown release, or release not allowed to be composed: %s' % r
                )
            else:
                _releases.append(release)
    else:
        # Since the user didn't ask for specific Releases, let's just filter for releases that are
        # current or pending.
        _releases = releases_query

    return query.filter(or_(*[Update.release == r for r in _releases]))


if __name__ == '__main__':
    push()
