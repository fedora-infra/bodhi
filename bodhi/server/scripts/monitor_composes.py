# -*- coding: utf-8 -*-
# Copyright © 2017-2018 Red Hat, Inc.
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
"""Print a simple human-readable report about existing Compose objects."""
import json

import click

from bodhi.server import buildsys, config, initialize_db, models


@click.command()
@click.version_option(message='%(version)s')
def monitor():
    """Print a simple human-readable report about existing Compose objects."""
    initialize_db(config.config)
    buildsys.setup_buildsystem(config.config)

    click.echo("This utility has been deprecated. Please use 'bodhi composes list' instead.")

    click.echo('Locked updates: %s\n' % models.Update.query.filter_by(locked=True).count())

    for c in sorted([c for c in models.Compose.query.all()]):
        click.echo(c)
        for attr in ('state', 'state_date', 'security', 'error_message'):
            if getattr(c, attr) is not None:
                click.echo('\t%s: %s' % (attr, getattr(c, attr)))
        click.echo('\tcheckpoints: %s' % ', '.join(sorted(json.loads(c.checkpoints).keys())))
        click.echo('\tlen(updates): %s\n' % len(c.updates))
