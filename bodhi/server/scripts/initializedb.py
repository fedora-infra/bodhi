# Copyright © 2013-2019 Red Hat, Inc. and others.
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
"""Initialize the database on a new Bodhi installation."""

import os
import sys

from pyramid.paster import get_appsettings

from bodhi.server import initialize_db
from bodhi.server.logging import setup as setup_logging
from ..models import Base


def usage(argv):
    """
    Print usage information and exit with code 1.

    Args:
        argv (list): A list of command line arguments.
    """
    cmd = os.path.basename(argv[0])
    print('usage: %s <config_uri>\n'
          '(example: "%s development.ini")' % (cmd, cmd))
    sys.exit(1)


def main(argv=sys.argv):
    """
    Initialize the Bodhi database on a new installation.

    This function is the entry point used by the initialize_bodhi_db console script.

    Args:
        argv (list): A list of command line arguments. Defaults to sys.argv.
    """
    if len(argv) != 2:
        usage(argv)
    config_uri = argv[1]
    setup_logging()
    settings = get_appsettings(config_uri)
    engine = initialize_db(settings)
    Base.metadata.bind = engine
    Base.metadata.create_all(engine)
