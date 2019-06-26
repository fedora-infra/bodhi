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
Message schema for Composes.

Each message is defined as a Python class. For details, see `fedora-messaging
<https://fedora-messaging.readthedocs.io/en/stable/>`_ documentation on
messages.
"""

from .base import BodhiMessage, SCHEMA_URL


class ComposeCompleteV1(BodhiMessage):
    """Sent when a compose task completes."""

    body_schema = {
        'id': f'{SCHEMA_URL}/v1/bodhi.compose.complete#',
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'description': 'Schema for message sent when composes finish',
        'type': 'object',
        'properties': {
            'agent': {
                'type': 'string',
                'description': 'The name of the user who started this compose.'
            },
            'repo': {
                'type': 'string',
                'description': 'The name of the repository being composed.'
            },
            'success': {
                'type': 'boolean',
                'description': 'true if the compose was successful, false otherwise.'
            },
            'ctype': {
                'type': 'string',
                'description': 'Type of the compose.'
            }
        },
        'required': ['agent', 'repo', 'success'],
    }

    topic = "bodhi.compose.complete"

    @property
    def repo(self) -> str:
        """Return the name of the repository being composed."""
        return self.body.get('repo')

    @property
    def success(self) -> bool:
        """Return the name of the repository being composed."""
        return self.body.get('success')

    @property
    def ctype(self) -> str:
        """Return the compose type."""
        return self.body.get('ctype')

    @property
    def summary(self) -> str:
        """
        Return a short, human-readable representation of this message.

        This should provide a short summary of the message, much like the subject line
        of an email.

        Returns:
            The message summary.
        """
        if self.success:
            return f"bodhi composer successfully composed {self.repo}"
        else:
            return f"bodhi composer failed to compose {self.repo}"


class ComposeComposingV1(BodhiMessage):
    """Sent when the compose task composes."""

    body_schema = {
        'id': f'{SCHEMA_URL}/v1/bodhi.compose.composing#',
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'description': 'Schema for message sent when composes start',
        'type': 'object',
        'properties': {
            'agent': {
                'type': 'string',
                'description': 'The name of the user who started this compose.'
            },
            'repo': {
                'type': 'string',
                'description': 'The name of the repository being composed.'
            },
        },
        'required': ['agent', 'repo'],
    }

    topic = "bodhi.compose.composing"

    @property
    def repo(self) -> str:
        """Return the name of the repository being composed."""
        return self.body.get('repo')

    @property
    def summary(self) -> str:
        """
        Return a short, human-readable representation of this message.

        This should provide a short summary of the message, much like the subject line
        of an email.

        Returns:
            A summary for this message.
        """
        return f"bodhi composer started composing {self.repo}"


class ComposeStartV1(BodhiMessage):
    """Sent when a compose task starts."""

    body_schema = {
        'id': f'{SCHEMA_URL}/v1/bodhi.compose.start#',
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'description': 'Schema for message sent when composes start',
        'type': 'object',
        'properties': {
            'agent': {
                'type': 'string',
                'description': 'The name of the user who started this compose.'
            },
        },
        'required': ['agent'],
    }

    topic = "bodhi.compose.start"

    @property
    def summary(self) -> str:
        """
        Return a short, human-readable representation of this message.

        This should provide a short summary of the message, much like the subject line
        of an email.

        Returns:
            A summary for this message.
        """
        return "bodhi composer started a push"


class ComposeSyncDoneV1(BodhiMessage):
    """Sent when a compose task sync is done."""

    body_schema = {
        'id': f'{SCHEMA_URL}/v1/bodhi.compose.sync.done#',
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'description': ('Schema for message sent when the composer is done waiting to sync to '
                        'mirrors'),
        'type': 'object',
        'properties': {
            'agent': {
                'type': 'string',
                'description': 'The name of the user who started this compose.'
            },
            'repo': {
                'type': 'string',
                'description': 'The name of the repository being composed.'
            },
        },
        'required': ['agent', 'repo'],
    }

    topic = "bodhi.compose.sync.done"

    @property
    def repo(self) -> str:
        """Return the name of the repository being composed."""
        return self.body.get('repo')

    @property
    def summary(self) -> str:
        """
        Return a short, human-readable representation of this message.

        This should provide a short summary of the message, much like the subject line
        of an email.

        Returns:
            A summary for this message.
        """
        return f"bodhi composer finished waiting for {self.repo} to hit the master mirror"


class ComposeSyncWaitV1(BodhiMessage):
    """Sent when a compose task sync is waiting."""

    body_schema = {
        'id': f'{SCHEMA_URL}/v1/bodhi.compose.sync.wait#',
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'description': 'Schema for message sent when the composer is waiting to sync to mirrors',
        'type': 'object',
        'properties': {
            'agent': {
                'type': 'string',
                'description': 'The name of the user who started this compose.'
            },
            'repo': {
                'type': 'string',
                'description': 'The name of the repository being composed.'
            },
        },
        'required': ['agent', 'repo'],
    }

    topic = "bodhi.compose.sync.wait"

    @property
    def repo(self) -> str:
        """Return the name of the repository being composed."""
        return self.body.get('repo')

    @property
    def summary(self) -> str:
        """
        Return a short, human-readable representation of this message.

        This should provide a short summary of the message, much like the subject line
        of an email.

        Returns:
            A summary for this message.
        """
        return f"bodhi composer is waiting for {self.repo} to hit the master mirror"


class RepoDoneV1(BodhiMessage):
    """Sent when a repo is created and ready to be signed or otherwise processed."""

    body_schema = {
        'id': f'{SCHEMA_URL}/v1/bodhi.repo.done#',
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'description': 'Schema for message sent when a repo is created and ready to be signed',
        'type': 'object',
        'properties': {
            'agent': {
                'type': 'string',
                'description': 'The name of the user who started this compose.'
            },
            'path': {
                'type': 'string',
                'description': 'The path of the repository that was composed.'
            },
            'repo': {
                'type': 'string',
                'description': 'The name of the repository that was composed.'
            },
        },
        'required': ['agent', 'path', 'repo'],
    }

    topic = "bodhi.repo.done"

    @property
    def repo(self) -> str:
        """Return the name of the repository being composed."""
        return self.body.get('repo')

    @property
    def summary(self) -> str:
        """
        Return a short, human-readable representation of this message.

        This should provide a short summary of the message, much like the subject line
        of an email.

        Returns:
            A summary for this message.
        """
        return f"bodhi composer is finished building {self.repo}"
