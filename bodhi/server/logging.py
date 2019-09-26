# Copyright © 2019 Red Hat, Inc.
#
# This file is part of Bodhi.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""Utilities for logging in Bodhi."""

import logging

from pyramid import paster
import yaml

from bodhi.server import config


def setup():
    """Set up logging from our config file."""
    pyramid_includes = config.config.get('pyramid.includes', '').split('\n')
    if 'pyramid_sawing' in pyramid_includes:
        # This Bodhi deployment is using pyramid_sawing to configure logging. This means that we
        # cannot use paster.setup_logging() because the main config file doesn't have the logging
        # settings. Let's read the main config file to find out where the logging settings are.
        logging_config = config.config['pyramid_sawing.file']
        with open(logging_config) as logging_config_file:
            logging_config = yaml.safe_load(logging_config_file.read())
        logging.config.dictConfig(logging_config)
    else:
        paster.setup_logging(config.get_configfile())


class RateLimiter(logging.Filter):
    """
    Log filter that rate-limits logs based on time.

    The rate limit is applied to records by filename and line number.

    Filters can be applied to handlers and loggers. Configuring this via
    dictConfig is possible, but has somewhat odd syntax::

        log_config = {
            "filters": {
                "60_second_filter": {
                    "()": "fedmsg_migration_tools.filters.RateLimiter",
                    "rate": "60"
                }
            }
            "handlers": {
                "rate_limited": {
                    "filters": ["60_second_filter"],
                    ...
                }
            }
            "loggers": {
                "fedmsg_migration_tools": {
                    "filters": ["60_second_filter"],
                    ...
                }
            }
        }

    This was shamelessly stolen from
    https://github.com/fedora-infra/fedmsg-migration-tools/blob/0cafc8f/fedmsg_migration_tools/filters.py
    which is also licensed GPLv2+.

    Attributes:
        rate: How often, in seconds, to allow records. Defaults to hourly.
    """

    def __init__(self, rate: int = 3600):
        """
        Initialize the log filter.

        Args:
            rate: How often, in seconds, to allow records. Defaults to hourly.
        """
        self.rate = rate
        self._sent = {}

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Record call sites and filter based on time.

        Args:
            record: The log record we are filtering on.
        Returns:
            True if the record should be emitted, False otherwise.
        """
        key = "{}:{}".format(record.pathname, record.lineno)
        try:
            if self.rate > record.created - self._sent[key]:
                return False
        except KeyError:
            pass
        self._sent[key] = record.created
        return True
