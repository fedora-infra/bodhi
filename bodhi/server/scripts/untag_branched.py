# -*- coding: utf-8 -*-
# Copyright © 2015-2018 Red Hat, Inc. and others.
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
"""
Used to remove the pending and testing tags from updates in a branched release.

Since a separate task mashes the branched stable repos, this will leave
those stable updates with the testing tags for 1 day before untagging.

https://github.com/fedora-infra/bodhi/issues/576
"""

import os
import sys
import logging

from datetime import datetime, timedelta

from pyramid.paster import get_appsettings, setup_logging

from ..models import Release, ReleaseState, Update, UpdateStatus

from bodhi.server import buildsys, Session, initialize_db


def usage(argv):
    """
    Print usage information and exit with code 1.

    Args:
        argv (list): The arguments passed to the script.
    """
    cmd = os.path.basename(argv[0])
    print('usage: %s <config_uri>\n'
          '(example: "%s development.ini")' % (cmd, cmd))
    sys.exit(1)


def main(argv=sys.argv):
    """
    Remove the pending and testing tags from branched updates.

    Args:
        argv (list): The arguments passed to the script. Defaults to sys.argv.
    """
    if len(argv) != 2:
        usage(argv)

    config_uri = argv[1]

    setup_logging(config_uri)
    log = logging.getLogger(__name__)

    settings = get_appsettings(config_uri)
    initialize_db(settings)
    db = Session()
    koji = buildsys.get_session()
    one_day = timedelta(days=1)
    now = datetime.utcnow()

    try:
        for release in db.query(Release).filter_by(
                state=ReleaseState.pending).all():
            log.info(release.name)
            for update in db.query(Update).filter_by(
                    release=release, status=UpdateStatus.stable).all():
                assert update.date_stable, update.title
                if now - update.date_stable > one_day:
                    for build in update.builds:
                        tags = build.get_tags()
                        stable_tag = release.dist_tag
                        testing_tag = release.testing_tag
                        pending_signing_tag = release.pending_signing_tag
                        pending_testing_tag = release.pending_testing_tag
                        if stable_tag not in tags:
                            log.error('%s not tagged as stable %s' % (build.nvr, tags))
                            continue
                        if testing_tag in tags:
                            log.info('Removing %s from %s' % (testing_tag, build.nvr))
                            koji.untagBuild(testing_tag, build.nvr)
                        if pending_signing_tag in tags:
                            log.info('Removing %s from %s' % (pending_signing_tag, build.nvr))
                            koji.untagBuild(pending_signing_tag, build.nvr)
                        if pending_testing_tag in tags:
                            log.info('Removing %s from %s' % (pending_testing_tag, build.nvr))
                            koji.untagBuild(pending_testing_tag, build.nvr)
        db.commit()
    except Exception as e:
        log.error(e)
        db.rollback()
        Session.remove()
        sys.exit(1)
