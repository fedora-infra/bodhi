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

"""Linting jobs."""

from .job import BuildJob, Job


class PreCommitJob(Job):
    """
    Define a Job for running the pre-commit linters.

    See the Job superclass's docblock for details about its attributes.
    """

    _label = 'pre-commit'
    _command = ["/usr/bin/pre-commit", "run", "-a"]
    _dependencies = [BuildJob]
    only_releases = ["pip"]

    def __init__(self, *args, **kwargs):
        """
        Initialize the job.

        See the superclass's docblock for details about accepted parameters.
        """
        super().__init__(*args, **kwargs)
        # Pre-commit requires a git repo and network access
        self._convert_command_for_container(include_git=True, network="bridge")
