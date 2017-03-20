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

import logging
import xmlrpclib

from bunch import Bunch
from kitchen.text.converters import to_unicode
import bugzilla

from bodhi.server.config import config


bugtracker = None
log = logging.getLogger('bodhi')


class BugTracker(object):

    def _(self, *args, **kw):  # pragma: no cover
        raise NotImplementedError

    getbug = update_details = modified = on_qa = close = update_details = _


class FakeBugTracker(BugTracker):

    def getbug(self, bug_id, *args, **kw):
        return Bunch(bug_id=int(bug_id))

    def __noop__(self, *args, **kw):
        log.debug('__noop__(%s)' % str(args))

    comment = update_details = modified = close = on_qa = __noop__


class InvalidComment(Exception):
    """ Exception thrown when the comment posted is invalid (for example
    too long.
    """
    pass


class Bugzilla(BugTracker):

    def __init__(self):
        self._bz = None

    def _connect(self):
        user = config.get('bodhi_email')
        password = config.get('bodhi_password', None)
        url = config.get("bz_server")
        log.info("Using BZ URL %s" % url)
        if user and password:
            self._bz = bugzilla.Bugzilla(url=url,
                                         user=user, password=password,
                                         cookiefile=None, tokenfile=None)
        else:
            self._bz = bugzilla.Bugzilla(url=url,
                                         cookiefile=None, tokenfile=None)

    @property
    def bz(self):
        if self._bz is None:
            self._connect()
        return self._bz

    def get_url(self, bug_id):
        return "%s/show_bug.cgi?id=%s" % (config['bz_baseurl'], bug_id)

    def getbug(self, bug_id):
        return self.bz.getbug(bug_id)

    def comment(self, bug_id, comment):
        try:
            if len(comment) > 65535:
                raise InvalidComment("Comment is too long: %s" % comment)
            bug = self.bz.getbug(bug_id)
            attempts = 0
            while attempts < 5:
                try:
                    bug.addcomment(comment)
                    break
                except xmlrpclib.Fault as e:
                    attempts += 1
                    log.exception(
                        "\nA fault has occured \nFault code: %d \nFault string: %s" %
                        (e.faultCode, e.faultString))
        except InvalidComment:
            log.exception(
                "Comment too long for bug #%d:  %s" % (bug_id, comment))
        except:
            log.exception("Unable to add comment to bug #%d" % bug_id)

    def on_qa(self, bug_id, comment):
        """
        Change the status of this bug to ON_QA, and comment on the bug with
        some details on how to test and provide feedback for this update.
        """
        log.debug("Setting Bug #%d to ON_QA" % bug_id)
        try:
            bug = self.bz.getbug(bug_id)
            bug.setstatus('ON_QA', comment=comment)
        except:
            log.exception("Unable to alter bug #%d" % bug_id)

    def close(self, bug_id, versions, comment):
        """
        Close the bug given by bug_id, mark it as fixed in the given versions,
        and add a comment.
        """
        args = {'comment': comment}
        try:
            bug = self.bz.getbug(bug_id)
            # If this bug is for one of these builds...
            if bug.component in versions:
                version = versions[bug.component]
                # Get the existing list
                fixedin = [v.strip() for v in bug.fixed_in.split()]
                # Strip out any empty strings (already stripped)
                fixedin = [v for v in fixedin if v]
                # And add our build if its not already there
                if version not in fixedin:
                    fixedin.append(version)

                # There are Red Hat preferences to how this field should be
                # structured.  We should use:
                # - the full NVR as it appears in koji
                # - space-separated if there's more than one.
                args['fixedin'] = " ".join(fixedin)

            bug.close('ERRATA', **args)
        except xmlrpclib.Fault:
            log.exception("Unable to close bug #%d" % bug_id)

    def update_details(self, bug, bug_entity):
        if not bug:
            try:
                bug = self.bz.getbug(bug_entity.bug_id)
            except xmlrpclib.Fault:
                bug_entity.title = 'Invalid bug number'
                log.exception("Got fault from Bugzilla")
                return
            except:
                log.exception("Unknown exception from Bugzilla")
        if bug.product == 'Security Response':
            bug_entity.parent = True
        bug_entity.title = to_unicode(bug.short_desc)
        if isinstance(bug.keywords, basestring):
            keywords = bug.keywords.split()
        else:  # python-bugzilla 0.8.0+
            keywords = bug.keywords
        if 'security' in [keyword.lower() for keyword in keywords]:
            bug_entity.security = True

    def modified(self, bug_id):
        try:
            bug = self.bz.getbug(bug_id)
            if bug.product not in config.get('bz_products', '').split(','):
                log.info("Skipping %r bug" % bug.product)
                return
            if bug.bug_status not in ('MODIFIED', 'VERIFIED', 'CLOSED'):
                log.info('Setting bug #%d status to MODIFIED' % bug_id)
                bug.setstatus('MODIFIED')
        except:
            log.exception("Unable to alter bug #%d" % bug_id)


def set_bugtracker():
    """
    Set the module-level bugtracker attribute to the correct bugtracker, based on the config.
    """
    global bugtracker
    if config.get('bugtracker') == 'bugzilla':
        log.info('Using python-bugzilla')
        bugtracker = Bugzilla()
    else:
        log.info('Using the FakeBugTracker')
        bugtracker = FakeBugTracker()
