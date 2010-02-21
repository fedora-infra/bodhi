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

from sqlobject import *
from datetime import datetime

from turbogears import config
from turbogears.database import PackageHub
from turbogears.identity import RequestRequiredException

from os.path import isfile, join
from textwrap import wrap

try:
    from fedora.tg.tg1utils import tg_url
except ImportError:
    from fedora.tg.util import tg_url

from bodhi import buildsys, mail
from bodhi.util import get_nvr, rpm_fileheader, header, get_age, get_age_in_days
from bodhi.util import Singleton, authorized_user, flash_log, build_evr, url
from bodhi.exceptions import RPMNotFound, InvalidRequest
from bodhi.identity.tables import *

log = logging.getLogger(__name__)
hub = PackageHub("bodhi")
__connection__ = hub

soClasses=('Release', 'Package', 'PackageBuild', 'PackageUpdate', 'CVE',
           'Bugzilla', 'Comment', 'User', 'Group', 'Visit')


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
        return '%s-testing' % self.stable_tag

    @property
    def stable_tag(self):
        if self.name.startswith('EL'): # EPEL Hack.
            return self.dist_tag
        else:
            return '%s-updates' % self.dist_tag

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

        if action == 'unpush':
            self.unpush()
            self.comment('This update has been unpushed',
                         author=identity.current.user_name)
            flash_log("%s has been unpushed" % self.title)
            return
        elif action == 'obsolete':
            self.obsolete()
            flash_log("%s has been obsoleted" % self.title)
            return
        elif self.type == 'security' and not self.approved:
            flash_log("%s is awaiting approval of the Security Team" %
                      self.title)
            self.request = action
            return
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
        if action == 'stable' and self.release.locked and self.critpath:
            if not self.critpath_approved:
                action = 'testing'
                log.info('Forcing critical path update into testing')
                notes.append('This critical path update has not '
                             'yet been approved.  It must reach a karma '
                             'of %d, consisting of %d positive karma from '
                             'releng/qa, along with %d additional karma from '
                             'the community.' % (
                    config.get('critpath.min_karma'),
                    config.get('critpath.num_admin_approvals'),
                    config.get('critpath.min_karma') -
                    config.get('critpath.num_admin_approvals')))

        self.request = action
        self.pushed = False
        #self.date_pushed = None
        notes = notes and '. '.join(notes) or ''
        flash_log("%s has been submitted for %s. %s" %(self.title,action,notes))
        self.comment('This update has been submitted for %s' % action,
                     author=identity.current.user_name)
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
        hub.commit()

    def modify_bugs(self):
        """
        Comment on and close this updates bugs as necessary
        """
        if self.status == 'testing':
            map(lambda bug: bug.testing(self), self.bugs)
        elif self.status == 'stable':
            map(lambda bug: bug.add_comment(self), self.bugs)

            if self.close_bugs:
                if self.type == 'security':
                    # Close all tracking bugs first
                    for bug in self.bugs:
                        if not bug.parent:
                            log.debug("Closing tracker bug %d" % bug.bz_id)
                            bug.close_bug(self)

                    # Now, close our parents bugs as long as nothing else
                    # depends on them, and they are not in a NEW state
                    bz = Bugzilla.get_bz()
                    for bug in self.bugs:
                        if bug.parent:
                            parent = bz.getbug(bug.bz_id)
                            if parent.bug_status == "NEW":
                                log.debug("Parent bug %d is still NEW; not "
                                          "closing.." % bug.bz_id)
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
                                bug.close_bug(self)
                else:
                    map(lambda bug: bug.close_bug(self), self.bugs)

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
        # Until our update ids are reliable...
        #if self.updateid:
        #    path.append(self.release.name)
        #    path.append(self.updateid)
        #else:
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
                else:
                    anonymous = ""
                comments.append(u"%s%s%s - %s (karma %s)" % (' ' * 13,
                                comment.author, anonymous, comment.timestamp,
                                comment.karma))
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
        for bug in bugs:
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
                else:
                    bz = Bugzilla(bz_id=int(bug))
            if bz not in self.bugs:
                self.addBugzilla(bz)

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

    def comment(self, text, karma=0, author=None, anonymous=False):
        """ Add a comment to this update, adjusting the karma appropriately.

        Each user has the ability to comment as much as they want, but only
        their last karma adjustment will be counted.  If the karma reaches
        the 'stable_karma' value, then request that this update be marked
        as stable.  If it reaches the 'unstable_karma', it is unpushed.
        """
        if not author: author = identity.current.user_name
        critpath_approved = self.critpath_approved

        # Hack: Add admin groups to usernames (eg: "lmacken (releng)")
        admin_groups = config.get('admin_groups',
                                  'releng qa security_respons').split()

        try:
            for group in identity.current.groups:
                if group in admin_groups:
                    author += ' (%s)' % group
                    break
        except RequestRequiredException:
            # This happens when we're adding comments from the masher,
            # in which case this block is not necessary
            pass

        if not anonymous and karma != 0 and \
           not filter(lambda c: c.author == author and c.karma == karma,
                      self.comments):
            mycomments = [c.karma for c in self.comments if c.author == author]
            if karma == 1 and -1 in mycomments:
                self.karma += 2
            elif karma == -1 and 1 in mycomments:
                self.karma -= 2
            else:
                self.karma += karma
            log.info("Updated %s karma to %d" % (self.title, self.karma))

        Comment(text=text, karma=karma, update=self, author=author,
                anonymous=anonymous)

        if self.stable_karma != 0 and self.stable_karma == self.karma:
            # If we're a criticalpath update to a pending release that is
            # not yet approved, ensure that this karma can't cause it 
            # to go to stable.
            if (self.critpath and self.release.locked and 
                not self.critpath_approved):
                pass
            else:
                log.info("Automatically marking %s as stable" % self.title)
                self.request = 'stable'
                self.pushed = False
                #self.date_pushed = None
                mail.send(self.submitter, 'stablekarma', self)
                mail.send_admin('stablekarma', self)

        if self.status == 'testing' and self.unstable_karma != 0 and \
           self.karma == self.unstable_karma:
            log.info("Automatically unpushing %s" % self.title)
            self.obsolete()
            mail.send(self.submitter, 'unstable', self)

        # If we're a Critical Path update for a pending release
        if self.critpath and self.release.locked:
            # If we weren't approved before, and now are, push to stable
            if not critpath_approved and self.critpath_approved:
                self.comment('Critical path update approved', author='bodhi')
                self.request = 'stable'
                mail.send_admin('critpath_approved', self)

        # Send a notification to everyone that has commented on this update
        people = set()
        people.add(self.submitter)
        # Until we can differentiate between maintainers and committers
        #for person in self.get_maintainers():
        #    people.add(person)
        for comment in self.comments:
            if comment.anonymous or comment.author == 'bodhi':
                continue
            people.add(comment.author.split()[0])
        mail.send(people, 'comment', self)

    def unpush(self):
        """ Move this update back to its dist-fX-updates-candidate tag """
        koji = buildsys.get_session()
        tasks = []
        newtag = self.release.candidate_tag
        curtag = self.get_build_tag()
        if curtag == self.release.candidate_tag:
            log.debug("%s already unpushed" % self.title)
            return
        log.debug("Unpushing %s" % self.title)
        for build in self.builds:
            if build.inherited:
                log.debug("Removing %s tag from inherited build %s" % (
                    curtag, build.nvr))
                koji.untagBuild(curtag, build.nvr, force=True)
            else:
                log.debug("Moving %s from %s to %s" % (build.nvr, curtag, newtag))
                task = koji.moveBuild(curtag, newtag, build.nvr, force=True)
                tasks.append(task)
        if tasks:
            log.debug('Waiting for %s tasks to complete...' % tasks)
            if buildsys.wait_for_tasks(tasks, sleep=1):
                log.error('One or more tasks failed!')
            else:
                log.debug('Tasks complete!')
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

    def obsolete(self, newer=None):
        """
        Obsolete this update. Even though unpushing/obsoletion is an "instant"
        action, changes in the repository will not propagate until the next
        mash takes place.
        """
        log.debug("Obsoleting %s" % self.title)
        if self.status != 'pending':
            self.untag()
        self.status = 'obsolete'
        self.request = None
        if newer:
            self.comment("This update has been obsoleted by %s" % newer,
                         author='bodhi')
        else:
            self.comment("This update has been obsoleted", author='bodhi')

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
                close_bugs=self.close_bugs,
                nagged=self.nagged,
                approved=self.approved)

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
        critpath_pkgs = config.get('critpath').split()
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
            # FIXME:
            # We need to actually store the groups or approvals sanely.
            # Hack, to get this working for F13 w/o changing the DB
            if comment.author.endswith(')'):
                group = comment.author[:-1].split('(')[-1]
                if group in config.get('admin_groups', 'qa releng').split():
                    approvals += 1
        return approvals

    @property
    def critpath_approved(self):
        """ Return whether or not this critpath update has been approved """
        return self.num_admin_approvals >= config.get(
                'critpath.num_admin_approvals', 2) and \
               self.karma >= config.get('critpath.min_karma', 2)


class Comment(SQLObject):
    timestamp   = DateTimeCol(default=datetime.utcnow)
    update      = ForeignKey("PackageUpdate", notNone=True)
    author      = UnicodeCol(notNone=True)
    karma       = IntCol(default=0)
    text        = UnicodeCol()
    anonymous   = BoolCol(default=False)

    def __str__(self):
        karma = '0'
        if self.karma != 0:
            karma = '%+d' % (self.karma,)
        if self.anonymous:
            anonymous = " (unauthenticated)"
        else:
            anonymous = ""
        return "%s%s - %s (karma: %s)\n%s" % (self.author, anonymous,
                                            self.timestamp, karma, self.text)

    def __json__(self):
        return dict(author=self.author, text=self.text,
                    anonymous=self.anonymous, karma=self.karma,
                    timestamp=self.timestamp)


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
    default_msg = "%s has been pushed to the %s repository.  If problems " + \
                  "still persist, please make note of it in this bug report."

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
        message = self.default_msg % (update.get_title(delim=', '), "%s %s" % 
                                   (update.release.long_name, update.status))
        if update.status == "testing":
            if update.release.name in ('F9', 'F8'):
                repo = 'updates-testing-newkey'
            else:
                repo = 'updates-testing'
            message += ("\n If you want to test the update, you can install " +
                       "it with \n su -c 'yum --enablerepo=%s " +
                       "update %s'.  You can provide feedback for this " +
                       "update here: %s") % (repo,
                           ' '.join([build.package.name for build in 
                                     update.builds]),
                           config.get('base_address') + url(update.get_url()))

        return message

    def add_comment(self, update, comment=None):
        if not config.get('bodhi_email'):
            log.warning("No bodhi_email defined; skipping bug comment")
            return
        bz = Bugzilla.get_bz()
        if not comment:
            comment = self._default_message(update)
        log.debug("Adding comment to Bug #%d: %s" % (self.bz_id, comment))
        try:
            bug = bz.getbug(self.bz_id)
            bug.addcomment(comment)
        except Exception, e:
            log.error("Unable to add comment to bug #%d\n%s" % (self.bz_id,
                                                                str(e)))

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
                if bug.product != 'Fedora' and bug.product != 'Fedora EPEL':
                    log.warning("Skipping %r bug" % bug.product)
                    return
                bug.setstatus('ON_QA', comment=comment)
            except Exception, e:
                log.error("Unable to alter bug #%d\n%s" % (self.bz_id, str(e)))
        else:
            log.debug('Skipping bug modification, close_bugs == False')

    def close_bug(self, update):
        """Close this bugzilla with details from an update.

        This method will only close Fedora or Fedora EPEL bugs, and it will
        close them with the status of `ERRATA`.   For details on why this
        is so, see this ticket: https://fedorahosted.org/bodhi/ticket/320
        """
        bz = Bugzilla.get_bz()
        try:
            bug = bz.getbug(self.bz_id)
            if bug.product != 'Fedora' and bug.product != 'Fedora EPEL':
                log.warning("Not closing %r bug" % bug.product)
                return
            bug.close('ERRATA', fixedin=update.builds[0].nvr)
        except xmlrpclib.Fault, f:
            log.error("Unable to close bug #%d: %s" % (self.bz_id, str(f)))

    def get_url(self):
        return "https://bugzilla.redhat.com/show_bug.cgi?id=%s" % self.bz_id


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
                                           int(y['long_name'].split()[-1])))
        self.data = releases
