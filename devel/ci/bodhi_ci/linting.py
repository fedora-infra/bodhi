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

import typing

from .job import BuildJob, Job


class Flake8Job(Job):
    """
    Define a Job for running flake8.

    See the Job superclass's docblock for details about its attributes.
    """

    _label = 'flake8'
    _dependencies = [BuildJob]
    only_releases = ["pip"]

    def __init__(self, *args, **kwargs):
        """
        Initialize the Flake8Job.

        See the superclass's docblock for details about accepted parameters.
        """
        super().__init__(*args, **kwargs)

        if self.release == 'pip':
            self._command = ['/usr/local/bin/flake8']
        else:
            self._command = ['/usr/bin/flake8']
        self._convert_command_for_container()


class MyPyBuildJob(BuildJob):
    """
    Define a Job for building mypy container images.

    See the Job superclass's docblock for details about its attributes.
    """

    # We don't want the --pull build arg because we are based on a container built by bodhi-ci.
    _build_args = []  # type: typing.List[str]
    _container_image_template = '{}/{}/mypy'
    _dockerfile_template = 'Dockerfile-mypy-{}'
    _label = 'mypy-build'
    _dependencies = [BuildJob]


class MyPyJob(Job):
    """
    Define a Job for running mypy.

    See the Job superclass's docblock for details about its attributes.
    """

    _container_image_template = '{}/{}/mypy'
    _label = 'mypy'
    _dependencies = [MyPyBuildJob]
    only_releases = ["pip"]

    def __init__(self, *args, **kwargs):
        """
        Initialize the MyPyJob.

        See the superclass's docblock for details about accepted parameters.
        """
        super().__init__(*args, **kwargs)

        self._command = ['/usr/local/bin/mypy']
        self._convert_command_for_container()


class PydocstyleJob(Job):
    """
    Define a Job for running pydocstyle.

    See the Job superclass's docblock for details about its attributes.
    """

    _label = 'pydocstyle'
    _dependencies = [BuildJob]
    only_releases = ["pip"]

    def __init__(self, *args, **kwargs):
        """
        Initialize the PydocstyleJob.

        See the superclass's docblock for details about accepted parameters.
        """
        super().__init__(*args, **kwargs)

        if self.release == 'pip':
            self._command = ['/usr/local/bin/pydocstyle', 'bodhi']
        else:
            self._command = ['/usr/bin/pydocstyle', 'bodhi']
        self._convert_command_for_container()
