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

import fedmsg
import fedmsg.config

import bodhi
import bodhi.config


def init(active=None, cert_prefix=None):
    if not bodhi.config.config.get('fedmsg_enabled'):
        bodhi.log.warn("fedmsg disabled.  not initializing.")
        return

    fedmsg_config = fedmsg.config.load_config()

    # Only override config from disk if explicitly argued.
    if active is not None:
        fedmsg_config['active'] = active
        fedmsg_config['name'] = 'relay_inbound'
    if cert_prefix is not None:
        fedmsg_config['cert_prefix'] = cert_prefix

    fedmsg.init(**fedmsg_config)
    bodhi.log.info("fedmsg initialized")


def publish(topic, msg):
    if not bodhi.config.config.get('fedmsg_enabled'):
        bodhi.log.warn("fedmsg disabled.  not sending %r" % topic)
        return

    bodhi.log.debug("fedmsg sending %r" % topic)
    fedmsg.publish(topic=topic, msg=msg)
