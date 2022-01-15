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
The Bodhi handler that is listening for CI messages.

This module is responsible for creating comment on update when CI starts tests.
"""

import logging

import fedora_messaging

from bodhi.server import buildsys
from bodhi.server.models import Build
from bodhi.server.util import transactional_session_maker

log = logging.getLogger('bodhi')


class CIHandler:
    """
    The Bodhi CI Handler.

    A consumer that listens for messages about CI tests and comments on
    updates.
    """

    def __init__(self, db_factory: transactional_session_maker = None):
        """
        Initialize the CI Handler.

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
        """Comment on related update.

        Args:
            message: The message we are processing.
        """
        body = message.body

        missing = []
        for mandatory in ('contact', 'run', 'artifact', 'pipeline', 'test',
                          'generated_at', 'version'):
            if mandatory not in body:
                missing.append(mandatory)
        if missing:
            log.debug(f"Received incomplete CI message. Missing: {', '.join(missing)}")
            return

        nvr = body['artifact'].get('nvr', None)
        build_id = body['pipeline'].get('id', None)
        run_url = body['run'].get('url', None)

        koji = buildsys.get_session()

        if not nvr and build_id:
            kbuildinfo = koji.getBuild(build_id)
            log.debug(kbuildinfo)
            if not kbuildinfo:
                log.debug(f"Can't find Koji build with id '{build_id}'.")
                return
            elif 'nvr' not in kbuildinfo:
                log.debug(f"Koji build info with id '{build_id}' doesn't contain 'nvr'.")
                return
            else:
                nvr = kbuildinfo['nvr']
        elif not nvr and not build_id:
            log.debug("Received incomplete CI message. Missing: 'artifact.nvr', 'pipeline.id'.")
            return

        with self.db_factory() as dbsession:
            build = dbsession.query(Build).filter_by(nvr=nvr).first()
            if not build:
                log.debug(f"Can't get build for '{nvr}'.")
                return

            if build.update:
                if build.update.from_tag:
                    log.debug("Update is created from tag. Skipping comment.")
                    return
                comment = "CI testing started."
                if run_url:
                    comment = f"CI testing started: '{run_url}'."
                build.update.comment(
                    dbsession, text=comment, author='bodhi', email_notification=False)
            else:
                log.debug(f"No update in Bodhi for '{nvr}'. Nothing to comment on.")
                return

            log.debug("Committing changes to the database.")
            dbsession.commit()
