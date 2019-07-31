# Copyright (c) 2018 Sebastian Wojciechowski
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
"""This script will run a handy python shell initialized with Bodhi models."""

import sys
from subprocess import call
import logging

import click

from bodhi.server.config import get_configfile


logger = logging.getLogger('bodhi-shell')
logging.basicConfig(level=logging.INFO)


@click.command()
@click.version_option(message='%(version)s')
def get_bodhi_shell():
    """Run python shell initialized with Bodhi models."""
    configfile = get_configfile()
    if configfile is not None:
        call(['pshell-3', configfile])
    else:
        click.echo("Config file not found!", err=True)
        sys.exit(1)
