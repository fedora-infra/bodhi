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

"""Report progress."""

import asyncio
import typing

import click

from .job import Job


class ProgressReporter:
    """Report progress on the provided jobs.

    Attributes:
        jobs: A list of the Jobs to report on.
    """

    def __init__(self, jobs: typing.List['Job']):
        """
        Args:
            jobs: A list of the Jobs to report on.
        """
        self._jobs = []  # type: typing.List[Job]
        for job in jobs:
            self.register_job(job)

    def register_job(self, job):
        """Register a job to be reported.

        Args:
            job (Job): A job to report the status of.
        """
        if not job._label:
            # No label, no reporting
            return
        self._jobs.append(job)
        loop = asyncio.get_event_loop()
        loop.create_task(self._print_on_complete(job))

    async def _print_on_complete(self, job):
        """Print the status of a job when it's complete."""
        await job.complete.wait()
        self.print_status()

    def print_status(self):
        """Print a status report on all the jobs."""
        for job in self._jobs:
            click.echo(self.get_job_summary(job))
        click.echo('\n')

    def get_job_summary(self, job):
        """
        Create a summary line for the Job.

        If the exit_code indicates failure, it is printed to the console immediately. Failed jobs'
        stdout is not printed until the end of the job, so this gives the user a way to know that a
        job failed before its output is printed, and they can ctrl-c to see its output.

        Returns:
            str: A summary line suitable to print at the end of the process.
        """
        blue_start = '\033[0;34m' if job.options["tty"] else ''
        yellow_start = '\033[0;33m' if job.options["tty"] else ''
        green_start = '\033[0;32m' if job.options["tty"] else ''
        red_start = '\033[0;31m' if job.options["tty"] else ''
        color_end = '\033[0m' if job.options["tty"] else ''
        if not job.complete.is_set():
            if not job.started:
                return f'{job.label}:  {blue_start}WAITING{color_end}'
            else:
                return f'{job.label}:  {yellow_start}RUNNING{color_end}'
        if job.cancelled:
            if job._start_time is not None:
                return f'{job.label}:  {yellow_start}CANCELED{color_end}  [{job.duration}]'
            return f'{job.label}:  {yellow_start}CANCELED{color_end}'
        if job.skipped:
            return f'{job.label}:  {blue_start}SKIPPED{color_end}'
        if job.returncode == 0:
            return f'{job.label}:  {green_start}SUCCESS!{color_end}  [{job.duration}]'
        else:
            return (
                f'{job.label}:  {red_start}FAILED{color_end}    [{job.duration}] '
                f'(exited with code: {job.returncode})'
            )
