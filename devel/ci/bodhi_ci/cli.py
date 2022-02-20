#!/usr/bin/python3
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

import asyncio

import click

from .constants import DEFAULT_OPTIONS, MODULES, RELEASES
from .integration import IntegrationJob
from .job import Job
from .runner import Runner


def _set_context(ctx, param, value):
    """
    Set up a global variable based on click input.

    Args:
        ctx (click.core.Context): The Click context, unused.
        param (click.core.Option): The option being handled. Used to find the global we are setting.
        value (str): The value of the flag.
    Returns:
        bool: The value of the flag.
    """
    value = value or DEFAULT_OPTIONS[param.name]
    ctx.obj[param.name] = value
    return value


def _set_concurrency(ctx, param, value):
    """
    Set up the concurrency_semaphore.

    Args:
        ctx (click.core.Context): The Click context, unused.
        param (click.core.Option): The option being handled. Unused.
        value (str): The value of the -j flag.
    Returns:
        str: The value of the -j flag.
    """
    value = _set_context(ctx, param, value)
    Job.concurrency_semaphore = asyncio.Semaphore(value=value)
    # We don't want too many integration test jobs to run at once because they consume
    # many system resources and will fail due to timeouts. Therefore, let's set another semaphore
    # to limit how many of these can run at once that cannot be greater than an arbitrary value.
    # The arbitrary value was chosen because it seems to work in a Vagrant guest on a
    # Lenovo T480s.
    IntegrationJob.extra_concurrency_semaphore = asyncio.Semaphore(value=max(1, value / 4))
    return value


archive_option = click.option(
    '--archive/--no-archive', is_flag=True, default=True, callback=_set_context, expose_value=False,
    help=("Collect *.xml from the tests and put them into test_results/."))
archive_path_option = click.option(
    '--archive-path', envvar='BODHI_CI_ARCHIVE_PATH', callback=_set_context, expose_value=False,
    help='Define where test results should be placed if -a is used.')
concurrency_option = click.option(
    '--concurrency', '-j', type=int, callback=_set_concurrency, expose_value=False,
    help=('Number of concurrent processes to run. Integration test runs are separately limited due '
          'to resource contention. Defaults to the number of cores detected'))
container_runtime_option = click.option(
    '--container-runtime', '-c', default='docker', type=click.Choice(['docker', 'podman']),
    callback=_set_context, expose_value=False,
    help='Select the container runtime to use. Defaults to docker.')
failfast_option = click.option(
    '--failfast', '-x', is_flag=True, callback=_set_context, expose_value=False,
    help='Exit immediately upon error.')
onlytests_option = click.option(
    '--only-tests', '-k', metavar="EXPRESSION", callback=_set_context, expose_value=False,
    help='only run tests which match the given substring expression. '
         'See the pytest documentation for the -k option for details.')
no_build_option = click.option(
    '--no-build', is_flag=True, callback=_set_context, expose_value=False,
    help='Do not run docker build if the image already exists.')
releases_option = click.option(
    '--release', '-r', "releases", default=list(RELEASES), multiple=True,
    help=("Limit to a particular release. May be specified multiple times. "
          "Acceptable values: {}".format(', '.join(RELEASES))))
modules_option = click.option(
    '--module', '-m', 'modules', default=list(MODULES), type=click.Choice(MODULES), multiple=True,
    show_default=True, callback=_set_context, expose_value=False,
    help='The Bodhi modules to run CI for (can be specified multiple times).')
tty_option = click.option('--tty/--no-tty', default=True, help='Allocate a pseudo-TTY.',
                          callback=_set_context, expose_value=False)
z_option = click.option(
    '-Z', default=False, callback=_set_context, expose_value=False, is_flag=True,
    help="Use the container runtime's Z flag when bind mounting the .git folder")


@click.group()
@click.pass_context
def cli(ctx):
    """
    Bodhi's Continuous Integration helper script.
    """
    ctx.ensure_object(dict)
    for key, value in DEFAULT_OPTIONS.items():
        ctx.obj.setdefault(key, value)


@cli.command()
@archive_option
@archive_path_option
@concurrency_option
@container_runtime_option
@failfast_option
@no_build_option
@releases_option
@modules_option
@tty_option
@click.pass_context
def all(ctx, releases):
    """Run all the types of tests in parallel."""
    job_names = ["pre-commit", "docs", "unit", "diff-cover", "integration"]
    Runner(options=ctx.obj).run_jobs(job_names, releases=releases)


@cli.command()
@concurrency_option
@container_runtime_option
@failfast_option
@releases_option
@tty_option
@click.pass_context
def build(ctx, releases):
    """Build the containers for testing."""
    Runner(options=ctx.obj).run_jobs(["build"], releases=releases)


@cli.command()
@concurrency_option
@container_runtime_option
@releases_option
@tty_option
@click.pass_context
def clean(ctx, releases):
    """Remove all builds pertaining to Bodhi CI."""
    job_names = ("clean", "integration-clean")
    Runner(options=ctx.obj).run_jobs(job_names, releases=releases)


@cli.command()
@concurrency_option
@container_runtime_option
@failfast_option
@no_build_option
@releases_option
@tty_option
@archive_option
@archive_path_option
@click.pass_context
def docs(ctx, releases):
    """Build the docs."""
    Runner(options=ctx.obj).run_jobs(["docs"], releases=releases)


@cli.command("pre-commit")
@concurrency_option
@container_runtime_option
@failfast_option
@no_build_option
@releases_option
@tty_option
@click.pass_context
def pre_commit(ctx, releases):
    """Run pre-commit checks."""
    Runner(options=ctx.obj).run_jobs(["pre-commit"], releases=releases)


@cli.command()
@archive_option
@concurrency_option
@container_runtime_option
@failfast_option
@onlytests_option
@no_build_option
@releases_option
@modules_option
@archive_path_option
@tty_option
@click.pass_context
def unit(ctx, releases):
    """Run the unit tests."""
    Runner(options=ctx.obj).run_jobs(["unit"], releases=releases)


@cli.command("diff-cover")
@archive_option
@archive_path_option
@concurrency_option
@container_runtime_option
@failfast_option
@no_build_option
@releases_option
@modules_option
@tty_option
@z_option
@click.pass_context
def diff_cover(ctx, releases):
    """Run the diff cover test."""
    Runner(options=ctx.obj).run_jobs(["diff-cover"], releases=releases)


@cli.command("integration-build")
@concurrency_option
@container_runtime_option
@failfast_option
@releases_option
@tty_option
@click.pass_context
def integration_build(ctx, releases):
    """Build the containers for integration testing."""
    Runner(options=ctx.obj).run_jobs(["integration-build"], releases=releases)


@cli.command()
@archive_option
@concurrency_option
@container_runtime_option
@failfast_option
@onlytests_option
@no_build_option
@releases_option
@archive_path_option
@tty_option
@click.pass_context
def integration(ctx, releases):
    """Run the integration tests."""
    Runner(options=ctx.obj).run_jobs(["integration"], releases=releases)


@cli.command()
@concurrency_option
@container_runtime_option
@failfast_option
@no_build_option
@releases_option
@tty_option
@archive_option
@archive_path_option
@modules_option
@click.pass_context
def rpm(ctx, releases):
    """Build the rpms."""
    Runner(options=ctx.obj).run_jobs(["rpm"], releases=releases)


if __name__ == "__main__":
    cli()
