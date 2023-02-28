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

"""Job runner."""

import asyncio
import functools
import signal
import subprocess
import sys
import typing

import click

from .constants import CONTAINER_LABEL
from .job import Job, StopJob
from .job_registry import build_jobs_list
from .reporter import ProgressReporter


def _cancel_jobs(jobs: typing.List[Job]):
    """
    Mark the given jobs as cancelled.

    This is used as the SIGINT handler.

    Args:
        jobs: A list of Jobs which will have their cancelled attribute set to True.
    """
    for job in jobs:
        if job.returncode is None:
            job.cancelled = True


class Runner:
    """Execute the tests."""

    def __init__(self, options: dict):
        self.options = options
        self.loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

    def run_jobs(self, job_names, releases):
        """Get the jobs list and run them."""
        jobs = build_jobs_list(job_names, releases=releases, options=self.options)
        self._run_jobs(jobs)

    def _run_jobs(self, jobs: typing.List[Job]):
        """
        Run the given jobs in parallel.

        Start a process for each Job. The stdout and stderr for each process is written to the
        terminal. Processes that exited with code 0 or were cancelled are output first,
        followed by any processes that failed. If any jobs failed, one of the failed jobs' exit
        code will be used to exit this process.

        Args:
            jobs: A list of Jobs to run.
        """
        if not jobs:
            click.echo("No jobs!", err=True)
            sys.exit(3)

        progress_reporter = ProgressReporter(jobs)
        progress_reporter.print_status()

        processes = [self.loop.create_task(j.run()) for j in jobs]

        return_when: str = asyncio.ALL_COMPLETED
        if self.options["failfast"]:
            return_when = asyncio.FIRST_EXCEPTION
        future = asyncio.wait(processes, return_when=return_when)
        self.loop.add_signal_handler(signal.SIGINT, functools.partial(_cancel_jobs, jobs))

        try:
            done, pending = self.loop.run_until_complete(future)

            results = self._process_results(done, pending)
        finally:
            self._stop_all_jobs()

        # Now it's time to print any error output we collected, then exit or return.
        if results['returncode']:
            click.echo(results['error_output'], err=True)
            sys.exit(results['returncode'])

    def _process_results(self, done, pending):
        """
        Process the finished and pendings tasks and return error output and an exit code.

        This function is used by _run_processes() to generate the final stdout to be printed
        (which is going to be the output of the failed tasks since the cancelled tasks and
        successful tasks already had their output printed) and an exit code that bodhi-ci
        should use. Any pending tasks will be cancelled.

        Args:
            done (set): A set of asyncio.Tasks that represent finished tasks.
            pending (set): A set of asyncio.Tasks that represent unfinished tasks.
                These will be canceled.
        Returns:
            dict: A dictionary with two keys:
                'error_output': The error output that should be printed.
                'returncode': The exit code that bodhi-ci should exit with.
        """
        returncode = 0
        error_output = ''

        if pending:
            for task in pending:
                task.cancel()
            future = asyncio.wait(pending)
            cancelled, pending = self.loop.run_until_complete(future)
            done = done | cancelled
            returncode = -signal.SIGINT

        for task in done:
            try:
                result = task.result()
            except RuntimeError as e:
                result = e.result
            if not result.cancelled and result.returncode:
                if result.output:
                    error_output = f'{error_output}\n{result.output}'
                if not returncode:
                    returncode = result.returncode

        return {'error_output': error_output, 'returncode': returncode}

    def _stop_all_jobs(self):
        """
        Stop all running docker jobs with the CONTAINER_LABEL.

        Even though we terminate() all of our child processes above, Docker does not always proxy
        signals through to the container, so we will do a final cleanup to make sure all the jobs
        we started in this process have been told to stop.
        """
        args = [self.options["container_runtime"], 'ps', f'--filter=label={CONTAINER_LABEL}', '-q']
        processes = subprocess.check_output(args).decode()
        stop_jobs = [
            self.loop.create_task(StopJob(process).run())
            for process in processes.split('\n')
            if process
        ]

        # If you give run_until_complete a future with no tasks, you will haz a sad (that's the
        # technical wording for a ValueError).
        if stop_jobs:
            stop_future = asyncio.wait(stop_jobs)
            self.loop.run_until_complete(stop_future)
