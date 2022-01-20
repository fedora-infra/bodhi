# Copyright © 2017, 2018 Red Hat, Inc.
#
# This file is part of Bodhi.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# version 2 as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
# Authors:
#   Pierre-Yves Chibon <pingou@pingoured.fr>
#   Randy Barlow <bowlofeggs@fedoraproject.org>
"""This test module contains tests for the migration system."""

import os
import subprocess
import sys


REPO_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))


class TestAlembic:
    """This test class contains tests pertaining to alembic."""

    def test_alembic_history(self):
        """Enforce a linear alembic history.

        This test runs the `alembic history | grep ' (head), '` command,
        and ensure it returns only one line.
        """
        alembic = None
        # Fedora calls the executable alembic-3, but the pip installed alembic will be alembic.
        for executable in (
            '/usr/local/bin/alembic',
            '/usr/bin/alembic-3',
            os.path.join(os.path.dirname(sys.executable), 'alembic')
        ):
            if os.path.exists(executable):
                alembic = executable
                break
        assert alembic is not None, "Couldn't find the alembic executable"

        proc1 = subprocess.Popen(
            [alembic, 'history'],
            cwd=REPO_PATH, stdout=subprocess.PIPE)
        proc2 = subprocess.Popen(
            ['grep', ' (head), '],
            stdin=proc1.stdout, stdout=subprocess.PIPE)

        stdout = proc2.communicate()[0]
        stdout = stdout.strip().split(b'\n')
        assert len(stdout) == 1
        proc1.communicate()
