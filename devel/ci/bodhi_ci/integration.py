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

"""Integration test jobs."""

import datetime
import os
import sys

from .constants import INTEGRATION_APPS, PROJECT_PATH
from .job import BuildJob, Job


class IntegrationAppBuildJob(BuildJob):
    """
    Define a Job for building container images for integration testing.

    See the Job superclass's docblock for details about its attributes.
    """

    def __init__(self, app_name, *args, **kwargs):
        """
        Initialize the IntegrationAppBuildJob.

        See the superclass's docblock for details about accepted parameters.
        """
        self._app_name = app_name
        super().__init__(*args, **kwargs)
        self._label = f'integration-build-{app_name}'
        dockerfile = os.path.join(
            PROJECT_PATH, 'devel', 'ci', 'integration', app_name, 'Dockerfile'
        )
        self._command = [self.options["container_runtime"], 'build', '--force-rm', '--pull',
                         '-t', self._container_image, '-f', dockerfile, '.']

    def __repr__(self):
        return f"<{self.__class__.__name__} app={self._app_name!r}>"

    def _get_container_image(self):
        return f'{self._get_container_name()}-integration-{self._app_name}'

    def get_dependencies(self):
        deps = super().get_dependencies()
        if self._app_name in ["waiverdb", "bodhi"]:
            deps.append(
                (IntegrationDumpDownloadJob, dict(app_name=self._app_name, release="prod"))
            )
        return deps


class IntegrationBodhiBuildJob(IntegrationAppBuildJob):
    """
    Build Bodhi in a container image for integration testing.

    See the Job superclass's docblock for details about its attributes.
    """

    _dependencies = [BuildJob]

    def __init__(self, *args, **kwargs):
        """
        Initialize the IntegrationBodhiBuildJob.

        See the superclass's docblock for details about accepted parameters.
        """
        super().__init__(*args, app_name="bodhi", **kwargs)

        dockerfile = os.path.join(
            PROJECT_PATH, 'devel', 'ci', 'integration', 'bodhi',
            'Dockerfile-{}'.format(self.release),
        )
        self._command = [
            self.options["container_runtime"],
            'build', '--force-rm', '-t', self._container_image,
            '-f', dockerfile, '.'
        ]

    def __repr__(self):
        return Job.__repr__(self)

    def _get_container_image(self):
        return '{}-integration-bodhi/{}'.format(self._get_container_name(), self.release)


class IntegrationDumpDownloadJob(BuildJob):
    """
    Define a Job for downloading database dumps for integration testing.

    See the Job superclass's docblock for details about its attributes.
    """

    def __init__(self, app_name, *args, **kwargs):
        """
        Initialize the IntegrationDumpDownloadJob.

        See the superclass's docblock for details about accepted parameters.
        """
        super().__init__(*args, **kwargs)

        self._app_name = app_name
        self._label = f'integration-dump-download-{self._app_name}'
        if self._app_name == "bodhi":
            db_name = "bodhi2"
        else:
            db_name = self._app_name
        self.filepath = os.path.join(
            "devel", "ci", "integration", "dumps", f"{db_name}.dump")
        url = f"https://infrastructure.fedoraproject.org/infra/db-dumps/{db_name}.dump.xz"
        self._popen_kwargs['shell'] = True
        self._command = [
            (f"curl -f -o {self.filepath}.xz {url} && xz -d --keep --force {self.filepath}.xz")]

    def __repr__(self):
        return f"<{self.__class__.__name__} app={self._app_name!r}>"

    async def run(self) -> 'IntegrationDumpDownloadJob':
        """
        Run the download, unless we already have the file and it's recent enough.

        Returns:
            Returns self.
        """
        if os.path.exists(self.filepath):
            # st_mtime is going to use the filesystem's timestamp, not necessarily UTC. Thus, we
            # will use tz=None on fromttimestamp() so that the time is expressed in the system's
            # local time. Therefore, we also need to collect the current time in the system's local
            # time for comparison.
            modified_time = datetime.datetime.fromtimestamp(os.stat(self.filepath).st_mtime)
            if datetime.datetime.now() - modified_time < datetime.timedelta(days=1):
                # Our download is within a day and infrastructure only produces downloads once a
                # day, so let's skip this task.
                self.skip()
                return self

        return await super().run()


class IntegrationBuildJob(Job):
    """Build the apps required for integration testing."""
    def get_dependencies(self):
        for app_name in INTEGRATION_APPS:
            yield (IntegrationAppBuildJob, dict(app_name=app_name, release="prod"))
        yield (IntegrationBodhiBuildJob, dict(release=self.release))


class IntegrationJob(Job):
    """
    Define a Job for running the integration tests.

    See the Job superclass's docblock for details about its attributes.
    """

    _label = 'integration'
    skip_releases = ['f32', 'pip']
    _dependencies = [IntegrationBuildJob]

    def __init__(self, *args, **kwargs):
        """
        Initialize the IntegrationJob.

        See the superclass's docblock for details about additional accepted parameters.

        Args:
            archive (bool): If True, set up the volume mount so we can retrieve the test results
                from the container.
            archive_path (str): A path on the host to share as a volume into the container for
                its /results path.
        """
        super().__init__(*args, **kwargs)

        self._command = [sys.executable, '-m', 'pytest', '-vv', '--no-cov',
                         'devel/ci/integration/tests/']
        bodhi_container_image = f'{self._get_container_name()}-integration-bodhi/{self.release}'
        self._popen_kwargs["env"] = os.environ.copy()
        self._popen_kwargs["env"]["BODHI_INTEGRATION_IMAGE"] = bodhi_container_image
        self._popen_kwargs["env"]["CONTAINER_RUNTIME"] = self.options["container_runtime"]
        if self.options["failfast"]:
            self._command.append('-x')
        if self.options["only_tests"]:
            self._command.extend(['-k', self.options["only_tests"]])
        if self.options["archive"]:
            self._command.append(
                f'--junit-xml={self.options["archive_path"]}/'
                f'{self.release}-{self._label}/nosetests.xml'
            )


class IntegrationCleanAppJob(Job):
    """
    Define a Job for removing all container images built by bodhi-ci.

    See the Job superclass's docblock for details about its attributes.
    """

    def __init__(self, app_name, *args, **kwargs):
        """
        Initialize the IntegrationCleanJob.

        See the superclass's docblock for details about accepted parameters.
        """
        super().__init__(*args, **kwargs)
        self._app_name = app_name
        self._label = f'integration-clean-{self._app_name}'
        self._command = [self.options["container_runtime"], 'rmi', self._container_image]

    def __repr__(self):
        return f"<{self.__class__.__name__} app={self._app_name!r} release={self.release!r}>"

    def _get_container_image(self):
        name = f'{self._get_container_name()}-integration-{self._app_name}'
        if self._app_name == "bodhi":
            name = f"{name}/{self.release}"
        return name


class IntegrationCleanJob(Job):
    """Clean the app builds required for integration testing."""
    def get_dependencies(self):
        for app_name in INTEGRATION_APPS:
            yield (IntegrationCleanAppJob, dict(app_name=app_name, release="prod"))
        yield (IntegrationCleanAppJob, dict(app_name="bodhi", release=self.release))
