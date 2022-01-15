# Copyright © 2013-2019 Red Hat, Inc. and others.
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
"""Defines utilities for accessing Bugzilla."""

from collections import namedtuple
from xmlrpc import client as xmlrpc_client
import logging
import typing

import bugzilla

from bodhi.server.config import config

if typing.TYPE_CHECKING:  # pragma: no cover
    from bodhi.server import models  # noqa: 401


bugtracker: typing.Union['Bugzilla', 'FakeBugTracker', None] = None
log = logging.getLogger('bodhi')
FakeBug = namedtuple('FakeBug', ['bug_id'])


class FakeBugTracker(object):
    """Provide an API similar to bugzilla.base.Bugzilla without doing anything."""

    def getbug(self, bug_id: typing.Union[str, int], *args, **kw) -> FakeBug:
        """
        Return a FakeBug representing the requested bug id.

        Args:
            bug_id: The requested bug id.
            args: Unused.
            kwargs: Unused.
        """
        return FakeBug(bug_id=int(bug_id))

    def __noop__(self, *args, **kw) -> None:
        """
        Log the method call at debug.

        Args:
            args: The list of args passed to the method.
            kwargs: The kwargs passed to the method.
        """
        log.debug('__noop__(%s)' % str(args))

    comment = update_details = modified = close = on_qa = __noop__


class InvalidComment(Exception):
    """Exception thrown when the comment posted is invalid (for example too long)."""


class Bugzilla(object):
    """Provide methods for Bodhi's frequent Bugzilla operations."""

    def __init__(self) -> None:
        """Initialize self._bz as None."""
        self._bz = None

    def _connect(self) -> None:
        """Create a Bugzilla client instance and store it on self._bz."""
        user = config.get('bodhi_email')
        password = config.get('bodhi_password')
        url = config.get("bz_server")
        log.info("Using BZ URL %s" % url)
        if config['bugzilla_api_key']:
            self._bz = bugzilla.Bugzilla(url=url, api_key=config.get('bugzilla_api_key'),
                                         cookiefile=None, tokenfile=None)
        elif user and password:
            self._bz = bugzilla.Bugzilla(url=url,
                                         user=user, password=password,
                                         cookiefile=None, tokenfile=None)
        else:
            self._bz = bugzilla.Bugzilla(url=url,
                                         cookiefile=None, tokenfile=None)

    @property
    def bz(self) -> bugzilla.Bugzilla:
        """
        Ensure we have connected to Bugzilla and return the client instance.

        Returns:
            A client Bugzilla instance.
        """
        if self._bz is None:
            self._connect()
        return self._bz

    def getbug(self, bug_id: int) -> 'bugzilla.bug.Bug':
        """
        Retrieve a bug from Bugzilla.

        Args:
            bug_id: The id of the bug you wish to retrieve.
        Returns:
            A Bug instance representing the bug in Bugzilla.
        """
        return self.bz.getbug(bug_id)

    def comment(self, bug_id: int, comment: str) -> None:
        """
        Add a comment to the given bug.

        Args:
            bug_id: The id of the bug you wish to comment on.
            comment: The comment to add to the bug.
        """
        try:
            if len(comment) > 65535:
                raise InvalidComment(f"Comment is too long: {comment}")
            bug = self.bz.getbug(bug_id)
            attempts = 0
            while attempts < 5:
                try:
                    bug.addcomment(comment)
                    break
                except xmlrpc_client.Fault as e:
                    attempts += 1
                    log.error(
                        f"\nA fault has occurred \nFault code: {e.faultCode}"
                        f" \nFault string: {e.faultString}"
                    )
        except InvalidComment:
            log.error(
                "Comment too long for bug #%d:  %s" % (bug_id, comment))
        except xmlrpc_client.Fault as err:
            if err.faultCode == 102:
                log.info('Cannot retrieve private bug #%d.', bug_id)
            else:
                log.exception(
                    "Got fault from Bugzilla on #%d: fault code: %d, fault string: %s",
                    bug_id, err.faultCode, err.faultString)
        except Exception:
            log.exception("Unable to add comment to bug #%d" % bug_id)

    def on_qa(self, bug_id: int, comment: str) -> None:
        """
        Change the status of this bug to ON_QA if it is not already ON_QA, VERIFIED, or CLOSED.

        This method will only operate on bugs that are associated with products listed
        in the bz_products setting.

        This will also comment on the bug with some details on how to test and provide feedback for
        this update.

        Args:
            bug_id: The bug id you wish to set to ON_QA.
            comment: The comment to be included with the state change.
        """
        try:
            bug = self.bz.getbug(bug_id)
            if bug.product not in config.get('bz_products'):
                log.info("Skipping set on_qa on {0!r} bug #{1}".format(bug.product, bug_id))
                return
            if bug.bug_status not in ('ON_QA', 'VERIFIED', 'CLOSED'):
                log.debug("Setting Bug #%d to ON_QA" % bug_id)
                bug.setstatus('ON_QA', comment=comment)
            else:
                bug.addcomment(comment)
        except xmlrpc_client.Fault as err:
            if err.faultCode == 102:
                log.info('Cannot retrieve private bug #%d.', bug_id)
            else:
                log.exception(
                    "Got fault from Bugzilla on #%d: fault code: %d, fault string: %s",
                    bug_id, err.faultCode, err.faultString)
        except Exception:
            log.exception("Unable to alter bug #%d" % bug_id)

    def close(self, bug_id: int, versions: typing.Mapping[str, str], comment: str) -> None:
        """
        Close the bug given by bug_id, mark it as fixed in the given versions, and add a comment.

        This method will only operate on bugs that are associated with products listed
        in the bz_products setting.

        Args:
            bug_id: The ID of the bug you wish to close.
            versions: A mapping of package names to nvrs of those packages that close the bug.
            comment: A comment to leave on the bug when closing it.
        """
        args = {'comment': comment}
        try:
            bug = self.bz.getbug(bug_id)
            if bug.product not in config.get('bz_products'):
                log.info("Skipping set closed on {0!r} bug #{1}".format(bug.product, bug_id))
                return
            # If this bug is for one of these builds...
            if bug.component in versions:
                version = versions[bug.component]
                # Get the existing list
                fixedin = [v.strip() for v in bug.fixed_in.split()]
                # Strip out any empty strings (already stripped)
                fixedin = [v for v in fixedin if v]

                # There are Red Hat preferences to how this field should be
                # structured.  We should use:
                # - the full NVR as it appears in koji
                # - space-separated if there's more than one.
                fixedin_str = " ".join(fixedin)

                # Add our build if its not already there
                # but only if resultant string length is lower than 256 chars
                # See https://github.com/fedora-infra/bodhi/issues/1430
                if (version not in fixedin) and ((len(fixedin_str) + len(version)) < 255):
                    args['fixedin'] = " ".join([fixedin_str, version]).strip()

            bug.close('ERRATA', **args)
        except xmlrpc_client.Fault as err:
            if err.faultCode == 102:
                log.info('Cannot retrieve private bug #%d.', bug_id)
            else:
                log.exception(
                    "Got fault from Bugzilla on #%d: fault code: %d, fault string: %s",
                    bug_id, err.faultCode, err.faultString)

    def update_details(self, bug: typing.Union['bugzilla.bug.Bug', None],
                       bug_entity: 'models.Bug') -> None:
        """
        Update the details on bug_entity to match what is found in Bugzilla.

        Args:
            bug: The Bugzilla Bug we will use to update our own Bug object from. If None,
                 bug_entity.bug_id will be used to fetch the object from Bugzilla.
            bug_entity: The bug we wish to update.
        """
        if not bug:
            try:
                bug = self.bz.getbug(bug_entity.bug_id)
            except xmlrpc_client.Fault as err:
                if err.faultCode == 102:
                    log.info('Cannot retrieve private bug #%d.', bug_entity.bug_id)
                    bug_entity.title = 'Private bug'
                else:
                    log.exception(
                        "Got fault from Bugzilla on #%d: fault code: %d, fault string: %s",
                        bug_entity.bug_id, err.faultCode, err.faultString)
                    bug_entity.title = 'Invalid bug number'
                return
            except Exception:
                log.exception("Unknown exception from Bugzilla")
                return
        if bug.product == 'Security Response':
            bug_entity.parent = True
        bug_entity.title = bug.short_desc
        if isinstance(bug.keywords, str):
            keywords = bug.keywords.split()
        else:  # python-bugzilla 0.8.0+
            keywords = bug.keywords
        if 'security' in [keyword.lower() for keyword in keywords]:
            bug_entity.security = True

    def modified(self, bug_id: typing.Union[int, str], comment: str) -> None:
        """
        Change the status of this bug to MODIFIED if not already MODIFIED, VERIFIED, or CLOSED.

        This method will only operate on bugs that are associated with products listed
        in the bz_products setting.

        This will also comment on the bug stating that an update has been submitted.

        Args:
            bug_id: The bug you wish to mark MODIFIED.
            comment: The comment to be included with the state change.
        """
        try:
            bug = self.bz.getbug(bug_id)
            if bug.product not in config.get('bz_products'):
                log.info("Skipping set modified on {0!r} bug #{1}".format(bug.product, bug_id))
                return
            if bug.bug_status not in ('MODIFIED', 'VERIFIED', 'CLOSED'):
                log.info('Setting bug #%s status to MODIFIED' % bug_id)
                bug.setstatus('MODIFIED', comment=comment)
            else:
                bug.addcomment(comment)
        except xmlrpc_client.Fault as err:
            if err.faultCode == 102:
                log.info('Cannot retrieve private bug #%d.', bug_id)
            else:
                log.exception(
                    "Got fault from Bugzilla on #%d: fault code: %d, fault string: %s",
                    bug_id, err.faultCode, err.faultString)
        except Exception:
            log.exception("Unable to alter bug #%s" % bug_id)


def set_bugtracker() -> None:
    """Set the module-level bugtracker attribute to the correct bugtracker, based on the config."""
    global bugtracker
    if config.get('bugtracker') == 'bugzilla':
        log.info('Using python-bugzilla')
        bugtracker = Bugzilla()
    else:
        log.info('Using the FakeBugTracker')
        bugtracker = FakeBugTracker()
