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
The "signed handler".

This module is responsible for marking builds as "signed" when they get moved
from the pending-signing to pending-updates-testing tag by RoboSignatory.
"""

import logging
import pprint

import fedmsg.consumers
from pyramid.paster import get_appsettings
from sqlalchemy import engine_from_config

from bodhi.server.models import Base, Build, Release
from bodhi.server.util import transactional_session_maker

log = logging.getLogger('bodhi')


class SignedHandler(fedmsg.consumers.FedmsgConsumer):
    """The Bodhi Signed Handler.

    A fedmsg listener waiting for messages from koji about builds being tagged.

    """
    config_key = 'signed_handler'

    def __init__(self, hub, *args, **kwargs):
        config_uri = '/etc/bodhi/production.ini'
        self.settings = get_appsettings(config_uri)
        engine = engine_from_config(self.settings, 'sqlalchemy.')
        Base.metadata.create_all(engine)
        self.db_factory = transactional_session_maker(engine)

        prefix = hub.config.get('topic_prefix')
        env = hub.config.get('environment')
        self.topic = [
            prefix + '.' + env + '.buildsys.tag'
        ]

        log.info('Bodhi signed handler listening on:\n'
                 '%s' % pprint.pformat(self.topic))

    def consume(self, message):
        msg = message['body']['msg']
        topic = message['topic']

        log.info("Signed Handler handling  %s, %s" % (alias, topic))

        build_nvr = '%(name)s-%(version)s-%(release)s' % msg
        tag = msg['tag']

        log.info("%s tagged into %s" % (build_nvr, tag))

        with self.db_factory() as session:
            build = Build.get(build_nvr, session)
            if not build:
                log.info("Build was not submitted, skipping")
                return

            if build.release.pending_testing_tag != tag:
                log.info("Tag is not pending_testing tag, skipping")
                return

            # This build was moved into the pending_testing tag for the applicable release, which
            # is done by RoboSignatory to indicate that the build has been correctly signed and
            # written out. Mark it as such.
            log.info("Build has been signed, marking")
            build.signed = True
            log.info("Build %s has been marked as signed" % build_nvr)
