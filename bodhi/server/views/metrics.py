# -*- coding: utf-8 -*-
# Copyright © 2014-2017 Red Hat, Inc. and others.
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
"""Define the view that presents release metrics in the web UI."""

import json

from pyramid.view import view_config

import bodhi.server.models as m


def compute_ticks_and_data(db, releases, update_types):
    """
    Return the data and ticks to make the stats graph.

    Args:
        db (sqlalchemy.orm.session.Session): The database Session.
        releases (list): A list of release objects we are interested in generating metrics on.
        update_types (dict): A dictionary mapping the possible types of updates to human readable
            string defining them.
    Returns:
        tuple: A 2-tuple of data that can be graphed by the UI javascript.
    """
    data, ticks = [], []

    releases = sorted(releases, key=lambda x: int(x.version_int))

    for i, release in enumerate(releases):
        ticks.append([i, release.name])

    for update_type, label in update_types.items():
        d = []
        update_type = m.UpdateType.from_string(update_type)
        for i, release in enumerate(releases):
            num = db.query(m.Update).filter_by(
                release=release,
                type=update_type,
                status=m.UpdateStatus.stable
            ).count()
            d.append([i, num])
        data.append(dict(data=d, label=label))

    return (data, ticks)


@view_config(route_name='metrics', renderer='metrics.html')
def metrics(request):
    """
    Return a response with metric data to be graphed.

    Args:
        request (pyramid.util.Request): The current Request.
    Returns:
        dict: A dictionary with keys 'data', 'ticks', 'eldata', and 'elticket'. The 'el' prefixed
            keys are for enterprise Linux. These data are used to render the graphs by the template
            JavaScript.
    """
    db = request.db

    update_types = {
        'bugfix': 'Bug fixes',
        'enhancement': 'Enhancements',
        'security': 'Security updates',
        'newpackage': 'New packages'
    }

    releases = db.query(m.Release).filter(m.Release.name.like(u'F%')).all()
    data, ticks = compute_ticks_and_data(db, releases, update_types)

    releases = db.query(m.Release).filter(m.Release.name.like(u'E%')).all()
    eldata, elticks = compute_ticks_and_data(db, releases, update_types)

    return {
        'data': json.dumps(data), 'ticks': json.dumps(ticks),
        'eldata': json.dumps(eldata), 'elticks': json.dumps(elticks),
    }
