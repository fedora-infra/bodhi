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
Message schema for Buildroot Overrides.

Each message is defined as a Python class. For details, see `fedora-messaging
<https://fedora-messaging.readthedocs.io/en/stable/>`_ documentation on
messages.
"""

import typing

from .base import BodhiMessage, BuildV1, SCHEMA_URL, UserV1


class BuildrootOverrideMessage(BodhiMessage):
    """Base class for the buildroot_override messages."""

    @property
    def build(self) -> BuildV1:
        """Return the build that was overridden."""
        return BuildV1(self.body['override']['nvr'])

    @property
    def submitter(self) -> UserV1:
        """Return the name of the submitter for the override."""
        return UserV1(self.body['override']['submitter']['name'])

    @property
    def summary(self) -> str:
        """
        Return a short, human-readable representation of this message.

        This should provide a short summary of the message, much like the subject line
        of an email.
        """
        return self._summary_tmpl.format(submitter=self.submitter.name, build=self.build.nvr)

    @property
    def url(self) -> str:
        """
        Return a URL to the action that caused this message to be emitted.

        Returns:
            A relevant URL.
        """
        return f"https://bodhi.fedoraproject.org/overrides/{self.build.nvr}"

    @property
    def packages(self) -> typing.Iterable[str]:
        """List of packages affected by the action that generated this message.

        Returns:
            A list of affected package names.
        """
        return [self.build.package]

    @property
    def agent(self) -> str:
        """Return the agent's username for this message.

        Returns:
            The agent's username.
        """
        return self.submitter.name

    @property
    def usernames(self) -> typing.List[str]:
        """
        List of users affected by the action that generated this message.

        Returns:
            A list of affected usernames.
        """
        return [self.agent]


class BuildrootOverrideTagV1(BuildrootOverrideMessage):
    """Sent when a buildroot override is added and tagged into the build root."""

    body_schema = {
        'id': f'{SCHEMA_URL}/v1/bodhi.buildroot_override.tag#',
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'description': 'Schema for message sent when buildroot overrides are tagged',
        'type': 'object',
        'properties': {
            'override': {
                'type': 'object',
                'properties': {
                    'nvr': {
                        'type': 'string',
                        'description': 'The NVR of the build that was overridden'
                    },
                    'submitter': UserV1.schema(),
                },
                'required': ['nvr', 'submitter']
            }
        },
        'required': ['override'],
    }

    topic = "bodhi.buildroot_override.tag"
    _summary_tmpl = "{submitter} submitted a buildroot override for {build}"


class BuildrootOverrideUntagV1(BuildrootOverrideMessage):
    """Sent when a buildroot override is untagged from the build root."""

    body_schema = {
        'id': f'{SCHEMA_URL}/v1/bodhi.buildroot_override.untag#',
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'description': 'Schema for message sent when buildroot overrides are untagged',
        'type': 'object',
        'properties': {
            'override': {
                'type': 'object',
                'properties': {
                    'nvr': {
                        'type': 'string',
                        'description': 'The NVR of the build that had been overridden'
                    },
                    'submitter': UserV1.schema(),
                },
                'required': ['nvr', 'submitter']
            }
        },
        'required': ['override'],
    }

    topic = "bodhi.buildroot_override.untag"
    _summary_tmpl = "{submitter} expired a buildroot override for {build}"
