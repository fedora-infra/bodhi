import logging

from kitchen.text.converters import to_unicode
from bunch import Bunch
from bodhi.config import config

log = logging.getLogger('bodhi')


class BugTracker(object):
    pass


class FakeBugTracker(BugTracker):

    def getbug(self, bug_id, *args, **kw):
        return Bunch(bug_id=int(bug_id))

    def update_details(self, *args, **kw):
        pass


class Bugzilla(object):

    def __init__(self):
        user = config.get('bodhi_email')
        password = config.get('bodhi_password', None)
        if user and password:
            self.bz = bugzilla.Bugzilla(url=config.get("bz_server"),
                                        user=user, password=password)
        else:
            self.bz = bugzilla.Bugzilla(url=config.get("bz_server"))

    def get_url(self, bug_id):
        return "%s/show_bug.cgi?id=%s" % (config['bz_baseurl'], bug_id)

    def getbug(self, bug_id):
        return self.bz.getbug(bug_id)

    def comment(self, bug_id, comment):
        try:
            bug = self.bz.getbug(bug_id)
            bug.addcomment(comment)
        except Exception, e:
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
        except Exception, e:
            log.exception("Unable to alter bug #%d" % bug_id)

    def close(self, bug_id, fixedin=None):
        args = {}
        if fixedin:
            args['fixedin'] = fixedin
        try:
            ver = '-'.join(get_nvr(update.builds[0].nvr)[-2:])
            bug = self.bz.getbug(self.bug_id)
            bug.close('NEXTRELEASE', **args)
        except xmlrpclib.Fault, f:
            log.exception("Unable to close bug #%d" % self.bug_id)

    def update_details(self, bug, bug_entity):
        if not bug:
            try:
                bug = self.bz.getbug(bug_entity.bug_id)
            except xmlrpclib.Fault, f:
                bug_entity.title = 'Invalid bug number'
                log.exception("Got fault from Bugzilla")
                return
        if bug.product == 'Security Response':
            bug_entity.parent = True
        bug_entity.title = to_unicode(bug.short_desc)
        if isinstance(bug.keywords, basestring):
            keywords = bug.keywords.split()
        else:  # python-bugzilla 0.8.0+
            keywords = bug.keywords
        if 'security' in [keyword.lower() for keyword in keywords]:
            bug_entity.security = True


if config.get('bugtracker') == 'bugzilla':
    import bugzilla
    log.debug('Using python-bugzilla')
    bugtracker = Bugzilla()
else:
    log.debug('Using the dummy BugTracker')
    bugtracker = FakeBugTracker()
