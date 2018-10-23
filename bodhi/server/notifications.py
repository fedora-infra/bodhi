# -*- coding: utf-8 -*-
# Copyright 2014-2017 Red Hat, Inc.
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
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""A collection of fedmsg publishing utilities."""
import collections
import json
import logging
import socket

from sqlalchemy import event
import fedmsg
import fedmsg.config
import fedmsg.encoding

from bodhi.server import Session
import bodhi.server
import bodhi.server.config


_log = logging.getLogger(__name__)


def init(active=None, cert_prefix=None):
    """
    Initialize fedmsg for publishing.

    Args:
        active (bool or None): If True, publish messages to a relay. If False, publish messages to
            connected consumers.
        cert_prefix (basestring): Configures the ``cert_prefix`` setting in the fedmsg_config.
    """
    if not bodhi.server.config.config.get('fedmsg_enabled'):
        bodhi.server.log.warning("fedmsg disabled.  not initializing.")
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


@event.listens_for(Session, 'after_commit')
def send_fedmsgs_after_commit(session):
    """
    Send queued fedmsgs after a database commit.

    This relies on the session ``info`` dictionary being populated. At the moment,
    this is done by calling the :func:`publish` function. In the future it should
    be done automatically using SQLAlchemy listeners.

    Args:
        session (sqlalchemy.orm.session.Session): The session that was committed.
    """
    if 'fedmsg' in session.info:
        _log.debug('Emitting all queued fedmsgs for %r', session)
        # Initialize right before we try to publish, but only if we haven't
        # initialized for this thread already.
        if not fedmsg_is_initialized():
            init()

        for topic, messages in session.info['fedmsg'].items():
            _log.debug('emitting %d fedmsgs to the "%s" topic queued by %r',
                       len(messages), topic, session)
            for msg in messages:
                fedmsg.publish(topic=topic, msg=msg)
                _log.debug('Emitted a fedmsg, %r, on the "%s" topic, queued by %r',
                           msg, topic, session)
            # Tidy up after ourselves so a second call to commit on this session won't
            # send the same messages again. We cannot delete topic from fedmsg dict
            # because we cannot change dictionary size during iteration
            session.info['fedmsg'][topic] = []


def publish(topic, msg, force=False):
    """Publish a message to fedmsg.

    By default, messages are not sent immediately, but are queued in a
    transaction "data manager".  They will only get published after the
    sqlalchemy transaction completes successfully and will not be published at
    all if it fails, aborts, or rolls back.

    Specifying force=True to this function by-passes that -- messages are sent
    immediately.

    Args:
        topic (basestring): The message topic suffix.
        msg (dict): A dictionary representing the message to be published via fedmsg.
        force (bool): If True, send the message immediately. Else, queue the message to be sent
            after the current database transaction is committed.
    """
    if not bodhi.server.config.config.get('fedmsg_enabled'):
        _log.warning("fedmsg disabled.  not sending %r" % topic)
        return

    # Initialize right before we try to publish, but only if we haven't
    # initialized for this thread already.
    if not fedmsg_is_initialized():
        init()

    if force:
        _log.debug("fedmsg skipping transaction and sending %r" % topic)
        fedmsg.publish(topic=topic, msg=msg)
    else:
        # We need to do this to ensure all the SQLAlchemy objects that could be in the messages
        # are turned into JSON before the session is removed and expires the objects loaded with
        # it. The JSON is decoded again because the fedmsg API doesn't state it accepts strings.
        # An issue has been filed about this: https://github.com/fedora-infra/fedmsg/issues/407.
        json_msg = fedmsg.encoding.dumps(msg)
        msg_dict = json.loads(json_msg)
        # This gives us the thread-local session which we'll use to stash the fedmsg.
        # When commit is called on it, the :func:`send_fedmsgs_after_commit` is triggered.
        session = Session()
        if 'fedmsg' not in session.info:
            _log.debug('Adding a dictionary for fedmsg storage to %r', session)
            session.info['fedmsg'] = collections.defaultdict(list)
        session.info['fedmsg'][topic].append(msg_dict)
        _log.debug('Enqueuing a fedmsg, %r, for topic "%s" on %r', msg_dict, topic, session)


def fedmsg_is_initialized():
    """
    Return True or False if fedmsg is initialized or not.

    Returns:
        bool: Indicating if fedmsg is initialized.
    """
    local = getattr(fedmsg, '__local')
    if not hasattr(local, '__context'):
        return False
    # Ensure that fedmsg has an endpoint to publish to.
    context = getattr(local, '__context')
    return hasattr(context, 'publisher')
