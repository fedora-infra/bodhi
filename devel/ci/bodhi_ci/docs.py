# Copyright © 2018-2019 Red Hat, Inc.
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

"""Documentation build job."""

from .constants import MODULES
from .job import BuildJob, Job


class DocsJob(Job):
    """
    Define a Job for building docs.

    See the Job superclass's docblock for details about its attributes.
    """

    _command = [
        '/usr/bin/bash', '-c',
        (
            'for submodule in ' + ' '.join(MODULES) + '; do '
            'cd $submodule && /usr/bin/python3 setup.py develop && cd ..; done && '
            'make -C docs clean && '
            'make -C docs html PYTHON=/usr/bin/python3 && '
            'make -C docs man PYTHON=/usr/bin/python3 && '
            'cp -rv docs/_build/* /results/'
        )]
    _label = 'docs'
    _dependencies = [BuildJob]

    def __init__(self, *args, **kwargs):
        """
        Initialize the DocsJob.

        See the superclass's docblock for details about accepted parameters.

        Args:
            archive (bool): If True, set up the volume mount so we can retrieve the test results
                from the container.
            archive_path (str): A path on the host to share as a volume into the container for
                its /results path.
        """
        super().__init__(*args, **kwargs)

        self._convert_command_for_container()
