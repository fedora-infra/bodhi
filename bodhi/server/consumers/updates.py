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

import logging
import pprint
import time

import fedmsg.consumers

from bodhi.server import initialize_db, util, bugs as bug_module
from bodhi.server.config import config
from bodhi.server.exceptions import BodhiException
from bodhi.server.models import Bug, Update, UpdateType


log = logging.getLogger('bodhi')


class UpdatesHandler(fedmsg.consumers.FedmsgConsumer):
    """The Bodhi Updates Handler.

    A fedmsg listener waiting for messages from the frontend about new updates.

    """
    config_key = 'updates_handler'

    def __init__(self, hub, *args, **kwargs):
        initialize_db(config)
        self.db_factory = util.transactional_session_maker()

        prefix = hub.config.get('topic_prefix')
        env = hub.config.get('environment')
        self.topic = [
            prefix + '.' + env + '.bodhi.update.request.testing',
            prefix + '.' + env + '.bodhi.update.edit',
        ]

        self.handle_bugs = bool(config.get('bodhi_email'))
        if not self.handle_bugs:
            log.warn("No bodhi_email defined; not fetching bug details")
        else:
            bug_module.set_bugtracker()

        super(UpdatesHandler, self).__init__(hub, *args, **kwargs)
        log.info('Bodhi updates handler listening on:\n'
                 '%s' % pprint.pformat(self.topic))

    def consume(self, message):
        msg = message['body']['msg']
        topic = message['topic']
        alias = msg['update'].get('alias')

        log.info("Updates Handler handling  %s, %s" % (alias, topic))

        # Go to sleep for a second to try and avoid a race condition
        # https://github.com/fedora-infra/bodhi/issues/458
        time.sleep(1)

        if not alias:
            log.error("Update Handler got update with no "
                      "alias %s." % pprint.pformat(msg))
            return

        with self.db_factory() as session:
            update = Update.get(alias, session)
            if not update:
                raise BodhiException("Couldn't find alias %r in DB" % alias)

            if topic.endswith('update.edit'):
                bugs = [Bug.get(idx, session) for idx in msg['new_bugs']]
                # Sanity check
                for bug in bugs:
                    assert bug in update.bugs
            elif topic.endswith('update.request.testing'):
                bugs = update.bugs
            else:
                raise NotImplementedError("Should never get here.")

            self.work_on_bugs(session, update, bugs)
            self.fetch_test_cases(session, update)

        log.info("Updates Handler done with %s, %s" % (alias, topic))

    def fetch_test_cases(self, session, update):
        """ Query the wiki for test cases for each package """
        for build in update.builds:
            build.package.fetch_test_cases(session)

    def work_on_bugs(self, session, update, bugs):

        if not self.handle_bugs:
            log.warn("Not configured to handle bugs")
            return

        log.info("Got %i bugs to sync for %r" % (len(bugs), update.alias))
        for bug in bugs:
            log.info("Getting RHBZ bug %r" % bug.bug_id)
            try:
                rhbz_bug = bug_module.bugtracker.getbug(bug.bug_id)

                log.info("Updating our details for %r" % bug.bug_id)
                bug.update_details(rhbz_bug)
                log.info("  Got title %r for %r" % (bug.title, bug.bug_id))

                # If you set the type of your update to 'enhancement' but you
                # attach a security bug, we automatically change the type of your
                # update to 'security'. We need to do this first, so we don't
                # accidentally comment on stuff that we shouldn't.
                if bug.security:
                    log.info("Setting our UpdateType to security.")
                    update.type = UpdateType.security

                log.info("Commenting on %r" % bug.bug_id)
                comment = config['initial_bug_msg'] % (
                    update.title, update.release.long_name, update.abs_url())
                bug.add_comment(update, comment)

                log.info("Modifying %r" % bug.bug_id)
                bug.modified(update)
            except Exception:
                log.warning('Error occured during updating single bug', exc_info=True)
