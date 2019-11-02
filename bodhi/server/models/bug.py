# Copyright © 2011-2019 Red Hat, Inc. and others.
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
"""Bodhi's bug models."""

import typing

from sqlalchemy import Boolean, Column, Integer, Unicode, UnicodeText

from bodhi.server import bugs, log
from bodhi.server.config import config
from bodhi.server.models import Base, UpdateType, UpdateStatus, Update

if typing.TYPE_CHECKING:  # pragma: no cover
    import pyramid  # noqa: 401


class Bug(Base):
    """
    Represents a Bugzilla bug.

    Attributes:
        bug_id (int): The bug's id.
        title (str): The description of the bug.
        security (bool): True if the bug is marked as a security issue.
        url (str): The URL for the bug. Inaccessible due to being overridden by the url
            property (https://github.com/fedora-infra/bodhi/issues/1995).
        parent (bool): True if this is a parent tracker bug for release-specific bugs.
    """

    __tablename__ = 'bugs'
    __exclude_columns__ = ('id', 'updates')
    __get_by__ = ('bug_id',)

    # Bug number. If None, assume ``url`` points to an external bug tracker
    bug_id = Column(Integer, unique=True)

    # The title of the bug
    title = Column(Unicode(255))

    # If we're dealing with a security bug
    security = Column(Boolean, default=False)

    # Bug URL.  If None, then assume it's in Red Hat Bugzilla
    url = Column('url', UnicodeText)

    # If this bug is a parent tracker bug for release-specific bugs
    parent = Column(Boolean, default=False)

    @property
    def url(self) -> str:
        """
        Return a URL to the bug.

        Returns:
            The URL to this bug.
        """
        return config['buglink'] % self.bug_id

    def update_details(self, bug: typing.Optional['bugzilla.bug.Bug'] = None) -> None:
        """
        Grab details from rhbz to populate our bug fields.

        This is typically called "offline" in the UpdatesHandler task.

        Args:
            bug: The Bug to retrieve details from Bugzilla about. If
                 None, self.bug_id will be used to retrieve the bug. Defaults to None.
        """
        bugs.bugtracker.update_details(bug, self)

    def default_message(self, update: Update) -> str:
        """
        Return a default comment to add to a bug with add_comment().

        Args:
            update: The update that is related to the bug.
        Returns:
            The default comment to add to the bug related to the given update.
        """
        install_msg = (
            f'In short time you\'ll be able to install the update with the following '
            f'command:\n`{update.install_command}`') if update.install_command else ''
        msg_data = {'update_title': update.get_title(delim=", ", nvr=True),
                    'update_beauty_title': update.get_title(beautify=True, nvr=True),
                    'update_alias': update.alias,
                    'repo': f'{update.release.long_name} {update.status.description}',
                    'install_instructions': install_msg,
                    'update_url': f'{config.get("base_address")}{update.get_url()}'}

        if update.status is UpdateStatus.stable:
            message = config['stable_bug_msg'].format(**msg_data)
        elif update.status is UpdateStatus.testing:
            if update.release.id_prefix == "FEDORA-EPEL":
                if 'testing_bug_epel_msg' in config:
                    template = config['testing_bug_epel_msg']
                else:
                    template = config['testing_bug_msg']
                    log.warning("No 'testing_bug_epel_msg' found in the config.")
            else:
                template = config['testing_bug_msg']
            message = template.format(**msg_data)
        else:
            raise ValueError(f'Trying to post a default comment to a bug, but '
                             f'{update.alias} is not in Stable or Testing status.')

        return message

    def add_comment(self, update: Update, comment: typing.Optional[str] = None) -> None:
        """
        Add a comment to the bug, pertaining to the given update.

        Args:
            update: The update that is related to the bug.
            comment: The comment to add to the bug. If None, a default message
                is added to the bug. Defaults to None.
        """
        if update.type is UpdateType.security and self.parent \
                and update.status is not UpdateStatus.stable:
            log.debug('Not commenting on parent security bug %s', self.bug_id)
        else:
            if not comment:
                comment = self.default_message(update)
            log.debug("Adding comment to Bug #%d: %s" % (self.bug_id, comment))
            bugs.bugtracker.comment(self.bug_id, comment)

    def testing(self, update: Update) -> None:
        """
        Change the status of this bug to ON_QA.

        Also, comment on the bug with some details on how to test and provide feedback for the given
        update.

        Args:
            update: The update associated with the bug.
        """
        # Skip modifying Security Response bugs for testing updates
        if update.type is UpdateType.security and self.parent:
            log.debug('Not modifying parent security bug %s', self.bug_id)
        else:
            comment = self.default_message(update)
            bugs.bugtracker.on_qa(self.bug_id, comment)

    def close_bug(self, update: Update) -> None:
        """
        Close the bug.

        Args:
            update: The update associated with the bug.
        """
        # Build a mapping of package names to build versions
        # so that .close() can figure out which build version fixes which bug.
        versions = dict([
            (b.nvr_name, b.nvr) for b in update.builds
        ])
        bugs.bugtracker.close(self.bug_id, versions=versions, comment=self.default_message(update))

    def modified(self, update: Update, comment: str) -> None:
        """
        Change the status of this bug to MODIFIED unless it is a parent security bug.

        Also, comment on the bug stating that an update has been submitted.

        Args:
            update: The update that is associated with this bug.
            comment: A comment to leave on the bug when modifying it.
        """
        if update.type is UpdateType.security and self.parent:
            log.debug('Not modifying parent security bug %s', self.bug_id)
        else:
            bugs.bugtracker.modified(self.bug_id, comment)
