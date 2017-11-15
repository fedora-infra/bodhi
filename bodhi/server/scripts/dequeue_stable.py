# -*- coding: utf-8 -*-
# Copyright © 2017 Caleigh Runge-Hottman and Red Hat, Inc.
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
"""This script is responsible for moving all updates with a batched request to a stable request."""

import sys

import click

from bodhi.server import buildsys, config, models, Session, initialize_db


@click.command()
@click.version_option(message='%(version)s')
def dequeue_stable():
    """Convert all batched requests to stable requests."""
    initialize_db(config.config)
    buildsys.setup_buildsystem(config.config)
    db = Session()

    try:
        batched = db.query(models.Update).filter_by(request=models.UpdateRequest.batched).all()
        for update in batched:
            try:
                update.set_request(db, models.UpdateRequest.stable, u'bodhi')
                db.commit()
            except Exception as e:
                print('Unable to stabilize {}: {}'.format(update.alias, str(e)))
                db.rollback()
                msg = u"Bodhi is unable to request this update for stabilization: {}"
                update.comment(db, msg.format(str(e)), author=u'bodhi')
                db.commit()
    except Exception as e:
        print(str(e))
        sys.exit(1)
    finally:
        Session.remove()
