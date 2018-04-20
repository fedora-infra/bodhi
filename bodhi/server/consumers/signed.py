# -*- coding: utf-8 -*-
# Copyright © 2016-2018 Red Hat, Inc.
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
The "signed handler".

This module is responsible for marking builds as "signed" when they get moved
from the pending-signing to pending-updates-testing tag by RoboSignatory.
"""

import logging
import pprint

import fedmsg.consumers

from bodhi.server import initialize_db
from bodhi.server.config import config
from bodhi.server.models import Build
from bodhi.server.util import transactional_session_maker


log = logging.getLogger('bodhi')


class SignedHandler(fedmsg.consumers.FedmsgConsumer):
    """
    The Bodhi Signed Handler.

    A fedmsg listener waiting for messages from koji about builds being tagged.
    """

    config_key = 'signed_handler'

    def __init__(self, hub, *args, **kwargs):
        """
        Initialize the SignedHandler, configuring its topic and database.

        Args:
            hub (moksha.hub.hub.CentralMokshaHub): The hub this handler is consuming messages from.
                It is used to look up the hub config.
        """
        initialize_db(config)
        self.db_factory = transactional_session_maker()

        prefix = hub.config.get('topic_prefix')
        env = hub.config.get('environment')
        self.topic = [
            prefix + '.' + env + '.buildsys.tag'
        ]

        super(SignedHandler, self).__init__(hub, *args, **kwargs)
        log.info('Bodhi signed handler listening on:\n'
                 '%s' % pprint.pformat(self.topic))

    def consume(self, message):
        """
        Handle fedmsgs arriving with the configured topic.

        This marks a build as signed if it is assigned to the pending testing release tag.

        Example message format::
            {
                u'body': {
                    u'i': 628,
                    u'timestamp': 1484692585,
                    u'msg_id': u'2017-821031da-be3a-4f4b-91df-0baa834ca8a4',
                    u'crypto': u'x509',
                    u'topic': u'org.fedoraproject.prod.buildsys.tag',
                    u'signature': u'100% real please trust me',
                    u'msg': {
                        u'build_id': 442562,
                        u'name': u'colord',
                        u'tag_id': 214,
                        u'instance': u's390',
                        u'tag': 'f26-updates-testing-pending',
                        u'user': u'sharkcz',
                        u'version': u'1.3.4',
                        u'owner': u'sharkcz',
                        u'release': u'1.fc26'
                    },
                },
            }

        The message can contain additional keys.

        Args:
            message (dict): The incoming fedmsg in the format described above.
        """
        msg = message['body']['msg']

        build_nvr = '%(name)s-%(version)s-%(release)s' % msg
        tag = msg['tag']

        log.info("%s tagged into %s" % (build_nvr, tag))

        with self.db_factory():
            build = Build.get(build_nvr)
            if not build:
                log.info("Build was not submitted, skipping")
                return

            if not build.release:
                log.info('Build is not assigned to release, skipping')
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
