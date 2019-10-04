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
Define Bodhi's base classes for its message schemas.

Each message is defined as a Python class. For details, see `fedora-messaging
<https://fedora-messaging.readthedocs.io/en/stable/>`_ documentation on
messages.
"""

import json
import re
import typing

from fedora_messaging import message
from fedora_messaging.schema_utils import user_avatar_url

from bodhi import MENTION_RE


SCHEMA_URL = 'https://bodhi.fedoraproject.org/message-schemas'


class BodhiMessage(message.Message):
    """A base class for Bodhi messages."""

    @property
    def app_icon(self) -> str:
        """
        Return a URL that points to the application's icon.

        This is used when displaying the message to users.

        Returns:
            A URL for Bodhi's app icon.
        """
        return "https://apps.fedoraproject.org/img/icons/bodhi.png"

    @property
    def agent(self) -> typing.Union[str, None]:
        """Return the agent's username for this message.

        Returns:
            The agent's username, or None if the body has no agent key.
        """
        return self.body.get('agent', None)

    @property
    def agent_avatar(self) -> typing.Union[None, str]:
        """
        Return a URL to the avatar of the user who caused the action.

        Returns:
            The URL to the user's avatar, or None if username is None.
        """
        username = self.agent
        if username is None:
            return None
        return user_avatar_url(username)

    @classmethod
    def from_dict(cls, message: dict) -> 'BodhiMessage':
        """
        Generate a message based on the given message dictionary.

        Args:
            message: A dictionary representation of the message you wish to instantiate.
        Returns:
            A Message.
        """
        # Dirty, nasty hack that I feel shame for: use the fedmsg encoder that modifies
        # messages quietly if they have objects with __json__ methods on them.
        # For now, copy that behavior. In the future, callers should pass
        # fedora_messaging.api.Message sub-classes or this whole API should go away.
        body = json.loads(json.dumps(message, cls=FedMsgEncoder))

        return cls(body=body)

    @property
    def usernames(self) -> typing.List[str]:
        """
        List of users affected by the action that generated this message.

        Returns:
            A list of affected usernames.
        """
        users = []
        if self.agent is not None:
            users.append(self.agent)

        if 'comment' in self.body:
            text = self.body['comment']['text']
            mentions = re.findall(MENTION_RE, text)
            for mention in mentions:
                users.append(mention[1:])

        users = list(set(users))
        users.sort()
        return users

    @property
    def containers(self) -> typing.Iterable[str]:
        """
        List of containers affected by the action that generated this message.

        Returns:
            A list of affected container names.
        """
        return []

    @property
    def modules(self) -> typing.Iterable[str]:
        """
        List of modules affected by the action that generated this message.

        Returns:
            A list of affected module names.
        """
        return []

    @property
    def flatpaks(self) -> typing.Iterable[str]:
        """
        List of flatpaks affected by the action that generated this message.

        Returns:
            A list of affected flatpaks names.
        """
        return []


class BuildV1(typing.NamedTuple):
    """
    A model for referencing a Build.

    Attributes:
        nvr: The koji id of the build.
    """

    nvr: str

    @property
    def package(self) -> str:
        """Return the name of the package that this build is associated with."""
        return self.nvr.rsplit('-', 2)[0]

    @staticmethod
    def schema() -> dict:
        """Return a schema snippet for a Build."""
        return {
            'type': 'object',
            'description': 'A build',
            'properties': {
                'nvr': {
                    'type': 'string',
                    'description': 'The nvr the identifies the build in koji'
                },
            },
            'required': ['nvr']
        }


class ReleaseV1(typing.NamedTuple):
    """
    A model for referencing a Release.

    Attributes:
        name: The name of the release.
    """

    name: str

    @staticmethod
    def schema() -> dict:
        """Return a schema snippet for a Build."""
        return {
            'type': 'object',
            'description': 'A release',
            'properties': {
                'name': {
                    'type': 'string',
                    'description': 'The name of the release e.g. F32'
                },
            },
            'required': ['name']
        }


class UpdateV1(typing.NamedTuple):
    """
    A model for referencing an Update object.

    Attributes:
        alias: The alias of the update.
        builds: A list of builds associated with the update.
    """

    alias: str
    builds: typing.Iterable[BuildV1]
    user: 'UserV1'
    status: str
    request: typing.Union[None, str]
    release: 'ReleaseV1'

    @property
    def packages(self) -> typing.Iterable[str]:
        """Return a list of package names included in this update."""
        return [b.package for b in self.builds]

    @staticmethod
    def schema() -> dict:
        """Return a schema snippet for an Update."""
        return {
            'type': 'object',
            'description': 'An update',
            'properties': {
                'alias': {
                    'type': 'string',
                    'description': 'The alias of the update'
                },
                'builds': {
                    'type': 'array',
                    'description': 'A list of builds included in this update',
                    'items': {'$ref': '#/definitions/build'}
                },
                'release': ReleaseV1.schema(),
                'request': {
                    'type': ['null', 'string'],
                    'description': 'The request of the update, if any',
                    'enum': [None, 'testing', 'obsolete', 'unpush', 'revoke', 'stable']
                },
                'status': {
                    'type': 'string',
                    'description': 'The current status of the update',
                    'enum': [None, 'pending', 'testing', 'stable', 'unpushed', 'obsolete',
                             'side_tag_active', 'side_tag_expired']
                },
                'user': UserV1.schema(),
            },
            'required': ['alias', 'builds', 'release', 'request', 'status', 'user']
        }


class UserV1(typing.NamedTuple):
    """
    A model for referencing a User object.

    Attributes:
        name: The User's account name
    """

    name: str

    @staticmethod
    def schema() -> dict:
        """Return a schema snippet for a User."""
        return {
            'type': 'object',
            'description': 'The user that submitted the override',
            'properties': {
                'name': {
                    'type': 'string',
                    'description': "The user's account name"
                },
            },
            'required': ['name']
        }


class FedMsgEncoder(json.encoder.JSONEncoder):
    """Encoder with convenience support.

    If an object has a ``__json__()`` method, use it to serialize to JSON.
    """

    def default(self, obj):
        """Encode objects which don't have a more specific encoding method."""
        if hasattr(obj, "__json__"):
            return obj.__json__()
        return super().default(obj)
