# Copyright (C) 2018-2019  Red Hat, Inc.
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
Message schema for Bodhi's composer messages.

Each message is defined as a Python class. For details, see `fedora-messaging
<https://fedora-messaging.readthedocs.io/en/stable/>`_ documentation on
messages.
"""

import typing

from .base import BodhiMessage, SCHEMA_URL


class ComposeV1(typing.NamedTuple):
    """
    A model for referencing a Compose object.

    Attributes:
        security: True if this compose contains security updates.
        release_id: The database id of the release we are composing.
        request: The request of the release we are composing.
        content_type: The content type of the builds in this compose.
    """

    release_id: int
    request: str
    content_type: str
    security: bool

    @staticmethod
    def schema() -> dict:
        """Return a schema snippet for a Compose object."""
        return {
            'type': 'object',
            'description': 'A compose being requested',
            'properties': {
                'content_type': {
                    'type': 'string',
                    'description': 'The content type of this compose'
                },
                'release_id': {
                    'type': 'integer',
                    'description': 'The database ID for the release being requested'
                },
                'request': {
                    'type': 'string',
                    'description': 'The request being requested'
                },
                'security': {
                    'type': 'boolean',
                    'description': 'true if this compose contains security updates'
                },
            },
            'required': ['content_type', 'release_id', 'request', 'security']
        }


class ComposerStartV1(BodhiMessage):
    """Sent when a compose begins."""

    body_schema = {
        'id': f'{SCHEMA_URL}/v1/bodhi.composer.start#',
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'description': 'Schema for message sent when a compose is requested to start',
        'type': 'object',
        'properties': {
            'agent': {
                'type': 'string',
                'description': 'The name of the user who started this compose.'
            },
            'composes': {
                'type': 'array',
                'description': 'A list of composes included in this compose job',
                'items': {'$ref': '#/definitions/compose'}
            },
            'resume': {
                'type': 'boolean',
                'description': 'true if this is a request to resume the given composes'
            }
        },
        'required': ['agent', 'composes', 'resume'],
        'definitions': {
            'compose': ComposeV1.schema(),
        }
    }

    topic = "bodhi.composer.start"

    @property
    def composes(self) -> typing.List[ComposeV1]:
        """Return a list of the composes included in this request."""
        return [ComposeV1(c['release_id'], c['request'], c['content_type'], c['security'])
                for c in self.body['composes']]

    @property
    def resume(self) -> bool:
        """Return True if this is a request to resume the composes."""
        return self.body['resume']

    @property
    def summary(self) -> str:
        """
        Return a short, human-readable representation of this message.

        This should provide a short summary of the message, much like the subject line
        of an email.
        """
        return f"{self.agent} requested a compose of {len(self.composes)} repositories"
