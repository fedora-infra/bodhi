# -*- coding: utf-8 -*-
# Copyright ® 2017 Red Hat, Inc.
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
"""Iterate updates that don't have final CI statuses to see if we missed messages about them."""
import click

from bodhi.server import config, initialize_db, models, Session


@click.command()
@click.version_option(message='%(version)s')
def babysit():
    """Iterate over updates that don't have final CI statuses to see if we missed messages."""
    initialize_db(config.config)
    session = Session()

    for b in models.Build.query.filter(models.Build.ci_status.in_(
            [models.CiStatus.waiting, models.CiStatus.queued, models.CiStatus.running])):
        # We might have failed to look up the scm_url when the update was created, so let's make
        # sure we know one now so we can use it to look up test results with it.
        if not b.scm_url:
            b.scm_url = b.get_scm_url()

        if session.is_modified(b):
            session.commit()
