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
The "updates handler".

This module is responsible for doing value-added work "offline" that used to be
done when updates were submitted.  Specifically, when someone submits an update
we used to:

- Update any bugs in bugzilla associated with the update.
- Check for test cases in the wiki.

Those things could sometimes take a *very* long time, especially if there were
lots of builds and lots of bugs in the update.

Now, update-submission breezes by those steps and simply tells the user "OK".
A fedmsg message gets published when their update goes through, and *that*
message gets received here and triggers us to do all that network-laden heavy
lifting.
"""

import pprint

import fedmsg.consumers

from pyramid.paster import get_appsettings
from sqlalchemy import engine_from_config

from bodhi.exceptions import BodhiException
from bodhi.util import transactional_session_maker
from bodhi.models import (
    Update,
    UpdateType,
    DBSession,
    Base,
)

from bodhi.bugs import bugtracker

import logging
log = logging.getLogger('bodhi')


class UpdatesHandler(fedmsg.consumers.FedmsgConsumer):
    """The Bodhi Updates Handler.

    A fedmsg listener waiting for messages from the frontend about new updates.

    """
    config_key = 'updates_handler'

    def __init__(self, hub, db_factory=None, *args, **kwargs):
        if not db_factory:
            config_uri = '/etc/bodhi/production.ini'
            self.settings = get_appsettings(config_uri)
            engine = engine_from_config(self.settings, 'sqlalchemy.')
            DBSession.configure(bind=engine)
            Base.metadata.create_all(engine)
            self.db_factory = transactional_session_maker
        else:
            self.db_factory = db_factory

        prefix = hub.config.get('topic_prefix')
        env = hub.config.get('environment')
        self.topic = prefix + '.' + env + '.bodhi.update.request.testing'

        self.handle_bugs = bool(self.settings.get('bodhi_email'))
        if not self.handle_bugs:
            log.warn("No bodhi_email defined; not fetching bug details")

        super(UpdatesHandler, self).__init__(hub, *args, **kwargs)
        log.info('Bodhi updates handler listening on: %s' % self.topic)

    def consume(self, msg):
        msg = msg['body']['msg']
        update = msg['update']
        alias = update.get('alias')

        log.info("Updates Handler handling  %s" % alias)
        if not alias:
            log.error("Update Handler got update with no "
                           "alias %s." % pprint.pformat(msg))
            return

        with self.db_factory() as session:
            self.work(session, alias)

        log.info("Updates Handler done with %s" % alias)

    def work(self, session, alias):
        update = Update.get(alias, session)
        if not update:
            raise BodhiException("Couldn't find alias %r in DB" % alias)

        if not self.handle_bugs:
            log.warn("Not configured to handle bugs")

        if self.handle_bugs:
            log.info("Found %i bugs on %r" % (len(update.bugs), alias))
            for bug in update.bugs:
                log.info("Getting RHBZ bug %r" % bug.bug_id)
                rhbz_bug = bugtracker.getbug(bug.bug_id)
                log.info("Updating our details for %r" % bug.bug_id)
                bug.update_details(rhbz_bug)
                log.info("  Got title %r for %r" % (bug.title, bug.bug_id))
                log.info("Modifying %r" % bug.bug_id)
                bug.modified(update)

                # Cool feature.  If you set the type of your update to
                # 'enhancement' but you attach a security bug, we automatically
                # change the type of your update to 'security'.
                if bug.security:
                    log.info("Setting our UpdateType to security.")
                    update.type = UpdateType.security
