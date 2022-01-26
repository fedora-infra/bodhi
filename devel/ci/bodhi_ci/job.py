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

"""Basic jobs."""

import asyncio
import datetime
import os
import subprocess
import typing

import click

from .constants import (CONTAINER_LABEL, CONTAINER_NAME, LABEL_TEMPLATE,
                        PROJECT_PATH)


class EmptySemaphore:
    """
    Implements a no-op context manager.

    This is used as the initial value on Job for the concurrency_semaphore and
    extra_concurrency_semaphore attributes so that they can be assumed to work with the async with
    statement if they are used without being turned into Semaphores.
    """

    async def __aenter__(self, *args, **kwargs):
        """Calls pass."""
        pass

    async def __aexit__(self, *args, **kwargs):
        """Calls pass."""
        pass


class Job:
    """
    Represent a CI job.

    This is intended to be a superclass for specific CI jobs, such as building container images, or
    running tests.

    Attributes:
        archive_dir (str): A path where this job's test results is on the host. Only set if an
            archive is used (not used on all jobs).
        release (str): The release this job is testing.
        depends_on (list of Job): This Job will wait for all the jobs' complete Event in the list
            to start.
        cancelled (bool): True if this Job has been cancelled, False otherwise.
        complete (asyncio.Event): An Event that allows other Jobs to wait for this Job to complete.
            complete.set() is called at the end of run().
        returncode (int or None): If the Job's process has finished, this will be set to its
            returncode. Otherwise it will be None.
        skipped (bool): If True, this Job was skipped.
    """

    # Subclasses should override this to set the command to run.
    _command = []  # type: typing.MutableSequence[str]
    # A template to name the image that is built. CONTAINER_NAME and the release gets substituted
    # into the {}'s.
    _container_image_template = '{}/{}'
    # Subclasses should define this to set the label that the job gets reported under.
    _label = ''
    # Dependent job classes
    _dependencies = []  # type: typing.List[typing.Type['Job']]
    # Only run on these releases (None means all releases):
    only_releases = None  # type: typing.Union[typing.List[str], None]
    # Do not run on these releases:
    skip_releases = []  # type: typing.List[str]
    # Limit how many Jobs can run at once. This is set by _set_concurrency().
    concurrency_semaphore = EmptySemaphore()
    # Jobs can set this if they want to have some additional limitations on how many of them can
    # run at once. The IntegrationJob uses this, for example, so that we don't run too many of
    # them no matter what the -j flag is set to. This is set by _set_concurrency().
    extra_concurrency_semaphore = EmptySemaphore()

    def __init__(self, release: str, options: dict = {}):
        """
        Initialize the new Job.

        Args:
            release: The release this Job pertains to.
            options: The command-line options.
        """
        self.release = release
        self.options = options

        self.depends_on: typing.List['Job'] = []
        self.cancelled = False
        # Used to block dependent processes until this Job is done.
        self.complete = asyncio.Event()
        self.started = False
        self.returncode = None
        self.skipped = False
        self._popen_kwargs = {'shell': False}  # type: typing.Mapping[str, typing.Union[bool, int]]
        if options["buffer_output"]:
            # Let's buffer the output so the user doesn't see a jumbled mess.
            self._popen_kwargs['stdout'] = subprocess.PIPE
            self._popen_kwargs['stderr'] = subprocess.STDOUT
        self._stdout = b''
        self._start_time = self._finish_time = None
        self.archive_dir: typing.Union[str, None] = None

    def __repr__(self):
        return f"<{self.__class__.__name__} release={self.release!r}>"

    def _get_container_name(self):
        if self.options["container_runtime"] == 'podman':
            # Workaround for https://github.com/containers/buildah/issues/1034
            return f'localhost/{CONTAINER_NAME}'
        return CONTAINER_NAME

    def _get_container_image(self):
        return self._container_image_template.format(self._get_container_name(), self.release)

    @property
    def _container_image(self):
        """Return the container image name."""
        return self._get_container_image()

    @property
    def label(self):
        """
        Return a label that represents this job.

        This label is used for the status line at the end of the bodhi-ci script, and is also
        prepended to each line of output.

        Returns:
            str: A label to represent this Job.
        """
        return LABEL_TEMPLATE.format(self.release, self._label)

    @property
    def output(self):
        """
        Run decode on the output, and then prepend label in front of each line.

        Returns:
            str: The output from the process.
        """
        if not self._stdout:
            return ''
        output = self._stdout.decode()
        return '\n'.join([f'{self.label}\t{line}' for line in output.split('\n')])

    @property
    def duration(self):
        """Return the duration of the job if it is finished, None otherwise."""
        if self._start_time is None or self._finish_time is None:
            return None
        return self._finish_time - self._start_time

    def skip(self):
        """Mark this job as skipped."""
        self.skipped = True
        self.complete.set()

    async def run(self):
        """
        Run the job, returning itself.

        Returns:
            Job: Returns self.
        """
        try:
            for job in self.depends_on:
                await job.complete.wait()
                if job.returncode != 0 and not job.skipped:
                    # If the Job we depend on failed, we should cancel.
                    raise asyncio.CancelledError()

            async with self.extra_concurrency_semaphore, self.concurrency_semaphore:
                await self._run()

            if self.returncode:
                # If there was a failure, we need to raise an Exception in case the failfast flag
                # was set, so that the runner can cancel the remaining tasks.
                error = RuntimeError()
                error.result = self
                raise error

        except asyncio.CancelledError:
            self.cancelled = True
        finally:
            # If the job's been cancelled or successful, let's go ahead and print its output now.
            # Failed jobs will have their output printed at the end.
            if self.output and (self.returncode == 0 or self.cancelled):
                click.echo(self.output)

            self._finish_time = datetime.datetime.utcnow()
            # Kick off any tasks that were waiting for us to finish.
            self.complete.set()

        return self

    async def _run(self):
        """Actually run the command."""
        # No command: it's just a job that triggers dependencies
        if not self._command:
            self.returncode = 0
            return
        # It's possible that we got cancelled while we were waiting on the Semaphore.
        if self.cancelled:
            return
        self._start_time = datetime.datetime.utcnow()
        self.started = True
        self._pre_start_hook()
        if not self._popen_kwargs["shell"]:
            process = await asyncio.create_subprocess_exec(
                *self._command, **self._popen_kwargs)
        else:
            process = await asyncio.create_subprocess_shell(
                *self._command, **self._popen_kwargs)

        try:
            self._stdout, stderr = await process.communicate()
            if process.returncode < 0:
                # A negative exit code means that our child process was sent a signal,
                # so let's mark this task as cancelled.
                raise asyncio.CancelledError()
        except asyncio.CancelledError:
            try:
                process.terminate()
            except ProcessLookupError:
                # The process is already stopped, nothing to see here.
                pass
            cancelled_stdout, stderr = await process.communicate()
            if self._stdout:
                self._stdout = self._stdout + cancelled_stdout
            else:
                self._stdout = cancelled_stdout
            raise
        finally:
            self.returncode = process.returncode

    def get_dependencies(self):
        return [
            (dep_class, dict(release=self.release))
            for dep_class in self._dependencies
        ]

    def _convert_command_for_container(self, include_git: bool = False, network: str = "none"):
        """
        Use this to convert self._command to run in a container.

        This method is a convenience method that allows Jobs to define their self._command
        attribute in a simple fashion, without having to redefine all the machinery to run the
        command in a container. This method replaces self._command with a command that will run it
        in a container.

        Args:
            include_git: If True, also bind mount the .git folder into the /bodhi folder inside
                the container. This is needed for the diff-cover test. Default: False.
        """
        args = [self.options["container_runtime"], 'run', '--network', network, '--rm',
                '--label', CONTAINER_LABEL, '--init']

        if self.options["tty"] and not self.options["buffer_output"]:
            # Don't request a TTY when outputing to pipes.
            # https://github.com/containers/podman/issues/9718
            args.append('-t')

        if self.options["archive"]:
            self.archive_dir = f'{self.options["archive_path"]}/{self.release}-{self._label}'
            args.extend(['-v', f'{self.archive_dir}:/results:z'])

        if include_git:
            mount_flags = ['ro']
            if self.options["z"]:
                mount_flags.append('Z')
            else:
                mount_flags.append('z')
            args.extend([
                '-v', f"{os.path.join(PROJECT_PATH, '.git')}:/bodhi/.git:{','.join(mount_flags)}"])

        args.append(self._container_image)
        args.extend(self._command)
        self._command = args

    def _pre_start_hook(self):
        """Announce that we are running now and create the archive dir if needed."""
        click.echo(f"Running {' '.join(self._command)}")
        if (
            self.options["archive"]
            and self.archive_dir is not None
            and not os.path.exists(self.archive_dir)
        ):
            os.makedirs(self.archive_dir)


class BuildJob(Job):
    """
    Define a Job for building container images.

    See the Job superclass's docblock for details about its attributes.
    """

    _label = 'build'
    # A template for finding the name of the Dockerfile to be used for this BuildJob. The release
    # gets substituted into the {}'s.
    _dockerfile_template = 'Dockerfile-{}'
    # Extra arguments to be passed to the container build command.
    _build_args = ['--force-rm', '--pull']

    def __init__(self, *args, **kwargs):
        """
        Initialize the BuildJob.

        See the superclass's docblock for details about accepted parameters.
        """
        super().__init__(*args, **kwargs)

        dockerfile = os.path.join(PROJECT_PATH, 'devel', 'ci',
                                  self._dockerfile_template.format(self.release))
        self._command = [self.options["container_runtime"], 'build', '-t', self._container_image,
                         '-f', dockerfile, '.']
        if self._build_args:
            for arg in reversed(self._build_args):
                self._command.insert(2, arg)

    async def run(self):
        """
        Run the BuildJob, unless --no-build has been requested and the needed build already exists.

        Returns:
            BuildJob: Returns self.
        """
        if self.options["no_build"] and self._build_exists:
            self.skip()
        else:
            await super().run()
        return self

    @property
    def _build_exists(self):
        """
        Determine whether a container image exists for this build job.

        Returns:
            bool: True if a build exists, False otherwise.
        """
        args = [self.options["container_runtime"], 'images', self._container_image]
        images = subprocess.check_output(args).decode()
        if self._container_image in images:
            return True
        return False


class CleanJob(Job):
    """
    Define a Job for removing all container images built by bodhi-ci.

    See the Job superclass's docblock for details about its attributes.
    """

    _label = 'clean'

    def __init__(self, *args, **kwargs):
        """
        Initialize the CleanJob.

        See the superclass's docblock for details about accepted parameters.
        """
        super().__init__(*args, **kwargs)

        self._command = [self.options["container_runtime"], 'rmi', self._container_image]


class StopJob(Job):
    """
    Define a Job for stopping all containers started by this process.

    See the Job superclass's docblock for details about its attributes.
    """

    _label = 'stop'

    def __init__(self, *args, **kwargs):
        """
        Initialize the StopJob.

        See the superclass's docblock for details about accepted parameters.
        """
        super().__init__(*args, **kwargs)

        self._command = [self.options["container_runtime"], 'stop', self.release]
        self._popen_kwargs['stdout'] = subprocess.DEVNULL

    def _pre_start_hook(self):
        """Do not announce this Job; it is noisy."""
        pass
