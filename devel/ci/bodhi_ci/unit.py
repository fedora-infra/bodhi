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
"""Unit test jobs."""
import os
import shutil

from .constants import SUBMODULES
from .job import BuildJob, Job


class UnitJob(Job):
    """
    Define a Job for running the unit tests.

    See the Job superclass's docblock for details about its attributes.
    """

    _label = 'unit'
    _dependencies = [BuildJob]

    def __init__(self, *args, **kwargs):
        """
        Initialize the UnitJob.

        See the superclass's docblock for details about additional accepted parameters.
        """
        super().__init__(*args, **kwargs)

        pytest_flags = '--junit-xml=nosetests.xml -v tests'
        if self.options["failfast"]:
            pytest_flags += ' -x'

        submodules = " ".join(SUBMODULES)

        test_command = (
            # Run setup.py develop in each submodule
            f'for submodule in {submodules}; do '
            'cd $submodule; /usr/bin/python3 setup.py develop; cd ..; done; '
            # Run the tests in each submodule
            f'for submodule in {submodules}; do '
            'mkdir -p /results/$submodule; '
            f'cd $submodule; /usr/bin/python3 -m pytest {pytest_flags} || '
            '   (cp *.xml /results/$submodule/ && exit 1) && '
            '   cp *.xml /results/$submodule/; '
            'cd ..; done'
        )
        self._command = ['/usr/bin/bash', '-c', test_command]

        self._convert_command_for_container()

    async def run(self):
        """
        Run the UnitJob, unless --no-build has been requested and the needed coverage data exists.

        Returns:
            UnitJob: Returns self.
        """
        if (
            self.options["no_build"]
            and os.path.exists(os.path.join(self.archive_dir, 'coverage.xml'))
        ):
            self.complete.set()
            self.skipped = True
        else:
            await super().run()
        return self


class DiffCoverJob(Job):
    """
    Define a Job for running diff-cover on the test results.

    See the Job superclass's docblock for details about its attributes.
    """

    _label = 'diff-cover'
    _dependencies = [UnitJob]

    def __init__(self, *args, **kwargs):
        """
        Initialize the DiffCoverJob.

        See the superclass's docblock for details about additional accepted parameters.
        """
        super().__init__(*args, **kwargs)

        if self.release == 'pip':
            executable = '/usr/local/bin/diff-cover'
        else:
            executable = '/usr/bin/diff-cover'
        self._command = [executable] + [
            f'/results/coverage-{s}.xml' for s in SUBMODULES
        ] + [
            '--compare-branch=origin/develop', '--fail-under=100'
        ]
        self._convert_command_for_container(include_git=True)

    def _pre_start_hook(self):
        """
        Copy the coverage.xml from the unit test job to the diff_cover container.
        """
        super()._pre_start_hook()
        for submodule in SUBMODULES:
            shutil.copy(os.path.join(self.depends_on[0].archive_dir, submodule, 'coverage.xml'),
                        os.path.join(self.archive_dir, f'coverage-{submodule}.xml'))
