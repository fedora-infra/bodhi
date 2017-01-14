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

import copy
import socket

import fedmsg
import fedmsg.config
import fedmsg.encoding
import transaction

import bodhi.server
import bodhi.server.config


def init(active=None, cert_prefix=None):
    if not bodhi.server.config.config.get('fedmsg_enabled'):
        bodhi.server.log.warn("fedmsg disabled.  not initializing.")
        return

    fedmsg_config = fedmsg.config.load_config()

    # Only override config from disk if explicitly argued.
    if active is not None:
        fedmsg_config['active'] = active
        fedmsg_config['name'] = 'relay_inbound'
    else:
        hostname = socket.gethostname().split('.', 1)[0]
        fedmsg_config['name'] = 'bodhi.%s' % hostname

    if cert_prefix is not None:
        fedmsg_config['cert_prefix'] = cert_prefix

    fedmsg.init(**fedmsg_config)
    bodhi.server.log.info("fedmsg initialized")


def publish(topic, msg, force=False):
    """ Publish a message to fedmsg.

    By default, messages are not sent immediately, but are queued in a
    transaction "data manager".  They will only get published after the
    sqlalchemy transaction completes successfully and will not be published at
    all if it fails, aborts, or rolls back.

    Specifying force=True to this function by-passes that -- messages are sent
    immediately.
    """
    if not bodhi.server.config.config.get('fedmsg_enabled'):
        bodhi.server.log.warn("fedmsg disabled.  not sending %r" % topic)
        return

    # Initialize right before we try to publish, but only if we haven't
    # initialized for this thread already.
    if not fedmsg_is_initialized():
        init()

    if force:
        bodhi.server.log.debug("fedmsg skipping transaction and sending %r" % topic)
        fedmsg.publish(topic=topic, msg=msg)
    else:
        bodhi.server.log.debug("fedmsg enqueueing %r" % topic)
        manager = _managers_map.get_current_data_manager()
        manager.enqueue(topic, msg)


def fedmsg_is_initialized():
    """ Return True or False if fedmsg is initialized or not. """
    local = getattr(fedmsg, '__local')
    if not hasattr(local, '__context'):
        return False
    # Ensure that fedmsg has an endpoint to publish to.
    context = getattr(local, '__context')
    return hasattr(context, 'publisher')


class ManagerMapping(object):
    """ Maintain a two-way one-to-one mapping between transaction managers and
    data managers (for different wsgi threads in the same process). """

    def __init__(self):
        self._left = {}
        self._right = {}

    def get_current_data_manager(self):
        current_transaction_manager = transaction.get()
        if current_transaction_manager not in self:
            current_data_manager = FedmsgDataManager()
            self.add(current_transaction_manager, current_data_manager)
            current_transaction_manager.join(current_data_manager)
        else:
            current_data_manager = self.get(current_transaction_manager)
        return current_data_manager

    def add(self, transaction_manager, data_manager):
        self._left[transaction_manager] = data_manager
        self._right[data_manager] = transaction_manager

    def __contains__(self, item):
        return item in self._left or item in self._right

    def get(self, transaction_manager):
        return self._left[transaction_manager]

    def remove(self, data_manager):
        transaction_manager = self._right[data_manager]
        del self._left[transaction_manager]
        del self._right[data_manager]

    def __repr__(self):
        return "<ManagerMapping: left(%i) right(%i)>" % (
            len(self._left),
            len(self._right),
        )


# This is a global object we'll maintain to keep track of the relationship
# between transaction managers and our data managers.  It ensures that we don't
# create multiple data managers per transaction and that we don't join the same
# data manager to a transaction multiple times.  Our data manager should clean
# up after itself and remove old tm/dm pairs from this mapping in the event of
# abort or commit.
_managers_map = ManagerMapping()


class FedmsgDataManager(object):
    transaction_manager = transaction.manager

    def __init__(self):
        self.uncommitted = []
        self.committed = []

    def enqueue(self, topic, msg):
        self.uncommitted.append((topic, msg,))

    def __repr__(self):
        return self.uncommitted.__repr__()

    def abort(self, transaction):
        self.uncommitted = copy.copy(self.committed)
        if self in _managers_map:
            _managers_map.remove(self)

    def tpc_begin(self, transaction):
        pass

    def commit(self, transaction):
        pass

    def tpc_vote(self, transaction):
        # This ensures two things:
        # 1) that all the objects we're about to publish are JSONifiable.
        # 2) that we convert them from sqlalchemy objects to dicts *before* the
        #    transaction enters its final phase, at which point our objects
        #    will be detached from their session.
        self.uncommitted = [
            (topic, fedmsg.encoding.loads(fedmsg.encoding.dumps(msg)))
            for topic, msg in self.uncommitted
        ]

        # Ensure that fedmsg has already been initialized.
        assert fedmsg_is_initialized(), "fedmsg is not initialized"

    def tpc_abort(self, transaction):
        self.abort(transaction)
        self._finish('aborted')

    def tpc_finish(self, transaction):
        for topic, msg in self.uncommitted:
            bodhi.server.log.debug("fedmsg sending %r" % topic)
            fedmsg.publish(topic=topic, msg=msg)
        self.committed = copy.copy(self.uncommitted)
        _managers_map.remove(self)
        self._finish('committed')

    def _finish(self, state):
        self.state = state

    def sortKey(self):
        """ Use a 'z' to make fedmsg come last, after the db is done. """
        return 'z_fedmsgdm' + str(id(self))

    def savepoint(self):
        return FedmsgSavepoint(self)


class FedmsgSavepoint(object):
    def __init__(self, dm):
        self.dm = dm
        self.saved_committed = copy.copy(self.dm.uncommitted)

    def rollback(self):
        self.dm.uncommitted = copy.copy(self.saved_committed)
