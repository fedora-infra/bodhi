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
Message schema for Updates.

Each message is defined as a Python class. For details, see `fedora-messaging
<https://fedora-messaging.readthedocs.io/en/stable/>`_ documentation on
messages.
"""

import typing

from .base import BodhiMessage, BuildV1, SCHEMA_URL, UpdateV1, UserV1
from ..utils import truncate


class UpdateMessage(BodhiMessage):
    """Base class for update messages."""

    @property
    def url(self) -> str:
        """
        Return a URL to the action that caused this message to be emitted.

        Returns:
            A relevant URL.
        """
        return f"https://bodhi.fedoraproject.org/updates/{self.update.alias}"

    @property
    def update(self) -> UpdateV1:
        """Return the Update referenced by this message."""
        # Many things use this object, so let's cache it so we don't construct it repeatedly.
        if not hasattr(self, '_update_obj'):
            self._update_obj = UpdateV1(
                self._update['alias'], [BuildV1(b['nvr']) for b in self._update['builds']],
                UserV1(self._update['user']['name']), self._update['status'],
                self._update['request'])
        return self._update_obj

    @property
    def usernames(self) -> typing.List[str]:
        """
        List of users affected by the action that generated this message.

        Returns:
            A list of affected usernames.
        """
        usernames = super(UpdateMessage, self).usernames
        # Add the submitter if there is one
        if self.update.user.name not in usernames:
            usernames.append(self.update.user.name)
        usernames.sort()
        return usernames

    @property
    def packages(self) -> typing.Iterable[str]:
        """
        List of names of packages affected by the action that generated this message.

        Returns:
            A list of affected package names.
        """
        return self.update.packages

    @property
    def _update(self) -> dict:
        """Return a dictionary from the body representing an update."""
        return self.body['update']


class UpdateCommentV1(UpdateMessage):
    """Sent when a comment is made on an update."""

    body_schema = {
        'id': f'{SCHEMA_URL}/v1/bodhi.update.comment#',
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'description': 'Schema for message sent when a comment is added to an update',
        'type': 'object',
        'properties': {
            'comment': {
                'type': 'object',
                'description': 'The comment added to an update',
                'properties': {
                    'karma': {
                        'type': 'integer',
                        'description': 'The karma associated with the comment',
                    },
                    'text': {
                        'type': 'string',
                        'description': 'The text of the comment',
                    },
                    'timestamp': {
                        'type': 'string',
                        'description': 'The timestamp that the comment was left on.'
                    },
                    'update': UpdateV1.schema(),
                    'user': UserV1.schema(),
                },
                'required': ['karma', 'text', 'timestamp', 'update', 'user'],
            },
        },
        'required': ['comment'],
        'definitions': {
            'build': BuildV1.schema(),
        }
    }

    topic = "bodhi.update.comment"

    def __str__(self) -> str:
        """
        Return a human-readable representation of this message.

        This should provide a detailed representation of the message, much like the body
        of an email.

        Returns:
            A human readable representation of this message.
        """
        return self.body['comment']['text']

    @property
    def karma(self) -> int:
        """Return the karma from this comment."""
        return self.body['comment']['karma']

    @property
    def summary(self) -> str:
        """
        Return a short, human-readable representation of this message.

        This should provide a short summary of the message, much like the subject line
        of an email.

        Returns:
            A summary for this message.
        """
        return (f"{self.user.name} commented on bodhi update {self.update.alias} "
                f"(karma: {self.karma})")

    @property
    def agent(self) -> str:
        """
        Return the agent's username for this message.

        Returns:
            The agent's username.
        """
        return self.user.name

    @property
    def user(self) -> UserV1:
        """Return the user who wrote this comment."""
        return UserV1(self.body['comment']['user']['name'])

    @property
    def _update(self) -> dict:
        """Return a dictionary from the body representing an update."""
        return self.body['comment']['update']


class UpdateCompleteStableV1(UpdateMessage):
    """Sent when an update is available in the stable repository."""

    body_schema = {
        'id': f'{SCHEMA_URL}/v1/bodhi.update.complete.stable#',
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'description': 'Schema for message sent when an update is pushed stable',
        'type': 'object',
        'properties': {
            'update': UpdateV1.schema(),
        },
        'required': ['update'],
        'definitions': {
            'build': BuildV1.schema(),
        }
    }

    topic = "bodhi.update.complete.stable"

    @property
    def summary(self) -> str:
        """
        Return a short, human-readable representation of this message.

        This should provide a short summary of the message, much like the subject line
        of an email.

        Returns:
            A summary for this message.
        """
        return (
            f"{self.update.user.name}'s {truncate(' '.join([b.nvr for b in self.update.builds]))} "
            f"bodhi update completed push to {self.update.status}")


class UpdateCompleteTestingV1(UpdateMessage):
    """Sent when an update is available in the testing repository."""

    body_schema = {
        'id': f'{SCHEMA_URL}/v1/bodhi.update.complete.testing#',
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'description': 'Schema for message sent when an update is pushed to testing',
        'type': 'object',
        'properties': {
            'update': UpdateV1.schema(),
        },
        'required': ['update'],
        'definitions': {
            'build': BuildV1.schema(),
        }
    }

    topic = "bodhi.update.complete.testing"

    @property
    def summary(self) -> str:
        """
        Return a short, human-readable representation of this message.

        This should provide a short summary of the message, much like the subject line
        of an email.

        Returns:
            A summary for this message.
        """
        return (
            f"{self.update.user.name}'s {truncate(' '.join([b.nvr for b in self.update.builds]))} "
            f"bodhi update completed push to {self.update.status}")


class UpdateEditV1(UpdateMessage):
    """Sent when an update is edited."""

    body_schema = {
        'id': f'{SCHEMA_URL}/v1/bodhi.update.edit#',
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'description': 'Schema for message sent when an update is edited',
        'type': 'object',
        'properties': {
            'agent': {
                'type': 'string',
                'description': 'The user who edited the update',
            },
            'new_bugs': {
                'type': 'array',
                'description': 'An array of bug ids that have been added to the update',
                'items': {
                    'type': 'integer',
                    'description': 'A Bugzilla bug ID'
                }
            },
            'update': UpdateV1.schema(),
        },
        'required': ['agent', 'new_bugs', 'update'],
        'definitions': {
            'build': BuildV1.schema(),
        }
    }

    topic = "bodhi.update.edit"

    @property
    def new_bugs(self) -> typing.Iterable[int]:
        """
        Return an iterable of the new bugs that have been added to the update.

        Returns:
            A list of Bugzilla bug IDs.
        """
        return self.body['new_bugs']

    @property
    def summary(self) -> str:
        """
        Return a short, human-readable representation of this message.

        This should provide a short summary of the message, much like the subject line
        of an email.

        Returns:
            A summary for this message.
        """
        return f"{self.agent} edited {self.update.alias}"


class UpdateEjectV1(UpdateMessage):
    """Sent when an update is ejected from the push."""

    body_schema = {
        'id': f'{SCHEMA_URL}/v1/bodhi.update.eject#',
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'description': 'Schema for message sent when an update is ejected from a compose',
        'type': 'object',
        'properties': {
            'reason': {
                'type': 'string',
                'description': 'The reason the update was ejected',
            },
            'repo': {
                'type': 'string',
                'description': 'The name of the repo that the update is associated with'
            },
            'update': UpdateV1.schema(),
        },
        'required': ['reason', 'repo', 'update'],
        'definitions': {
            'build': BuildV1.schema(),
        }
    }

    topic = "bodhi.update.eject"

    @property
    def reason(self) -> str:
        """Return the reason this update was ejected from the compose."""
        return self.body['reason']

    @property
    def repo(self) -> str:
        """Return the name of the repository that this update is associated with."""
        return self.body['repo']

    @property
    def summary(self) -> str:
        """
        Return a short, human-readable representation of this message.

        This should provide a short summary of the message, much like the subject line
        of an email.

        Returns:
            A summary for this message.
        """
        return (
            f"{self.update.user.name}'s {truncate(' '.join([b.nvr for b in self.update.builds]))} "
            f"bodhi update was ejected from the {self.repo} mash. Reason: \"{self.reason}\"")


class UpdateKarmaThresholdV1(UpdateMessage):
    """Sent when an update reaches its karma threshold."""

    body_schema = {
        'id': f'{SCHEMA_URL}/v1/bodhi.update.karma.threshold.reach#',
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'description': 'Schema for message sent when an update reaches its karma threshold',
        'type': 'object',
        'properties': {
            'status': {
                'type': 'string',
                'description': 'Which karma threshold was reached',
                'enum': ['stable', 'unstable']
            },
            'update': UpdateV1.schema(),
        },
        'required': ['status', 'update'],
        'definitions': {
            'build': BuildV1.schema(),
        }
    }

    topic = "bodhi.update.karma.threshold.reach"

    @property
    def status(self) -> str:
        """Return the threshold that was reached."""
        return self.body['status']

    @property
    def summary(self) -> str:
        """
        Return a short, human-readable representation of this message.

        This should provide a short summary of the message, much like the subject line
        of an email.

        Returns:
            A summary for this message.
        """
        return f"{self.update.alias} reached the {self.status} karma threshold"


class UpdateRequestMessage(UpdateMessage):
    """Sent when an update's request is changed."""

    @property
    def summary(self) -> str:
        """
        Return a short, human-readable representation of this message.

        This should provide a short summary of the message, much like the subject line
        of an email.

        Returns:
            A summary for this message.
        """
        status = self.topic.split('.')[-1]
        if status in ('unpush', 'obsolete', 'revoke'):
            # make our status past-tense
            status = status + (status[-1] == 'e' and 'd' or 'ed')
            return f"{self.agent} {status} {self.update.alias}"
        else:
            return f"{self.agent} submitted {self.update.alias} to {status}"


class UpdateRequestRevokeV1(UpdateRequestMessage):
    """Sent when an update is revoked."""

    body_schema = {
        'id': f'{SCHEMA_URL}/v1/bodhi.update.request.revoke#',
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'description': 'Schema for message sent when an update is revoked',
        'type': 'object',
        'properties': {
            'agent': {
                'type': 'string',
                'description': 'The user who requested the update to be revoked',
            },
            'update': UpdateV1.schema(),
        },
        'required': ['agent', 'update'],
        'definitions': {
            'build': BuildV1.schema(),
        }
    }

    topic = "bodhi.update.request.revoke"


class UpdateRequestStableV1(UpdateRequestMessage):
    """Sent when an update is submitted as a stable candidate."""

    body_schema = {
        'id': f'{SCHEMA_URL}/v1/bodhi.update.request.stable#',
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'description': 'Schema for message sent when an update is requested stable',
        'type': 'object',
        'properties': {
            'agent': {
                'type': 'string',
                'description': 'The user who requested the update to be stable',
            },
            'update': UpdateV1.schema(),
        },
        'required': ['agent', 'update'],
        'definitions': {
            'build': BuildV1.schema(),
        }
    }

    topic = "bodhi.update.request.stable"


class UpdateRequestTestingV1(UpdateRequestMessage):
    """Sent when an update is submitted as a testing candidate."""

    body_schema = {
        'id': f'{SCHEMA_URL}/v1/bodhi.update.request.testing#',
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'description': 'Schema for message sent when an update is requested testing',
        'type': 'object',
        'properties': {
            'agent': {
                'type': 'string',
                'description': 'The user who requested the update to be tested',
            },
            'update': UpdateV1.schema(),
        },
        'required': ['agent', 'update'],
        'definitions': {
            'build': BuildV1.schema(),
        }
    }

    topic = "bodhi.update.request.testing"


class UpdateRequestUnpushV1(UpdateRequestMessage):
    """Sent when an update is requested to be unpushed."""

    body_schema = {
        'id': f'{SCHEMA_URL}/v1/bodhi.update.request.unpush#',
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'description': 'Schema for message sent when an update is unpushed',
        'type': 'object',
        'properties': {
            'agent': {
                'type': 'string',
                'description': 'The user who requested the update to be unpushed',
            },
            'update': UpdateV1.schema(),
        },
        'required': ['agent', 'update'],
        'definitions': {
            'build': BuildV1.schema(),
        }
    }

    topic = "bodhi.update.request.unpush"


class UpdateRequestObsoleteV1(UpdateRequestMessage):
    """Sent when an update is requested to be obsoleted."""

    body_schema = {
        'id': f'{SCHEMA_URL}/v1/bodhi.update.request.obsolete#',
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'description': 'Schema for message sent when an update is obsoleted',
        'type': 'object',
        'properties': {
            'agent': {
                'type': 'string',
                'description': 'The user who requested the update to be obsoleted',
            },
            'update': UpdateV1.schema(),
        },
        'required': ['agent', 'update'],
        'definitions': {
            'build': BuildV1.schema(),
        }
    }

    topic = "bodhi.update.request.obsolete"


class UpdateRequirementsMetStableV1(UpdateMessage):
    """Sent when all the update requirements are meant for stable."""

    body_schema = {
        'id': f'{SCHEMA_URL}/v1/bodhi.update.requirements_met.stable#',
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'description': 'Schema for message sent when an update meets stable requirements',
        'type': 'object',
        'properties': {
            'update': UpdateV1.schema(),
        },
        'required': ['update'],
        'definitions': {
            'build': BuildV1.schema(),
        }
    }

    topic = "bodhi.update.requirements_met.stable"

    @property
    def summary(self) -> str:
        """
        Return a short, human-readable representation of this message.

        This should provide a short summary of the message, much like the subject line
        of an email.

        Returns:
            A summary for this message.
        """
        return f'{self.update.alias} has met stable testing requirements'


class UpdateReadyForTestingV1(UpdateMessage):
    """Sent when an update is ready to be tested."""

    body_schema = {
        'id': f'{SCHEMA_URL}/v1/bodhi.update.status.testing#',
        '$schema': 'http://json-schema.org/draft-04/schema#',
        'description': 'Schema for message sent when an update is ready for testing',
        'type': 'object',
        'properties': {
            'update': UpdateV1.schema(),
        },
        'required': ['update'],
        'definitions': {
            'build': BuildV1.schema(),
        },
        're-trigger': {
            'type': 'bool',
            'description': 'This flag is True if the message is sent to re-trigger tests'
        }
    }

    topic = "bodhi.update.status.testing"

    @property
    def summary(self) -> str:
        """
        Return a short, human-readable representation of this message.

        This should provide a short summary of the message, much like the subject line
        of an email.

        Returns:
            A summary for this message.
        """
        return (
            f"{self.update.user.name}'s "
            f"{truncate(' '.join([b.nvr for b in self.update.builds]))} "
            f"bodhi update is ready for {self.update.status}")
