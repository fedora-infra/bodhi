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

from time import sleep
import logging
import re

import fedora_messaging

from bodhi.server import buildsys
from bodhi.server.config import config
from bodhi.server.models import (
    Bug, Build, ContentType, Package, Release, Update, UpdateStatus, UpdateType, User)
from bodhi.server.tasks import work_on_bugs_task
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

        if kbuildinfo['owner_name'] in config.get('automatic_updates_blacklist'):
            log.debug(f"{bnvr} owned by {kbuildinfo['owner_name']} who is listed in "
                      "automatic_updates_blacklist, skipping.")
            return

        # some APIs want the Koji build info, some others want the same
        # wrapped in a larger (request?) structure
        rbuildinfo = {
            'info': kbuildinfo,
            'nvr': kbuildinfo['nvr'].rsplit('-', 2),
        }

        with self.db_factory() as dbsession:
            rel = dbsession.query(Release).filter_by(create_automatic_updates=True,
                                                     candidate_tag=btag).first()
            if not rel:
                log.debug(f"Ignoring build being tagged into {btag!r}, no release configured for "
                          "automatic updates for it found.")
                return

            bcls = ContentType.infer_content_class(Build, kbuildinfo)
            build = bcls.get(bnvr)
            if build and build.update:
                log.info(f"Build, active update for {bnvr} exists already, skipping.")
                return

            utype = (
                UpdateType.unspecified if Package.check_existence(rbuildinfo)
                else UpdateType.newpackage
            )

            if not build:
                log.debug(f"Build for {bnvr} doesn't exist yet, creating.")

                # Package.get_or_create() infers content type already
                log.debug("Getting/creating related package object.")
                pkg = Package.get_or_create(dbsession, rbuildinfo)

                log.debug("Creating build object, adding it to the DB.")
                build = bcls(nvr=bnvr, package=pkg, release=rel)
                dbsession.add(build)

            owner_name = kbuildinfo['owner_name']
            user = User.get(owner_name)
            if not user:
                log.debug(f"Creating bodhi user for '{owner_name}'.")
                # Leave email, groups blank, these will be filled
                # in or updated when they log into Bodhi next time, see
                # bodhi.server.auth.utils:remember_me().
                user = User(name=owner_name)
                dbsession.add(user)

            log.debug(f"Creating new update for {bnvr}.")
            try:
                changelog = build.get_changelog(lastupdate=True)
            except ValueError as e:
                # Often due to bot-generated builds
                # https://pagure.io/koji/issue/3178
                log.warning(str(e))
                sleep(5)
                # Re-raise exception, so that the message can be re-queued
                raise
            except Exception:
                # Re-raise exception, so that the message can be re-queued
                raise
            closing_bugs = []
            if changelog:
                log.debug("Adding changelog to update notes.")
                notes = f"""Automatic update for {bnvr}.

##### **Changelog**

```
{changelog}
```"""

                if rel.name not in config.get('bz_exclude_rels'):
                    for b in re.finditer(config.get('bz_regex'), changelog, re.IGNORECASE):
                        idx = int(b.group(1))
                        log.debug(f'Adding bug #{idx} to the update.')
                        bug = Bug.get(idx)
                        if bug is None:
                            bug = Bug(bug_id=idx)
                            dbsession.add(bug)
                            dbsession.flush()
                        if bug not in closing_bugs:
                            closing_bugs.append(bug)
            else:
                notes = f"Automatic update for {bnvr}."
            update = Update(
                release=rel,
                builds=[build],
                bugs=closing_bugs,
                notes=notes,
                type=utype,
                stable_karma=3,
                unstable_karma=-3,
                autokarma=False,
                user=user,
                status=UpdateStatus.pending,
                critpath=Update.contains_critpath_component([build], rel.branch),
            )

            # Comment on the update that it was automatically created.
            update.comment(
                dbsession,
                str("This update was automatically created"),
                author="bodhi",
            )

            update.add_tag(update.release.pending_signing_tag)

            log.debug("Adding new update to the database.")
            dbsession.add(update)

            log.debug("Flushing changes to the database.")
            dbsession.flush()

            # Obsolete older updates which may be stuck in testing due to failed gating
            try:
                update.obsolete_older_updates(dbsession)
            except Exception as e:
                log.error(f'Problem obsoleting older updates: {e}')

            alias = update.alias
            buglist = [b.bug_id for b in update.bugs]

        # This must be run after dbsession is closed so changes are committed to db
        work_on_bugs_task.delay(alias, buglist)
