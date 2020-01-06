# Copyright © 2013-2019 Red Hat, Inc. and others.
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
"""Generates console scripts for former cron jobs that have been replaced by celery-beat."""

import sys
import logging

import click
from pyramid.paster import get_appsettings

from bodhi.server.config import config


logger = logging.getLogger(__name__)

config_uri_argument = click.argument(
    'config_uri', required=False, default=None,
)


def _trigger_task(config_uri: str, task_name: str, task_kwargs=None):
    """Trigger a task after initializing the configuration."""
    logging.basicConfig(level=logging.INFO)
    if config_uri:
        settings = get_appsettings(config_uri)
    else:
        settings = None
    config.load_config(settings)
    task_kwargs = task_kwargs or {}

    # Import here or the config will be loaded too early.
    import bodhi.server.tasks
    task = getattr(bodhi.server.tasks, task_name)

    result = task.delay(**task_kwargs)

    if bodhi.server.tasks.app.conf.result_backend is None:
        click.echo(
            "No result backend have been configured in Celery, "
            "I cannot wait for the task to complete."
        )
        return
    try:
        result.get(propagate=True)
    except Exception as e:
        click.echo(str(e))
        sys.exit(1)


@click.command()
@click.version_option(message='%(version)s')
@config_uri_argument
def approve_testing(config_uri):
    """
    Comment on updates that are eligible to be pushed to stable.

    Queries for updates in the testing state that have a NULL request, looping over them looking for
    updates that are eligible to be pushed to stable but haven't had comments from Bodhi to this
    effect. For each such update it finds it will add a comment stating that the update may now be
    pushed to stable.

    This function is the entry point for the bodhi-approve-testing console script.

    Args:
        config_uri (str): The path to the configuration file (example: development.ini)
    """
    _trigger_task(config_uri, "approve_testing_task")


@click.command()
@config_uri_argument
@click.version_option(message='%(version)s')
def check_policies(config_uri):
    """Check the enforced policies by Greenwave for each open update.

    Args:
        config_uri (str): The path to the configuration file (example: development.ini)
    """
    _trigger_task(config_uri, "check_policies_task")


@click.command()
@config_uri_argument
@click.version_option(message='%(version)s')
def clean_old_composes(config_uri):
    """Delete any repo composes that are older than the newest 10 from each repo series.

    Args:
        config_uri (str): The path to the configuration file (example: development.ini)
    """
    _trigger_task(config_uri, "clean_old_composes_task", {"num_to_keep": 10})


@click.command()
@config_uri_argument
@click.version_option(message='%(version)s')
def expire_overrides(config_uri):
    """Search for overrides that are past their expiration date and mark them expired.

    Args:
        config_uri (str): The path to the configuration file (example: development.ini)
    """
    _trigger_task(config_uri, "expire_overrides_task")
