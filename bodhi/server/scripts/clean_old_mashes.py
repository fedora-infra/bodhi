# -*- coding: utf-8 -*-
# Copyright © 2016-2018 Red Hat, Inc.
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
"""Cleans up old mashes that are left over in mash_dir."""
import collections

import click
import os
import shutil

from bodhi.server import config


# How many of the newest mash dirs to keep during cleanup
NUM_TO_KEEP = 10


@click.command()
@click.version_option(message='%(version)s')
def clean_up():
    """Delete any repo mashes that are older than the newest 10 from each repo series."""
    remove_old_composes()


# Helper function used in auto clean composes (masher.py)
def remove_old_composes():
    """Delete any repo mashes that are older than the newest 10 from each repo series."""
    mash_dir = config.config['mash_dir']

    # This data structure will map the beginning of a group of dirs for the same repo to a list of
    # the dirs that start off the same way.
    pattern_matched_dirs = collections.defaultdict(list)

    for directory in [d for d in os.listdir(mash_dir) if os.path.isdir(os.path.join(mash_dir, d))]:
        # If this directory ends with a float, it is a candidate for potential deletion
        try:
            split_dir = directory.split('-')
            float(split_dir[-1])
        except ValueError:
            # This directory didn't end in a float, so let's just move on to the next one.
            continue

        pattern = directory.replace(split_dir[-1], '')
        pattern_matched_dirs[pattern].append(directory)

    dirs_to_delete = []

    for dirs in pattern_matched_dirs.values():
        if len(dirs) > NUM_TO_KEEP:
            dirs_to_delete.extend(sorted(dirs, reverse=True)[NUM_TO_KEEP:])

    if dirs_to_delete:
        print('Deleting the following directories:')
        for d in dirs_to_delete:
            d = os.path.join(mash_dir, d)
            print(d)
            shutil.rmtree(d)
