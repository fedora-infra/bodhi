# Copyright (C) 2018-2019 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""
Message schema for Errata.

Each message is defined as a Python class. For details, see `fedora-messaging
<https://fedora-messaging.readthedocs.io/en/stable/>`_ documentation on
messages.
"""

import typing

from .base import BodhiMessage, BuildV1, ReleaseV1, SCHEMA_URL, UpdateV1, UserV1


class ErrataPublishV1(BodhiMessage):
    """Sent when an errata is published."""

    body_schema = {
        'id': f'{SCHEMA_URL}/v1/bodhi.errata.publish#',
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'description': 'Schema for message sent when an update is pushed to stable',
        'type': 'object',
        'properties': {
            'body': {
                'type': 'string',
                'description': 'The body of an human readable message about the update',
            },
            'subject': {
                'type': 'string',
                'description': 'A short summary of the update'
            },
            'update': UpdateV1.schema(),
        },
        'required': ['body', 'subject', 'update'],
        'definitions': {
            'build': BuildV1.schema(),
        }
    }

    topic = "bodhi.errata.publish"

    def __str__(self) -> str:
        """
        Return a human-readable representation of this message.

        This should provide a detailed representation of the message, much like the body
        of an email.
        """
        return self.body['body']

    @property
    def agent(self) -> str:
        """Return the agent's username for this message.

        Returns:
            The agent's username.
        """
        return self.update.user.name

    @property
    def packages(self) -> typing.Iterable[str]:
        """List of package names affected by the action that generated this message.

        Returns:
            A list of affected package names.
        """
        return self.update.packages

    @property
    def summary(self) -> str:
        """
        Return a short, human-readable representation of this message.

        This should provide a short summary of the message, much like the subject line
        of an email.
        """
        return self.body['subject']

    @property
    def url(self) -> str:
        """
        Return a URL to the action that caused this message to be emitted.

        Returns:
            A relevant URL.
        """
        return f'https://bodhi.fedoraproject.org/updates/{self.update.alias}'

    @property
    def update(self) -> UpdateV1:
        """Return the Update from this errata."""
        if not hasattr(self, '_update'):
            # Let's cache the Update since a few different methods use it.
            self._update = UpdateV1(
                self.body['update']['alias'],
                [BuildV1(b['nvr']) for b in self.body['update']['builds']],
                UserV1(self.body['update']['user']['name']), self.body['update']['status'],
                self.body['update']['request'], ReleaseV1(self.body['update']['release']['name']))
        return self._update
