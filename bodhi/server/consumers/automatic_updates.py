# Copyright © 2019 Red Hat, Inc. and others.
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
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""
The Bodhi handler that creates updates automatically from tagged builds.

This module is responsible for the process of creating updates when builds are
tagged with certain tags.
"""

import logging

import fedora_messaging

from bodhi.server import buildsys
from bodhi.server.config import config
from bodhi.server.models import Build, ContentType, Package, Release, TestGatingStatus
from bodhi.server.models import Update, UpdateStatus, UpdateType, User
from bodhi.server.util import transactional_session_maker

log = logging.getLogger('bodhi')


class AutomaticUpdateHandler:
    """
    The Bodhi Automatic Update Handler.

    A consumer that listens for messages about tagged builds and creates
    updates from them.
    """

    def __init__(self, db_factory: transactional_session_maker = None):
        """
        Initialize the Automatic Update Handler.

        Args:
            db_factory: If given, used as the db_factory for this handler. If
            None (the default), a new TransactionalSessionMaker is created and
            used.
        """
        if not db_factory:
            self.db_factory = transactional_session_maker()
        else:
            self.db_factory = db_factory

    def __call__(self, message: fedora_messaging.api.Message) -> None:
        """Create updates from appropriately tagged builds.

        Args:
            message: The message we are processing.
        """
        body = message.body

        missing = []
        for mandatory in ('tag', 'build_id', 'name', 'version', 'release'):
            if mandatory not in body:
                missing.append(mandatory)
        if missing:
            log.debug(f"Received incomplete tag message. Missing: {', '.join(missing)}")
            return

        btag = body['tag']
        bnvr = '{name}-{version}-{release}'.format(**body)

        koji = buildsys.get_session()

        kbuildinfo = koji.getBuild(bnvr)
        if not kbuildinfo:
            log.debug(f"Can't find Koji build for {bnvr}.")
            return

        if 'nvr' not in kbuildinfo:
            log.debug(f"Koji build info for {bnvr} doesn't contain 'nvr'.")
            return

        if 'owner_name' not in kbuildinfo:
            log.debug(f"Koji build info for {bnvr} doesn't contain 'owner_name'.")
            return

        # some APIs want the Koji build info, some others want the same
        # wrapped in a larger (request?) structure
        rbuildinfo = {
            'info': kbuildinfo,
            'nvr': kbuildinfo['nvr'].rsplit('-', 2),
        }

        with self.db_factory() as dbsession:
            rel = dbsession.query(Release).filter_by(create_automatic_updates=True,
                                                     pending_testing_tag=btag).first()
            if not rel:
                log.debug(f"Ignoring build being tagged into {btag!r}, no release configured for "
                          "automatic updates for it found.")
                return

            bcls = ContentType.infer_content_class(Build, kbuildinfo)
            build = bcls.get(bnvr)
            if build:
                if build.update.status == UpdateStatus.pending:
                    log.info(
                        f"Build, active update for {bnvr} exists already "
                        "in Pending, moving it along.")
                    build.update.status = UpdateStatus.testing
                    build.update.request = None
                    dbsession.add(build)
                    if config.get('test_gating.required'):
                        log.debug(
                            'Test gating is required, marking the update as waiting on test '
                            'gating and updating it from Greenwave to get the real status.')
                        build.update.test_gating_status = TestGatingStatus.waiting
                        build.update.update_test_gating_status()
                    dbsession.commit()
                else:
                    log.info(f"Build, active update for {bnvr} exists already, skipping.")
                return

            log.debug(f"Build for {bnvr} doesn't exist yet, creating.")

            # Package.get_or_create() infers content type already
            log.debug("Getting/creating related package object.")
            pkg = Package.get_or_create(rbuildinfo)

            log.debug("Creating build object, adding it to the DB.")
            build = bcls(nvr=bnvr, package=pkg)
            dbsession.add(build)

            owner_name = kbuildinfo['owner_name']
            user = User.get(owner_name)
            if not user:
                log.debug(f"Creating bodhi user for '{owner_name}'.")
                # Leave email, groups blank, these will be filled
                # in or updated when they log into Bodhi next time, see
                # bodhi.server.security:remember_me().
                user = User(name=owner_name)
                dbsession.add(user)

            log.debug(f"Creating new update for {bnvr}.")
            update = Update(
                release=rel,
                builds=[build],
                notes=f"Automatic update for {bnvr}.",
                type=UpdateType.unspecified,
                stable_karma=3,
                unstable_karma=-3,
                user=user,
                status=UpdateStatus.testing,
            )

            # Comment on the update that it was automatically created.
            update.comment(
                dbsession,
                str("This update was automatically created"),
                author="bodhi",
            )

            if config.get('test_gating.required'):
                log.debug(
                    'Test gating required is enforced, marking the update as '
                    'waiting on test gating and updating it from Greenwave to '
                    'get the real status.')
                update.test_gating_status = TestGatingStatus.waiting
                update.update_test_gating_status()

            log.debug("Adding new update to the database.")
            dbsession.add(update)

            log.debug("Committing changes to the database.")
            dbsession.commit()
