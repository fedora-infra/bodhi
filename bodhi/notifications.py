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

import transaction

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

    bodhi.log.debug("fedmsg enqueueing %r" % topic)

    manager = _managers_map.get_current_data_manager()
    manager.enqueue(topic, msg)


class ManagerMapping(object):
    """ Maintain a two-way one-to-one mapping between transaction managers and
    data managers (for different wsgi threads in the same process). """

    def __init__(self):
        self.left = {}
        self.right = {}

    def get_current_data_manager(self):
        current_transaction_manager = transaction.get()
        if not current_transaction_manager in self:
            current_data_manager = FedmsgDataManager()
            self.add(current_transaction_manager, current_data_manager)
            current_transaction_manager.join(current_data_manager)
        else:
            current_data_manager = self.get(current_transaction_manager)
        return current_data_manager

    def add(self, transaction_manager, data_manager):
        self.left[transaction_manager] = data_manager
        self.right[data_manager] = transaction_manager

    def __contains__(self, item):
        return item in self.left or item in self.right

    def get(self, transaction_manager):
        return self.left[transaction_manager]

    def remove(self, data_manager):
        transaction_manager = self.right[data_manager]
        del self.left[transaction_manager]
        del self.right[data_manager]


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
        _managers_map.remove(self)

    def tpc_begin(self, transaction):
        pass

    def commit(self, transaction):
        pass

    def tpc_vote(self, transaction):
        #raise NotImplementedError("Check that fedmsg is initialized and that messages are serializable")
        # We're not allowed to fail after this function returns.  But we can
        # raise an exception to cancel the transaction for the other managers.
        pass

    def tpc_abort(self, transaction):
        return self.abort(transaction)

    def tpc_finish(self, transaction):
        for topic, msg in self.uncommitted:
            bodhi.log.debug("fedmsg sending %r" % topic)
            fedmsg.publish(topic=topic, msg=msg)
        self.committed = copy.copy(self.uncommitted)
        _managers_map.remove(self)

    def sortKey(self):
        return 'fedmsgdm' + str(id(self))

    def savepoint(self):
        return FedmsgSavepoint(self)


class FedmsgSavepoint(object):
    def __init__(self, dm):
        self.dm = dm
        self.saved_committed = copy.copy(self.dm.uncommitted)

    def rollback(self):
        self.dm.uncommitted = copy.copy(self.saved_committed)
