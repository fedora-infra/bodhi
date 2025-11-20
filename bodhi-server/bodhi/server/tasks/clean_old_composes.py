# Copyright © 2016-2019 Red Hat, Inc.
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
"""Cleans up old composes that are left over in compose_dir."""

import logging
import collections
import os
import shutil

from bodhi.server import config


log = logging.getLogger(__name__)


def main(num_to_keep: int):
    """
    Delete any repo composes that are older than the newest 10 from each repo series.

    Args:
        num_to_keep: How many of the newest compose dirs to keep during cleanup
    """
    compose_dir = config.config['compose_dir']

    log.info(f'Cleaning {compose_dir}...')
    # This data structure will map the beginning of a group of dirs for the same repo to a list of
    # the dirs that start off the same way.
    pattern_matched_dirs = collections.defaultdict(list)
    with os.scandir(compose_dir) as it:
        for entry in it:
            if entry.is_dir():
                # If this directory ends with a float, it is a candidate for potential deletion
                try:
                    split_dir = entry.name.split('-')
                    float(split_dir[-1])
                except ValueError:
                    # This directory didn't end in a float, so let's just move on to the next one.
                    continue
                pattern = entry.name.replace(split_dir[-1], '')
                pattern_matched_dirs[pattern].append(entry)

    dirs_to_delete = []

    for dirs in pattern_matched_dirs.values():
        if len(dirs) > num_to_keep:
            dirs_to_delete.extend(
                sorted(dirs, key=lambda dir: dir.name, reverse=True)[num_to_keep:])

    if dirs_to_delete:
        log.info('Deleting the following directories:')
        for d in dirs_to_delete:
            log.info(d.path)
            shutil.rmtree(d)
    else:
        log.info('Nothing to delete')
