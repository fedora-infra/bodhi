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

import fedmsg.consumers

from pyramid.paster import get_appsettings
from sqlalchemy import engine_from_config

from bodhi.util import transactional_session_maker
from bodhi.models import (
    Update,
    UpdateRequest,
    UpdateType,
    Release,
    UpdateStatus,
    ReleaseState,
    DBSession,
    Base,
)



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
        super(UpdatesHandler, self).__init__(hub, *args, **kwargs)
        self.log.info('Bodhi updates handler listening on: %s' % self.topic)

    def consume(self, msg):
        msg = msg['body']['msg']
        update = msg['update']
        alias = update.get('alias')

        self.log.info("Updates Handler handling %s" % alias)
        if not alias:
            self.log.error("Update Handler received update with no alias.")
            return

        with self.db_factory() as session:
            self.work(session, alias)

        self.log.info("Updates Handler done with %s" % alias)

    def work(self, session, alias):
        raise NotImplementedError
