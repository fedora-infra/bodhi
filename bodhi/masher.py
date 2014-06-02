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

import fedmsg.consumers

from pprint import pprint
from pyramid.paster import bootstrap

from bodhi import log
from bodhi.config import config, get_configfile
from bodhi.models import Update


class Masher(fedmsg.consumers.FedmsgConsumer):
    """The Bodhi Masher.

    A fedmsg consumer that listens for messages from releng members.

    An updates "push" consists of::

    - verify that the message was sent by someone in releng
    - determine which updates to push
    - Lock repo
      - track which repos were completed
      - track which packages are in the push
      - lock updates
    - Move build tags
    - Update security bug titles
    - Expire buildroot overrides
    - Remove pending tags
    - mash
    - request_complete
    - Add testing updates to updates-testing digest
    - Generate/update updateinfo.xml and inject it into the repodata
    - Sanity check the repo
    - Flip the symlinks to the new repo
    - Cache the latest repodata
    - Wait for the repo to hit the master mirror
    - Update bugzillas
    - Add comments to updates
    - Generate and email stable update notices
    - Email updates-testing digest
    - Unlock repo
        - unlock updates
        - see if any updates now meet the stable criteria, and set the request
    - Send fedmsgs

    """
    config_key = 'masher'

    def __init__(self, hub, *args, **kw):
        prefix = hub.config.get('topic_prefix')
        env = hub.config.get('environment')
        self.topic = prefix + '.' + env + '.' + hub.config.get('masher_topic')
        log.info('Bodhi masher listening on topic: %s' % self.topic)
        super(Masher, self).__init__(hub, *args, **kw)

    def consume(self, msg):
        pprint(msg)
        body = msg['body']['msg']
        env = bootstrap(get_configfile())
        db = env['request'].db

        if not self.validate_msg_cert(msg):
            log.warn('Received message with invalid signature! Ignoring...')
            # TODO: send email notifications
            return

    def validate_msg_cert(self, msg):
        """ Verify that this message was signed by releng """
        valid_signer = config.get('releng_fedmsg_certname')
        if valid_signer:
            return fedmsg.crypto.validate_signed_by(msg, valid_signer,
                                                    **self.hub.config)
        else:
            log.warn('No releng_fedmsg_certname defined. Cert validation disabled')
            return True
