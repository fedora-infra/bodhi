# $Id: model.py,v 1.9 2007/01/08 06:07:07 lmacken Exp $
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

import re
import rpm
import time
import logging
import bugzilla
import turbomail
import xmlrpclib

from kid import XML
from kid.element import encode_entity
from sqlobject import *
from datetime import datetime
try:
    from collections import defaultdict
except ImportError:
    from kitchen.pycompat25.collections import defaultdict

from turbogears import config
from turbogears.database import PackageHub
from turbogears.identity import RequestRequiredException

from os.path import isfile, join
from textwrap import wrap

try:
    from fedora.tg.tg1utils import tg_url
except ImportError:
    from fedora.tg.util import tg_url

import fedmsg

from bodhi import buildsys, mail
from bodhi.util import get_nvr, rpm_fileheader, header, get_age, get_age_in_days
from bodhi.util import Singleton, authorized_user, flash_log, build_evr, url
from bodhi.util import link, isint, get_critpath_pkgs
from bodhi.exceptions import RPMNotFound, InvalidRequest
from bodhi.identity.tables import *

log = logging.getLogger(__name__)
hub = PackageHub("bodhi")
__connection__ = hub

soClasses=('Release', 'Package', 'PackageBuild', 'PackageUpdate', 'CVE',
           'Bugzilla', 'Comment', 'User', 'Group', 'Visit', 'BuildRootOverride')


class Release(SQLObject):
    """ Table of releases that we will be pushing updates for """
    name        = UnicodeCol(alternateID=True, notNone=True)
    long_name   = UnicodeCol(notNone=True)
    updates     = MultipleJoin('PackageUpdate', joinColumn='release_id')
    id_prefix   = UnicodeCol(notNone=True)
    dist_tag    = UnicodeCol(notNone=True) # ie dist-fc7
    metrics     = PickleCol(default=None) # {metric: {data}}

    # [No Frozen Rawhide] We're going to re-use this column to flag 'pending'
    # releases, since we'll no longer need to lock releases in this case.
    locked      = BoolCol(default=False)

    def get_version(self):
        regex = re.compile('\D+(\d+)$')
        return int(regex.match(self.name).groups()[0])

    @property
    def collection_name(self):
        """ Return the collection name of this release.  (eg: Fedora EPEL) """
        return ' '.join(self.long_name.split()[:-1])

    @property
    def candidate_tag(self):
        if self.name.startswith('EL'): # EPEL Hack.
            return '%s-testing-candidate' % self.dist_tag
        else:
            return '%s-updates-candidate' % self.dist_tag

    @property
    def testing_tag(self):
        if self.locked:
            return '%s-updates-testing' % self.stable_tag
        return '%s-testing' % self.stable_tag

    @property
    def stable_tag(self):
        if self.locked:
            return self.dist_tag
        if self.name.startswith('EL'): # EPEL Hack.
            return self.dist_tag
        else:
            return '%s-updates' % self.dist_tag

    @property
    def pending_testing_tag(self):
        return self.testing_tag + '-pending'

    @property
    def pending_stable_tag(self):
        if self.locked:
            return '%s-updates-pending' % self.dist_tag
        return self.stable_tag + '-pending'

    @property
    def override_tag(self):
        return '%s-override' % self.dist_tag

    @property
    def stable_repo(self):
        id = self.name.replace('-', '').lower()
        if self.name.startswith('EL'): # EPEL Hack.
            return '%s-epel' % id
        else:
            return '%s-updates' % id

    @property
    def testing_repo(self):
        id = self.name.replace('-', '').lower()
        if self.name.startswith('EL'):
            return '%s-epel-testing' % id
        else:
            return '%s-updates-testing' % id

    @property
    def mandatory_days_in_testing(self):
        name = self.name.lower().replace('-', '')
        status = config.get('%s.status' % name, None)
        if status:
            days = config.get('%s.%s.mandatory_days_in_testing' % (name, status))
            if days:
                return days
        return config.get('%s.mandatory_days_in_testing' %
                          self.id_prefix.lower().replace('-', '_'))

    def __json__(self):
        return dict(name=self.name, long_name=self.long_name,
                    id_prefix=self.id_prefix, dist_tag=self.dist_tag,
                    locked=self.locked)


class Package(SQLObject):
    name            = UnicodeCol(alternateID=True, notNone=True)
    builds          = MultipleJoin('PackageBuild', joinColumn='package_id')
    suggest_reboot  = BoolCol(default=False)
    committers      = PickleCol(default=[])
    stable_karma    = IntCol(default=3)
    unstable_karma  = IntCol(default=-3)

    def updates(self):
        updates = set()
        for build in self.builds:
            for update in build.updates:
                updates.add(update)
        updates = list(updates)
        updates.sort(cmp=lambda x, y: cmp(x.date_submitted, y.date_submitted),
                     reverse=True)
        return updates

    def __str__(self):
        x = header(self.name)
        states = { 'pending' : [], 'testing' : [], 'stable' : [] }
        if len(self.builds):
            for build in self.builds:
                for state in states.keys():
                    states[state] += filter(lambda u: u.status == state,
                                            build.updates)
        for state in states.keys():
            if len(states[state]):
                x += "\n %s Updates (%d)\n" % (state.title(),
                                               len(states[state]))
                for update in states[state]:
                    x += "    o %s\n" % update.title
        del states
        return x

    def __json__(self):
        return dict(name=self.name, suggest_reboot=self.suggest_reboot,
                    committers=self.committers)

    def get_test_cases(self):
        """ Get a list of test cases from the wiki """
        from simplemediawiki import MediaWiki
        wiki = MediaWiki(config.get('wiki_url', 'https://fedoraproject.org/w/api.php'))
        cat_page = 'Category:Package %s test cases' % self.name
        limit = 10

        def list_categorymembers(wiki, cat_page, limit=10):
            # Build query arguments and call wiki
            query = dict(action='query', list='categorymembers', cmtitle=cat_page)
            response = wiki.call(query)
            members = [entry.get('title') for entry in
                       response.get('query',{}).get('categorymembers',{})
                       if entry.has_key('title')]

            # Determine whether we need to recurse
            idx = 0
            while True:
                if idx >= len(members) or limit <= 0:
                    break
                # Recurse?
                if members[idx].startswith('Category:') and limit > 0:
                    members.extend(list_categorymembers(wiki, members[idx], limit-1))
                    members.remove(members[idx]) # remove Category from list
                else:
                    idx += 1

            return members

        return list_categorymembers(wiki, cat_page)


class PackageBuild(SQLObject):
    nvr             = UnicodeCol(notNone=True, alternateID=True)
    package         = ForeignKey('Package')
    updates         = RelatedJoin("PackageUpdate")
    inherited       = BoolCol(default=False)

    def get_rpm_header(self):
        """ Get the rpm header of this build """
        return rpm_fileheader(self.get_srpm_path())

    def get_changelog(self, timelimit=0):
        """
        Retrieve the RPM changelog of this package since it's last update
        """
        rpm_header = self.get_rpm_header()
        descrip = rpm_header[rpm.RPMTAG_CHANGELOGTEXT]
        if not descrip: return ""

        who = rpm_header[rpm.RPMTAG_CHANGELOGNAME]
        when = rpm_header[rpm.RPMTAG_CHANGELOGTIME]

        num = len(descrip)
        if num == 1: when = [when]

        str = ""
        i = 0
        while (i < num) and (when[i] > timelimit):
            str += '* %s %s\n%s\n' % (time.strftime("%a %b %e %Y",
                                      time.localtime(when[i])), who[i],
                                      descrip[i])
            i += 1
        del rpm_header
        return str

    def get_srpm_path(self):
        """ Return the path to the SRPM for this update """
        src_path = self.get_source_path()
        path = src_path.split('/')
        srpm = join(src_path, "src", "%s.src.rpm" % ('-'.join(path[-3:])))
        if not isfile(srpm):
            log.debug("Cannot find SRPM: %s" % srpm)
            raise RPMNotFound
        return srpm

    def get_source_path(self):
        """ Return the path of this built update """
        return join(config.get('build_dir'), *get_nvr(self.nvr))

    def get_latest(self):
        """ Return the path to the last released srpm of this package """
        latest_srpm = None
        koji_session = buildsys.get_session()

        # Grab a list of builds tagged with dist-$RELEASE-updates, and find
        # the most recent update for this package, other than this one.  If
        # nothing is tagged for -updates, then grab the first thing in
        # dist-$RELEASE.  We aren't checking -updates-candidate first, because
        # there could potentially be packages that never make their way over
        # -updates, so we don't want to generate ChangeLogs against those.
        nvr = get_nvr(self.nvr)
        release = self.updates[0].release
        for tag in [release.stable_tag, release.dist_tag]:
            builds = koji_session.getLatestBuilds(tag, None, self.package.name)
            latest = None

            # Find the first build that is older than us
            for build in builds:
                if rpm.labelCompare(nvr, get_nvr(build['nvr'])) > 0:
                    latest = get_nvr(build['nvr'])
                    break

            if latest:
                srpm_path = join(config.get('build_dir'), latest[0],
                                 latest[1], latest[2], 'src',
                                 '%s.src.rpm' % '-'.join(latest))
                if isfile(srpm_path):
                    log.debug("Latest build before %s: %s" % (self.nvr,
                                                              srpm_path))
                    latest_srpm = srpm_path
                else:
                    log.warning("Latest build %s not found" % srpm_path)
                break

        return latest_srpm

    def get_url(self):
        """ Return a the url to details about this build """
        return '/' + self.nvr

    def get_tags(self):
        """ Return the koji tags for this build """
        koji = buildsys.get_session()
        return [tag['name'] for tag in koji.listTags(build=self.nvr)]

    def __json__(self):
        return dict(nvr=self.nvr, package=self.package.__json__())


class PackageUpdate(SQLObject):
    """ This class defines an update in our system. """
    title            = UnicodeCol(notNone=True, alternateID=True)
    builds           = RelatedJoin("PackageBuild")
    date_submitted   = DateTimeCol(default=datetime.utcnow, notNone=True)
    date_modified    = DateTimeCol(default=None)
    date_pushed      = DateTimeCol(default=None)
    submitter        = UnicodeCol(notNone=True)
    updateid         = UnicodeCol(default=None)
    type             = EnumCol(enumValues=['security', 'bugfix', 'enhancement',
                                           'newpackage'])
    cves             = RelatedJoin("CVE")
    bugs             = RelatedJoin("Bugzilla")
    release          = ForeignKey('Release')
    status           = EnumCol(enumValues=['pending', 'testing', 'stable',
                                           'obsolete'], default='pending')
    pushed           = BoolCol(default=False)
    notes            = UnicodeCol()
    request          = EnumCol(enumValues=['testing', 'stable', 'obsolete',
                                           None], default=None)
    comments         = MultipleJoin('Comment', joinColumn='update_id', orderBy='timestamp')
    karma            = IntCol(default=0)
    close_bugs       = BoolCol(default=True)
    nagged           = PickleCol(default=None) # { nagmail_name : datetime, ... }
    approved         = DateTimeCol(default=None)

    stable_karma     = property(lambda self: self.builds[0].package.stable_karma)
    unstable_karma   = property(lambda self: self.builds[0].package.unstable_karma)

    def get_title(self, delim=' '):
        return delim.join([build.nvr for build in self.builds])

    def get_bugstring(self, show_titles=False):
        """ Return a space-delimited string of bug numbers for this update """
        val = ''
        if show_titles:
            i = 0
            for bug in self.bugs:
                bugstr = '%s%s - %s\n' % (i and ' ' * 11 + ': ' or '',
                                          bug.bz_id, bug.title)
                val += '\n'.join(wrap(bugstr, width=67,
                                      subsequent_indent=' ' * 11 + ': ')) + '\n'
                i += 1
            val = val[:-1]
        else:
            val = ' '.join([str(bug.bz_id) for bug in self.bugs])
        return val

    def get_cvestring(self):
        """ Return a space-delimited string of CVE ids for this update """
        return ' '.join([cve.cve_id for cve in self.cves])

    def assign_id(self):
        """
        Assign an update ID to this update.  This function finds the next number
        in the sequence of pushed updates for this release, increments it and
        prefixes it with the id_prefix of the release and the year
        (ie FEDORA-2007-0001)
        """
        if self.updateid != None and self.updateid != u'None':
            log.debug("Keeping current update id %s" % self.updateid)
            return

        releases = Release.select(Release.q.id_prefix == self.release.id_prefix)
        updates = PackageUpdate.select(
                    AND(PackageUpdate.q.date_pushed != None,
                        PackageUpdate.q.updateid != None,
                        OR(*[PackageUpdate.q.releaseID == rel.id
                             for rel in releases])),
                    orderBy=PackageUpdate.q.date_pushed, limit=1).reversed()

        try:
            update = updates[0]

            # We need to check if there are any other updates that were pushed
            # at the same time, since SQLObject ignores milliseconds
            others = PackageUpdate.select(
                        PackageUpdate.q.date_pushed == update.date_pushed)
            if others.count() > 1:
                # find the update with the highest id
                for other in others:
                    if other.updateid_int > update.updateid_int:
                        update = other

            split = update.updateid.split('-')
            year, id = split[-2:]
            prefix = '-'.join(split[:-2])
            if int(year) != time.localtime()[0]: # new year
                id = 0
            id = int(id) + 1
        except IndexError:
            id = 1 # First update

        self.updateid = u'%s-%s-%0.4d' % (self.release.id_prefix,
                                          time.localtime()[0],id)
        log.debug("Setting updateid for %s to %s" % (self.title,
                                                     self.updateid))
        self.date_pushed = datetime.utcnow()
        hub.commit()

    def set_request(self, action, pathcheck=True):
        """ Attempt to request an action for this update.

        This method either sets the given request on this update, or raises
        an InvalidRequest exception.

        At the moment, this method cannot be called outside of a request.

        @param pathcheck: Check for broken update paths for stable requests
        """
        notes = []
        if not authorized_user(self, identity):
            raise InvalidRequest("Unauthorized to perform action on %s" %
                                 self.title)
        if action not in ('testing', 'stable', 'obsolete', 'unpush', 'revoke'):
            raise InvalidRequest("Unknown request: %s" % action)
        if action == self.status:
            raise InvalidRequest("%s already %s" % (self.title, action))
        if action == self.request:
            raise InvalidRequest("%s has already been submitted to %s" % (
                                 self.title, self.request))
        if action == 'None':
            log.warning('%r was passed to set_request' % action)
            return

        fedmsg_topic = 'update.request.' + action
        if action == 'unpush':
            self.unpush()
            self.comment('This update has been unpushed',
                         author=identity.current.user_name)
            fedmsg.publish(topic=fedmsg_topic, msg=dict(update=self))
            flash_log("%s has been unpushed" % self.title)
            return
        elif action == 'obsolete':
            self.obsolete()
            fedmsg.publish(topic=fedmsg_topic, msg=dict(update=self))
            flash_log("%s has been obsoleted" % self.title)
            return
        #elif self.type == 'security' and not self.approved:
        #    flash_log("%s is awaiting approval of the Security Team" %
        #              self.title)
        #    # FIXME: Disallow direct to stable pushes of stable
        #    self.request = action
        #    return
        elif action == 'stable' and pathcheck:
            # Make sure we don't break update paths by trying to push out
            # an update that is older than than the latest.
            koji = buildsys.get_session()
            for build in self.builds:
                mybuild = koji.getBuild(build.nvr)
                mybuild['nvr'] = "%s-%s-%s" % (mybuild['name'],
                                               mybuild['version'],
                                               mybuild['release'])
                kojiBuilds = koji.listTagged(self.release.stable_tag,
                                             package=build.package.name,
                                             latest=True)
                for oldBuild in kojiBuilds:
                    if rpm.labelCompare(build_evr(mybuild),
                                        build_evr(oldBuild)) < 0:
                        raise InvalidRequest("Broken update path: %s is "
                                             "already released, and is newer "
                                             "than %s" % (oldBuild['nvr'],
                                                          mybuild['nvr']))
        elif action == 'revoke':
            if self.request:
                fedmsg.publish(topic=fedmsg_topic, msg=dict(update=self))
                flash_log('%s %s request revoked' % (self.title, self.request))
                self.request = None
                self.comment('%s request revoked' % action,
                             author=identity.current.user_name)
                mail.send_admin('revoke', self)
            else:
                flash_log('%s does not have a request to revoke' % self.title)
            return

        # [No Frozen Rawhide] Disable pushing critical path updates for
        # pending releases directly to stable.
        if action == 'stable' and self.critpath:
            if config.get('critpath.num_admin_approvals') is not None:
                if not self.critpath_approved:
                    notes.append('This critical path update has not '
                                 'yet been approved for pushing to the stable '
                                 'repository.  It must first reach a karma '
                                 'of %d, consisting of %d positive karma from '
                                 'proventesters, along with %d additional '
                                 'karma from the community. Or, it must '
                                 'spend %d days in testing without any '
                                 'negative feedback' % (
                        config.get('critpath.min_karma'),
                        config.get('critpath.num_admin_approvals'),
                        config.get('critpath.min_karma') -
                        config.get('critpath.num_admin_approvals'),
                        config.get('critpath.stable_after_days_without_negative_karma')))
                    if self.status == 'testing':
                        self.request = None
                        flash_log('. '.join(notes))
                        return
                    else:
                        log.info('Forcing critical path update into testing')
                        action = 'testing'

        # Ensure this update meets the minimum testing requirements
        flash_notes = '' 
        if action == 'stable' and not self.critpath:
            # Check if we've met the karma requirements
            if (self.stable_karma != 0 and self.karma >= self.stable_karma) or \
                    self.critpath_approved:
                pass
            else:
                # If we haven't met the stable karma requirements, check if it has met
                # the mandatory time-in-testing requirements
                if self.release.mandatory_days_in_testing:
                    if not self.met_testing_requirements and \
                       not self.meets_testing_requirements:
                        flash_notes = config.get('not_yet_tested_msg')
                        if self.status == 'testing':
                            self.request = None
                            flash_log(flash_notes)
                            return
                        elif self.request == 'testing':
                            flash_log(flash_notes)
                            return
                        else:
                            action = 'testing'

        # Add the appropriate 'pending' koji tag to this update, so tools like
        # AutoQA can mash repositories of them for testing.
        if action == 'testing':
            self.add_tag(self.release.pending_testing_tag)
        elif action == 'stable':
            self.add_tag(self.release.pending_stable_tag)

        # If an obsolete build is being re-submitted, return
        # it to the pending state, and make sure it's tagged as a candidate
        if self.status == 'obsolete':
            self.status = 'pending'
            if not self.release.candidate_tag in self.get_tags():
                self.add_tag(self.release.candidate_tag)

        self.request = action
        self.pushed = False
        #self.date_pushed = None
        notes = notes and '. '.join(notes) or ''
        flash_notes = flash_notes and '. %s' % flash_notes
        flash_log("%s has been submitted for %s. %s%s" % (self.title,
            action, notes, flash_notes))
        self.comment('This update has been submitted for %s by %s. %s' % (
            action, identity.current.user_name, notes), author='bodhi')
        fedmsg.publish(topic='update.request.' + action,
                            msg=dict(update=self))
        mail.send_admin(action, self)

    def request_complete(self):
        """
        Perform post-request actions.
        """
        if self.request == 'testing':
            self.pushed = True
            self.status = 'testing'
            self.assign_id()
        elif self.request == 'obsolete':
            self.pushed = False
            self.status = 'obsolete'
        elif self.request == 'stable':
            self.pushed = True
            self.status = 'stable'
            self.assign_id()
        self.request = None

        fedmsg_topic = 'update.complete.' + self.status
        fedmsg.publish(topic=fedmsg_topic, msg=dict(update=self))

        hub.commit()

    def modify_bugs(self):
        """
        Comment on and close this updates bugs as necessary
        """
        if self.status == 'testing':
            map(lambda bug: bug.testing(self), self.bugs)
        elif self.status == 'stable':

            if self.close_bugs:
                if self.type == 'security':
                    # Close all tracking bugs first
                    for bug in self.bugs:
                        if not bug.parent:
                            log.debug("Closing tracker bug %d" % bug.bz_id)
                            bug.close_bug(self, bug._default_message(self))

                    # Now, close our parents bugs as long as nothing else
                    # depends on them, and they are not in a NEW state
                    bz = Bugzilla.get_bz()
                    for bug in self.bugs:
                        if bug.parent:
                            parent = bz.getbug(bug.bz_id)
                            if parent.bug_status == "NEW":
                                log.debug("Parent bug %d is still NEW; not "
                                          "closing.." % bug.bz_id)
                                bug.add_comment(self)
                                continue
                            depsclosed = True
                            for dep in parent.dependson:
                                try:
                                    tracker = bz.getbug(dep)
                                except xmlrpclib.Fault, f:
                                    log.error("Can't access bug: %s" % str(f))
                                    depsclosed = False
                                    break
                                if tracker.bug_status != "CLOSED":
                                    log.debug("Tracker %d not yet closed" %
                                              bug.bz_id)
                                    depsclosed = False
                                    break
                            if depsclosed:
                                log.debug("Closing parent bug %d" % bug.bz_id)
                                bug.close_bug(self, bug._default_message(self))
                            else:
                                bug.add_comment(self)
                else:
                    map(lambda bug: bug.close_bug(
                            self, bug._default_message(self)), self.bugs)
            else:
                map(lambda bug: bug.add_comment(self), self.bugs)

    def status_comment(self):
        """
        Add a comment to this update about a change in status
        """
        if self.status == 'stable':
            self.comment('This update has been pushed to stable',
                         author='bodhi')
        elif self.status == 'testing':
            self.comment('This update has been pushed to testing',
                         author='bodhi')
        elif self.status == 'obsolete':
            self.comment('This update has been obsoleted', author='bodhi')

    def send_update_notice(self):
        log.debug("Sending update notice for %s" % self.title)
        mailinglist = None
        sender = config.get('bodhi_email')
        # eg: fedora_epel
        release_name = self.release.id_prefix.lower().replace('-', '_')
        if not sender:
            log.error("bodhi_email not defined in configuration!  Unable " +
                      "to send update notice")
            return
        if self.status == 'stable':
            mailinglist = config.get('%s_announce_list' % release_name)
        elif self.status == 'testing':
            mailinglist = config.get('%s_test_announce_list' % release_name)
        templatetype = '%s_errata_template' % release_name
        if mailinglist:
            for subject, body in mail.get_template(self, templatetype):
                message = turbomail.Message(sender, mailinglist, subject)
                message.plain = body
                try:
                    log.debug(message)
                    log.debug("Sending mail: %s" % message.plain)
                    turbomail.enqueue(message)
                except turbomail.MailNotEnabledException:
                    log.warning("mail.on is not True!")
        else:
            log.error("Cannot find mailing list address for update notice")

    def get_url(self):
        """ Return the relative URL to this update """
        path = ['/']
        if self.updateid:
            path.append(self.updateid)
            path.append(self.title)
        else:
            path.append(self.title)
        return join(*path)

    def __str__(self):
        """
        Return a string representation of this update.
        """
        val = u"%s\n%s\n%s\n" % ('=' * 80, u'\n'.join(wrap(
            self.title.replace(',', ', '), width=80, initial_indent=' '*5,
            subsequent_indent=' '*5)), '=' * 80)
        if self.updateid:
            val += u"  Update ID: %s\n" % self.updateid
        val += u"""    Release: %s
     Status: %s
       Type: %s
      Karma: %d""" % (self.release.long_name,self.status,self.type,self.karma)
        if self.request != None:
            val += u"\n    Request: %s" % self.request
        if len(self.bugs):
            bugs = self.get_bugstring(show_titles=True)
            val += u"\n       Bugs: %s" % bugs
        if len(self.cves):
            val += u"\n       CVEs: %s" % self.get_cvestring()
        if self.notes:
            notes = wrap(self.notes, width=67, subsequent_indent=' ' * 11 +': ')
            val += u"\n      Notes: %s" % '\n'.join(notes)
        val += u"""
  Submitter: %s
  Submitted: %s\n""" % (self.submitter, self.date_submitted)
        if len(self.comments):
            val += u"   Comments: "
            comments = []
            for comment in self.comments:
                if comment.anonymous:
                    anonymous = " (unauthenticated)"
                    ignored = " (ignored)"
                else:
                    anonymous = ""
                    ignored = ""
                comments.append(u"%s%s%s - %s (karma %s%s)" % (' ' * 13,
                                comment.author, anonymous, comment.timestamp,
                                comment.karma, ignored))
                if comment.text:
                    text = wrap(comment.text, initial_indent=' ' * 13,
                                subsequent_indent=' ' * 13, width=67)
                    comments.append(u'\n'.join(text) + '\n')
            val += u'\n'.join(comments).lstrip()
        val += u"\n  %s\n" % (config.get('base_address') + tg_url(self.get_url()))
        return val

    def get_build_tag(self):
        """
        Get the tag that this build is currently tagged with.
        TODO: we should probably get this stuff from koji instead of guessing
        """
        tag = self.release.stable_tag
        if self.status in ('pending', 'obsolete'):
            tag = self.release.candidate_tag
        elif self.status == 'testing':
            tag = self.release.testing_tag
        return tag

    get_implied_build_tag = get_build_tag

    def update_bugs(self, bugs):
        """
        Create any new bugs, and remove any missing ones.  Destroy removed bugs
        that are no longer referenced anymore
        """
        fetchdetails = True
        if not config.get('bodhi_email'):
            log.warning("No bodhi_email defined; not fetching bug details")
            fetchdetails = False
        for bug in self.bugs:
            if bug.bz_id not in bugs:
                self.removeBugzilla(bug)
                if len(bug.updates) == 0:
                    log.debug("Destroying stray Bugzilla #%d" % bug.bz_id)
                    bug.destroySelf()

        errors = []
        for bug in bugs:
            try:
                try:
                    bug = int(bug)
                except ValueError: # bug alias
                    bugzilla = Bugzilla.get_bz()
                    bug = bugzilla.getbug(bug).bug_id
                try:
                    bz = Bugzilla.byBz_id(bug)
                except SQLObjectNotFound:
                    if fetchdetails:
                        bugzilla = Bugzilla.get_bz()
                        newbug = bugzilla.getbug(bug)
                        bz = Bugzilla(bz_id=newbug.bug_id)
                        bz.fetch_details(newbug)
                        bz.modified()
                    else:
                        bz = Bugzilla(bz_id=int(bug))
                if bz not in self.bugs:
                    self.addBugzilla(bz)
            except xmlrpclib.Fault, f:
                # Try to keep going if we failed to lookup a bz
                log.exception(f)
                errors.append(f.faultString)

        if errors:
            raise ValueError(" ".join(errors))

    def update_cves(self, cves):
        """
        Create any new CVES, and remove any missing ones.  Destroy removed CVES 
        that are no longer referenced anymore.
        """
        for cve in self.cves:
            if cve.cve_id not in cves:
                log.debug("Removing CVE %s from %s" % (cve.cve_id, self.title))
                self.removeCVE(cve)
                if cve.cve_id not in cves and len(cve.updates) == 0:
                    log.debug("Destroying stray CVE #%s" % cve.cve_id)
                    cve.destroySelf()
        for cve_id in cves:
            try:
                cve = CVE.byCve_id(cve_id)
                if cve not in self.cves:
                    self.addCVE(cve)
            except SQLObjectNotFound:
                log.debug("Creating new CVE: %s" % cve_id)
                cve = CVE(cve_id=cve_id)
                self.addCVE(cve)

    def get_pushed_age(self):
        return get_age(self.date_pushed)

    def get_submitted_age(self):
        return get_age(self.date_submitted)

    def get_pushed_color(self):
        age = get_age_in_days(self.date_pushed)
        if age == 0 or self.karma < 0:
            color = '#ff0000' # red
        elif age < 4:
            color = '#ff6600' # orange
        elif age < 7:
            color = '#ffff00' # yellow
        else:
            color = '#00ff00' # green
        return color

    def comment(self, text, karma=0, author=None, anonymous=False, email=True):
        """ Add a comment to this update, adjusting the karma appropriately.

        Each user has the ability to comment as much as they want, but only
        their last karma adjustment will be counted.  If the karma reaches
        the 'stable_karma' value, then request that this update be marked
        as stable.  If it reaches the 'unstable_karma', it is unpushed.
        """
        if not author: author = identity.current.user_name
        critpath_approved = self.critpath_approved

        # Update submitter may only submit a karma of zero
        if author == self.submitter:
            if karma != 0:
                flash_log("The karma value of your comment has been changed to zero, because you submitted the update.")
                karma = 0

        # Add admin groups to usernames (eg: "lmacken (releng)")
        if not anonymous and author != 'bodhi':
            admin_groups = config.get('admin_groups', '').split()
            try:
                groups =  list(identity.current.groups)
                for admin_group in admin_groups:
                    if admin_group in groups:
                        author += ' (%s)' % admin_group
                        break
            except RequestRequiredException:
                # This happens when we're adding comments from the masher,
                # in which case this block is not necessary
                pass

        if not anonymous and karma != 0:
            my_karmas = [c.karma for c in self.comments if c.author == author
                         and not c.anonymous and c.karma != 0]
            if len(my_karmas) > 0:
                # Remove the previous karma.
                self.karma -= my_karmas[-1]
            self.karma += karma
            log.info("Updated %s karma to %d" % (self.title, self.karma))

        c = Comment(text=text, karma=karma, update=self, author=author,
                anonymous=anonymous)
        # Send a notification to everyone that has commented on this update
        if email:
            mail.send(self.people_to_notify(), 'comment', self)

        if author != 'bodhi':
            fedmsg.publish(topic='update.comment', msg=dict(comment=c))

        if self.critpath:
            min_karma = config.get('critpath.min_karma')
            # If we weren't approved before, but are now...
            if not critpath_approved and self.critpath_approved:
                self.comment('Critical path update approved', author='bodhi')
                mail.send_admin('critpath_approved', self)
            # Karma automatism enabled
            if self.stable_karma != 0:
                # If this update has a stable karma threshold that is lower
                # than the critpath.min_karma, then automatically push it to
                # stable once it has met the requirements.
                if (self.stable_karma < min_karma and self.critpath_approved and
                    self.karma >= min_karma and self.pushable):
                    if self.request == 'testing':
                        self.remove_tag(self.release.pending_testing_tag)
                    if self.request != 'stable':
                        self.add_tag(self.release.pending_stable_tag)
                    self.request = 'stable'
                    self.comment(config.get('stablekarma_comment'), author='bodhi')
                    mail.send(self.submitter, 'stablekarma', self)
                    mail.send_admin('stablekarma', self)
                # If we're approved and meet the minimum requirements, then
                # automatically push this update to the stable repository
                if (self.critpath_approved and self.pushable and
                    self.karma >= self.stable_karma and
                    self.karma >= min_karma):
                    if self.request == 'testing':
                        self.remove_tag(self.release.pending_testing_tag)
                    if self.request != 'stable':
                        self.add_tag(self.release.pending_stable_tag)
                    self.request = 'stable'
                    self.comment(config.get('stablekarma_comment'), author='bodhi')
                    mail.send(self.submitter, 'stablekarma', self)
                    mail.send_admin('stablekarma', self)

        if self.stable_karma != 0 and self.stable_karma == self.karma:
            if self.pushable:
                if self.critpath and not self.critpath_approved:
                    pass
                else:
                    log.info("Automatically marking %s as stable" % self.title)
                    if self.request == 'testing':
                        self.remove_tag(self.release.pending_testing_tag)
                    if self.request != 'stable':
                        self.add_tag(self.release.pending_stable_tag)
                    self.request = 'stable'
                    self.pushed = False
                    #self.date_pushed = None
                    self.comment(config.get('stablekarma_comment'), author='bodhi')
                    mail.send(self.submitter, 'stablekarma', self)
                    mail.send_admin('stablekarma', self)

        if self.status == 'testing' and self.unstable_karma != 0 and \
           self.karma == self.unstable_karma:
            log.info("Automatically unpushing %s" % self.title)
            self.obsolete(msg='This update has reached a karma of %s and is '
                              'being unpushed and marked as unstable' % self.karma)
            mail.send(self.submitter, 'unstable', self)


    def unpush(self):
        """ Move this update back to its dist-fX-updates-candidate tag """
        log.debug("Unpushing %s" % self.title)
        koji = buildsys.get_session()
        tasks = []
        for build in self.builds:
            curtag = build.get_tags()
            if curtag:
                if self.release.testing_tag in curtag:
                    curtag = self.release.testing_tag
                    if build.inherited:
                        log.debug("Removing %s tag from inherited build %s" % (
                            curtag, build.nvr))
                        koji.untagBuild(curtag, build.nvr, force=True)
                    else:
                        log.debug("Moving %s from %s to %s" % (build.nvr, curtag,
                            self.release.candidate_tag))
                        task = koji.moveBuild(curtag, self.release.candidate_tag,
                                              build.nvr, force=True)
                        tasks.append(task)
                else:
                    # Could be stable or candidate already... so don't do anything
                    pass
            else:
                # Build is untagged
                task = koji.tagBuild(self.release.candidate_tag,build.nvr,force=True)
                tasks.append(task)
        if tasks:
            if buildsys.wait_for_tasks(tasks, sleep=1):
                log.error('One or more tasks failed!')
            else:
                log.debug('Tasks complete!')

        # Expire any buildroot overrides
        #try:
        #    self.expire_buildroot_overrides()
        #except Exception, e:
        #    log.exception(e)

        self.pushed = False
        self.status = 'pending'
        mail.send_admin('unpushed', self)

    def untag(self):
        """ Untag all of the builds in this update """
        log.info("Untagging %s" % self.title)
        koji = buildsys.get_session()
        tag = self.get_build_tag()
        for build in self.builds:
            try:
                koji.untagBuild(tag, build.nvr, force=True)
            except Exception, e:
                log.error('There was a problem untagging %s' % build.nvr)
                log.exception(e)
        self.pushed = False

    def obsolete(self, newer=None, msg=None):
        """
        Obsolete this update. Even though unpushing/obsoletion is an "instant"
        action, changes in the repository will not propagate until the next
        mash takes place.
        """
        log.debug("Obsoleting %s" % self.title)
        if self.status != 'pending':
            self.untag()

        # Remove the appropriate pending tags
        if self.request == 'testing':
            self.remove_tag(self.release.pending_testing_tag)
        elif self.request == 'stable':
            self.remove_tag(self.release.pending_stable_tag)

        # Expire any buildroot overrides
        #self.expire_buildroot_overrides()

        self.status = 'obsolete'
        self.request = None
        if newer:
            self.comment("This update has been obsoleted by %s" %
                    config.get('base_address') + tg_url('/%s' % newer),
                    author='bodhi')
        elif msg:
            self.comment(msg, author='bodhi')
        else:
            self.comment("This update has been obsoleted", author='bodhi')

    def add_tag(self, tag, koji=None):
        """ Add a koji tag to all builds in this update """
        log.debug('Adding tag %s to %s' % (tag, self.title))
        return_multicall = not koji
        if not koji:
            koji = buildsys.get_session()
            koji.multicall = True
        for build in self.builds:
            koji.tagBuild(tag, build.nvr, force=True)
        if return_multicall:
            return koji.multiCall()

    def remove_tag(self, tag, koji=None):
        """ Remove a koji tag from all builds in this update """
        log.debug('Removing tag %s from %s' % (tag, self.title))
        return_multicall = not koji
        if not koji:
            koji = buildsys.get_session()
            koji.multicall = True
        for build in self.builds:
            koji.untagBuild(tag, build.nvr, force=True)
        if return_multicall:
            return koji.multiCall()

    def get_maintainers(self):
        """
        Return a list of people that have commit access to all of the packages
        that are contained within this update.
        """
        people = set()
        for build in self.builds:
            if build.package.committers:
                for committer in build.package.committers:
                    people.add(committer)
        return list(people)

    def __json__(self, *args, **kw):
        """ Return a JSON representation of this update """
        return dict(
                title=self.title,
                builds=[build.__json__() for build in self.builds],
                date_submitted=self.date_submitted,
                date_modified=self.date_modified,
                date_pushed=self.date_pushed,
                submitter=self.submitter,
                updateid=self.updateid,
                type=self.type,
                bugs=[bug.__json__() for bug in self.bugs],
                release=self.release.__json__(),
                status=self.status,
                notes=self.notes,
                request=self.request,
                comments=[comment.__json__() for comment in self.comments],
                karma=self.karma,
                stable_karma=self.stable_karma,
                unstable_karma=self.unstable_karma,
                close_bugs=self.close_bugs,
                nagged=self.nagged,
                approved=self.approved,
                critpath=self.critpath,
                critpath_approved=self.critpath_approved)

    def get_comments(self):
        sorted = []
        sorted.extend(self.comments)
        sorted.sort(lambda x, y: cmp(x.timestamp, y.timestamp))
        return sorted

    @property
    def updateid_int(self):
        """ Return the integer $ID from the 'FEDORA-2008-$ID' updateid """
        if not self.updateid:
            return None
        return int(self.updateid.split('-')[-1])

    @property
    def critpath(self):
        """ Return whether or not this update is in the critical path """
        critical = False
        critpath_pkgs = get_critpath_pkgs(self.release.name.lower())
        if not critpath_pkgs:
            # Optimize case where there's no critpath packages
            return False
        for build in self.builds:
            if build.package.name in critpath_pkgs:
                critical = True
                break
        return critical

    @property
    def num_admin_approvals(self):
        """ Return the number of Releng/QA approvals of this update """
        approvals = 0
        for comment in self.comments:
            if comment.karma != 1:
                continue
            # FIXME:
            # We need to actually store the groups or approvals sanely.
            # Hack, to get this working for F13 w/o changing the DB
            if comment.author.endswith(')'):
                group = comment.author[:-1].split('(')[-1]
                if group in config.get('admin_groups').split():
                    approvals += 1
        return approvals

    @property
    def critpath_approved(self):
        """ Return whether or not this critpath update has been approved """
        # https://fedorahosted.org/bodhi/ticket/642
        if self.meets_testing_requirements:
            return True
        release_name = self.release.name.lower().replace('-', '')
        status = config.get('%s.status' % release_name, None)
        if status:
            num_admin_approvals = config.get('%s.%s.critpath.num_admin_approvals' % (
                    release_name, status), None)
            min_karma = config.get('%s.%s.critpath.min_karma' % (
                    release_name, status), None)
            if num_admin_approvals is not None and min_karma:
                return self.num_admin_approvals >= num_admin_approvals and \
                        self.karma >= min_karma
        return self.num_admin_approvals >= config.get(
                'critpath.num_admin_approvals', 2) and \
               self.karma >= config.get('critpath.min_karma', 2)

    def people_to_notify(self):
        """ Return a list of people to notify when this update changes """
        people = set()
        people.add(self.submitter)
        for comment in self.comments:
            if comment.anonymous or comment.author == 'bodhi':
                continue
            people.add(comment.author.split()[0])
        # This won't differentiate between maintainers and committers.
        # Do we want to spam *all* committers of a package for all
        # of it's updates?  If so,
        #for person in self.get_maintainers():
        #    people.add(person)
        return people

    @property
    def pushable(self):
        """ Return whether or not this update is in a pushable state.

        Note that this does not take into account critical path or karma
        policies.
        """
        return self.status != 'obsolete' and 'stable' not in (self.request,
                self.status)

    @property
    def days_in_testing(self):
        """ Return the number of days that this update has been in testing """
        timestamp = None
        for comment in self.comments[::-1]:
            if comment.text == 'This update has been pushed to testing' and \
                    comment.author == 'bodhi':
                timestamp = comment.timestamp
                if self.status == 'testing':
                    return (datetime.utcnow() - timestamp).days
                else:
                    break
        if not timestamp:
            return
        for comment in self.comments:
            if comment.text == 'This update has been pushed to stable' and \
                    comment.author == 'bodhi':
                return (comment.timestamp - timestamp).days
        return (datetime.utcnow() - timestamp).days

    @property
    def meets_testing_requirements(self):
        """
        Return whether or not this update meets the testing requirements
        for this specific release.

        If this release does not have a mandatory testing requirement, then
        simply return True.
        """
        if self.critpath:
            # Ensure there is no negative karma. We're looking at the sum of
            # each users karma for this update, which takes into account
            # changed votes.
            feedback = defaultdict(int)
            for comment in self.comments:
                if not comment.anonymous:
                    feedback[comment.author] += comment.karma
            for karma in feedback.values():
                if karma < 0:
                    return False
            num_days = config.get('critpath.stable_after_days_without_negative_karma')
            return self.days_in_testing >= num_days
        num_days = self.release.mandatory_days_in_testing
        if not num_days:
            return True
        return self.days_in_testing >= num_days

    @property
    def met_testing_requirements(self):
        """
        Return whether or not this update has already met the testing
        requirements.

        If this release does not have a mandatory testing requirement, then
        simply return True.
        """
        min_num_days = self.release.mandatory_days_in_testing
        num_days = self.days_in_testing
        if min_num_days:
            if num_days < min_num_days:
                return False
        else:
            return True
        for comment in self.comments:
            if comment.author == 'bodhi' and \
               comment.text.startswith('This update has reached') and \
               comment.text.endswith('days in testing and can be pushed to'
                                     ' stable now if the maintainer wishes'):
                return True
        return False

    def expire_buildroot_overrides(self):
        """ Obsolete any buildroot overrides from this update """
        for build in self.builds:
            try:
                override = BuildRootOverride.byBuild(build.nvr)
                if not override.date_expired:
                    log.info('Expiring buildroot override: %s' % build.nvr)
                    override.untag()
                else:
                    log.warning('Override %s already expired!' % build.nvr)
            except SQLObjectNotFound:
                pass

    def get_tags(self):
        """
        Return a list of all of the tags that all of the builds in this update
        are tagged with
        """
        tags = set()
        for build in self.builds:
            for tag in build.get_tags():
                tag.add(tags)
        return list(tags)


class Comment(SQLObject):
    timestamp   = DateTimeCol(default=datetime.utcnow)
    update      = ForeignKey("PackageUpdate", notNone=True)
    author      = UnicodeCol(notNone=True)
    karma       = IntCol(default=0)
    text        = UnicodeCol()
    anonymous   = BoolCol(default=False)

    @property
    def html_text(self):
        text = []
        if not self.text:
            return ''
        for token in encode_entity(self.text).split():
            if token.startswith('http'):
                text.append('<a href="%s">%s</a>' % (token, token))
            elif token.startswith('#') and isint(token[1:]):
                text.append('<a href="%s">%s</a>' % (
                    config.get('bz_buglink') + token[1:], token))
            elif len(token) == 6 and isint(token):
                text.append('<a href="%s">%s</a>' % (
                    config.get('bz_buglink') + token, token))
            elif token.startswith('rhbz#'):
                num = token.split('#')[1]
                if isint(num):
                    text.append('<a href="%s">%s</a>' % (
                        config.get('bz_buglink') + num, num))
                else:
                    text.append(token)
            else:
                text.append(token)
        return XML(' '.join(text))

    @property
    def author_name(self):
        return self.author.split(' (')[0]

    @property
    def author_group(self):
        split = self.author.split(' (')
        if len(split) == 2:
            return split[1][:-1]

    def __str__(self):
        karma = '0'
        if self.karma != 0:
            karma = '%+d' % (self.karma,)
        if self.anonymous:
            anonymous = " (unauthenticated)"
            ignored = " (ignored)"
        else:
            anonymous = ""
            ignored = ""
        return "%s%s - %s (karma: %s%s)\n%s" % (self.author, anonymous,
                                            self.timestamp, karma, ignored,
                                            self.text)

    def __json__(self):
        return dict(author=self.author_name, group=self.author_group,
                    text=self.text, anonymous=self.anonymous,
                    karma=self.karma, timestamp=self.timestamp)


class CVE(SQLObject):
    """
    Table of CVEs fixed within updates that we know of.

    This table has since been deprecated.  We are now tracking CVEs via 
    Bugzilla.  See http://fedoraproject.org/wiki/Security/TrackingBugs
    for more information on our bug tracking policy.

    @deprecated: We no longer track CVEs directly in bodhi.  See our new
    security bug tracking policy for more details:
        http://fedoraproject.org/wiki/Security/TrackingBugs
    """
    cve_id  = UnicodeCol(alternateID=True, notNone=True)
    updates = RelatedJoin("PackageUpdate")

    def get_url(self):
        return "http://www.cve.mitre.org/cgi-bin/cvename.cgi?name=%s" % self.cve_id


class Bugzilla(SQLObject):
    """ Table of Bugzillas that we know about. """
    bz_id    = IntCol(alternateID=True)
    title    = UnicodeCol(default=None)
    updates  = RelatedJoin("PackageUpdate")
    security = BoolCol(default=False)
    parent   = BoolCol(default=False)

    _bz_server = config.get("bz_server")

    newpackage_msg = "%s has been pushed to the %s repository."
    stable_msg = "%s has been pushed to the %s repository.  If problems " + \
                  "still persist, please make note of it in this bug report."
    testing_msg = "Package %s:\n" + \
            "* should fix your issue,\n" + \
            "* was pushed to the %s testing repository,\n" + \
            "* should be available at your local mirror within two days.\n" + \
            "Update it with:\n" + \
            "# su -c 'yum update --enablerepo=%s %s'\n" + \
            "as soon as you are able to%s.\n" + \
            "Please go to the following url:\n%s\n" + \
            "then log in and leave karma (feedback)."

    def __json__(self):
        return dict(bz_id=self.bz_id, title=self.title, security=self.security,
                    parent=self.parent)

    @staticmethod
    def get_bz():
        me = config.get('bodhi_email')
        password = config.get('bodhi_password', None)
        cookie = config.get('bz_cookie')
        if me and password:
            bz = bugzilla.Bugzilla(url=config.get("bz_server"), user=me,
                                   password=password, cookiefile=cookie)
        else:
            bz = bugzilla.Bugzilla(url=config.get("bz_server"), cookiefile=cookie)
        return bz

    def fetch_details(self, bug=None):
        if not bug:
            bz = Bugzilla.get_bz()
            try:
                bug = bz.getbug(self.bz_id)
            except xmlrpclib.Fault, f:
                self.title = 'Invalid bug number'
                log.warning("Got fault from Bugzilla: %s" % str(f))
                return
        if bug.product == 'Security Response':
            self.parent = True
        try:
            self.title = bug.short_desc
        except Exception, e:
            log.error("Unable to decode bug title: %s" % e)
            self.title = 'Unable to decode bug title'
        if 'security' in bug.keywords.lower():
            self.security = True

    def _default_message(self, update):
        if update.type == 'newpackage':
            message = self.newpackage_msg % (update.get_title(delim=', '),
                    "%s %s" % (update.release.long_name, update.status))
        elif update.status == 'testing':
            repo = 'updates-testing'
            reboot = ''
            for build in update.builds:
                if build.package.suggest_reboot:
                    reboot = ', then reboot'
                    break
            if update.release.name.startswith('EL'):
                repo = 'epel-testing'
            message = self.testing_msg % (
                update.get_title(delim=', '),
                update.release.long_name, repo, update.get_title(), reboot,
                config.get('base_address') + tg_url(update.get_url()))
        else:
            message = self.stable_msg % (update.get_title(delim=', '),
                    "%s %s" % (update.release.long_name, update.status))
        return message

    def add_comment(self, update, comment=None):
        if not config.get('bodhi_email'):
            log.warning("No bodhi_email defined; skipping bug comment")
            return
        bz = Bugzilla.get_bz()
        if not comment:
            comment = self._default_message(update)
        try:
            bug = bz.getbug(self.bz_id)
            # We only want to comment on Security Response bugs when an update
            # reaches the stable repository (#485)
            if bug.product == 'Security Response' and update.status == 'stable':
                pass
            # Skip commenting on any products not listed in our config
            elif bug.product not in config.get('bz_products', '').split(','):
                log.warning("Skipping %r bug #%d" % (bug.product, self.bz_id))
                return
            log.debug("Adding comment to Bug #%d: %s" % (self.bz_id, comment))
            bug.addcomment(comment)
        except Exception, e:
            log.error("Unable to add comment to bug #%d\n%s" % (self.bz_id,
                                                                str(e)))

    def modified(self):
        """ Change the status of this bug to MODIFIED """
        bz = Bugzilla.get_bz()
        log.debug("Setting Bug #%d to MODIFIED" % self.bz_id)
        try:
            bug = bz.getbug(self.bz_id)
            if bug.product not in config.get('bz_products', '').split(','):
                log.warning("Skipping %r bug" % bug.product)
                return
            if bug.bug_status != 'MODIFIED':
                bug.setstatus('MODIFIED')
        except Exception, e:
            log.error("Unable to alter bug #%d\n%s" % (self.bz_id, str(e)))

    def testing(self, update):
        """
        Change the status of this bug to ON_QA, and comment on the bug with
        some details on how to test and provide feedback for this update.
        """
        if update.close_bugs:
            bz = Bugzilla.get_bz()
            comment = self._default_message(update)
            log.debug("Setting Bug #%d to ON_QA" % self.bz_id)
            try:
                bug = bz.getbug(self.bz_id)
                if bug.product not in config.get('bz_products', '').split(','):
                    log.warning("Skipping %r bug" % bug.product)
                    return
                if bug.bug_status != 'ON_QA':
                    bug.setstatus('ON_QA', comment=comment)
            except Exception, e:
                log.error("Unable to alter bug #%d\n%s" % (self.bz_id, str(e)))
        else:
            log.debug('Skipping bug modification, close_bugs == False')

    def close_bug(self, update, comment=''):
        """Close this bugzilla with details from an update.

        This method will only close Fedora or Fedora EPEL bugs, and it will
        close them with the status of `ERRATA`.   For details on why this
        is so, see this ticket: https://fedorahosted.org/bodhi/ticket/320
        """
        bz = Bugzilla.get_bz()
        try:
            bug = bz.getbug(self.bz_id)
            if bug.product not in config.get('bz_products', '').split(','):
                log.warning("Not closing %r bug" % bug.product)
                return
            bug.close('ERRATA', fixedin=update.builds[0].nvr, comment=comment)
        except xmlrpclib.Fault, f:
            log.error("Unable to close bug #%d: %s" % (self.bz_id, str(f)))

    def get_url(self):
        return "https://bugzilla.redhat.com/show_bug.cgi?id=%s" % self.bz_id


class BuildRootOverride(SQLObject):
    build = UnicodeCol(alternateID=True, notNone=True)
    date_submitted = DateTimeCol(default=datetime.utcnow, notNone=True)
    notes = UnicodeCol()
    expiration = DateTimeCol(default=None)
    date_expired = DateTimeCol(default=None)
    submitter = UnicodeCol(notNone=True)
    release = ForeignKey('Release')

    def tag(self):
        koji = buildsys.get_session()
        log.debug('Tagging %s with %s' % (self.build,
            self.release.override_tag))
        koji.tagBuild(self.release.override_tag, self.build, force=True)
        mail.send_admin('buildroot_override', self)

    def untag(self):
        koji = buildsys.get_session()
        log.debug('Untagging %s with %s' % (self.build,
            self.release.override_tag))
        try:
            koji.untagBuild(self.release.override_tag, self.build, force=True)
        except Exception, e:
            log.exception(e)
            log.error('There was non-fatal problem expiring the override')

    def __json__(self):
        return dict(build=self.build, date_submitted=self.date_submitted,
                    notes=self.notes, expiration=self.expiration,
                    date_expired=self.date_expired, submitter=self.submitter,
                    release=self.release.name)


class Releases(Singleton):
    """ A cache of frequently used release data.

    This entails all of our releases, and the number of updates for
    every different type of update for each release.  This information
    is utilized by our master template, among other modules, so we want to
    avoid hitting the database for these frequent calls.

    """
    data = []

    def update(self):
        """ Refresh our release cache.

        This is called automatically by the bodhi.jobs.cache_release_data
        method periodically.
        """
        releases = []
        for release in Release.select():
            rel = {
                'long_name': release.long_name,
                'name': release.name,
                'id': release.id,
            }
            if not release.metrics or 'UpdateTypeMetric' not in release.metrics:
                log.warning("Release metrics have not been generated!")
                return
            rel.update(release.metrics['UpdateTypeMetric'])
            releases.append(rel)
            releases.sort(lambda x, y: cmp(int(x['long_name'].split()[-1]),
                                           int(y['long_name'].split()[-1])), reverse=True)
        self.data = releases
