# -*- coding: utf-8 -*-
# Copyright © 2014-2017 Red Hat, Inc. and others.
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
"""
Create and manage releases in Bodhi.

Here is an example of creatig a release:

    managereleases.py create --name F23 --long-name "Fedora 23" --id-prefix FEDORA --version 23
    --branch f23 --dist-tag f23 --stable-tag f23-updates --testing-tag f23-updates-testing
    --candidate-tag f23-updates-candidate --pending-stable-tag f23-updates-pending
    --pending-testing-tag f23-updates-testing-pending --override-tag f23-override --state pending
"""

import click

from bodhi.client import cli


def main():
    """
    Create and manage releases in Bodhi.

    (This utility has been deprecated. Please use 'bodhi releases' instead.)
    """
    click.echo("This utility has been deprecated. Please use 'bodhi releases' instead.")
    cli.commands['releases'].commands['create'].params[0].opts = ['--username']
    cli.commands['releases'].commands['edit'].params[0].opts = ['--username']
    cli.commands['releases']()


if __name__ == '__main__':
    main()
