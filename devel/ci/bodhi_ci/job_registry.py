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

"""Bodhi's CI command tool."""

import typing

from .docs import DocsJob
from .integration import (IntegrationBuildJob, IntegrationCleanJob,
                          IntegrationJob)
from .job import BuildJob, CleanJob, Job
from .linting import PreCommitJob
from .rpm import RPMJob
from .unit import DiffCoverJob, UnitJob

AVAILABLE_JOBS: typing.Dict[str, typing.Type['Job']] = {
    "build": BuildJob,
    "pre-commit": PreCommitJob,
    "docs": DocsJob,
    "unit": UnitJob,
    "diff-cover": DiffCoverJob,
    "integration": IntegrationJob,
    "integration-build": IntegrationBuildJob,
    "clean": CleanJob,
    "integration-clean": IntegrationCleanJob,
    "rpm": RPMJob,
}


def build_jobs_list(
    main_job_names: typing.Sequence[str],
    releases: typing.Sequence[str],
    options: dict
) -> typing.List[Job]:
    """
    Build and return a list of jobs to be run for the given command.

    Args:
        main_job_names: The name of the jobs to run.
        releases: The releases we are building Jobs for.
        options: The options provided on the command line.
    Returns:
        A list of Jobs to be run.
    """

    main_jobs = []
    for job_name in main_job_names:
        for release in releases:
            job_class = AVAILABLE_JOBS[job_name]
            if release in job_class.skip_releases:
                continue
            if job_class.only_releases is not None and release not in job_class.only_releases:
                continue
            main_jobs.append(
                (AVAILABLE_JOBS[job_name], dict(release=release))
            )

    # Don't buffer output if there's only one main job
    options["buffer_output"] = options["concurrency"] != 1 and len(main_jobs) > 1

    jobs = []  # type: typing.List[Job]
    # Don't duplicate when two jobs depend on the same job
    job_index = {}  # type: typing.Dict[str, Job]

    def populate_jobs_list(job_class, job_args, parent=None):
        """Populate the full job list by going through the dependencies recursively.

        Args:
            job_class (class): A Job subclass to add
            job_args (dict): The keyword arguments to instanciate the job class
            parent (Job, optional): The parent of the job subclass (the parent depends
                on the subclass). ``None`` for main jobs.
        """
        job_key = (job_class, ",".join(f"{k}={job_args[k]}" for k in sorted(job_args)))
        if job_key in job_index:
            job = job_index[job_key]
            created = False
        else:
            job = job_class(**job_args, options=options)
            job_index[job_key] = job
            created = True
        if parent is not None:
            parent.depends_on.append(job)
        for dep_class, dep_args in job.get_dependencies():
            populate_jobs_list(dep_class, dep_args, parent=job)
        if created:
            jobs.append(job)

    for job in main_jobs:
        populate_jobs_list(job[0], job[1])

    return jobs
