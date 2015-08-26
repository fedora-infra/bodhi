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

from kitchen.text.converters import to_unicode
from bunch import Bunch
from bodhi.config import config

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

class CommentException(Exception):
    def __init__(self, msg, comment, comment_t):
        self.args = {self.message: msg, comment: comment, comment_len: comment_t}
        
    def __repr__(self):
        return '%s %d' % (self.args['comment'],
                          self.args['comment_len'])
    
class Bugzilla(BugTracker):

    def __init__(self):
        user = config.get('bodhi_email')
        password = config.get('bodhi_password', None)
        if user and password:
            self.bz = bugzilla.Bugzilla(url=config.get("bz_server"),
                                        user=user, password=password,
                                        cookiefile=None, tokenfile=None)
        else:
            self.bz = bugzilla.Bugzilla(url=config.get("bz_server"),
                                        cookiefile=None, tokenfile=None)

    def get_url(self, bug_id):
        return "%s/show_bug.cgi?id=%s" % (config['bz_baseurl'], bug_id)

    def getbug(self, bug_id):
        return self.bz.getbug(bug_id)

    def comment(self, bug_id, comment):
        try:
            bug = self.bz.getbug(bug_id)
            bug.addcomment(comment)
            raise CommentException('Comments cannot be longer than 65535 characters.', comment, len(comment))
        except:
            log.exception("Unable to add comment to bug #%d" % bug_id)
        except CommentException as ce:
            log.exception(ce.message)
            
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

    def close(self, bug_id, fixedin=None):
        args = {}
        if fixedin:
            args['fixedin'] = fixedin
        try:
            bug = self.bz.getbug(bug_id)
            bug.close('NEXTRELEASE', **args)
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


if config.get('bugtracker') == 'bugzilla':
    import bugzilla
    log.info('Using python-bugzilla')
    bugtracker = Bugzilla()
else:
    log.info('Using the FakeBugTracker')
    bugtracker = FakeBugTracker()
