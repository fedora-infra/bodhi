# $Id: controllers.py,v 1.11 2007/01/08 06:07:07 lmacken Exp $
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

import rpm
import mail
import urllib2
import logging
import cherrypy
import xmlrpclib

from cgi import escape
from koji import GenericError
from datetime import datetime
from sqlobject import SQLObjectNotFound
from sqlobject.sqlbuilder import AND, OR

from turbogears import (controllers, expose, validate, redirect, identity,
                        paginate, flash, error_handler, validators, config, url)
from turbogears.widgets import DataGrid

from fedora.tg.util import request_format

from bodhi import buildsys, util
from bodhi.rss import Feed
from bodhi.new import NewUpdateController, update_form
from bodhi.util import make_update_link, make_type_icon, make_karma_icon, link
from bodhi.util import flash_log, get_pkg_pushers, make_request_icon
from bodhi.util import json_redirect
from bodhi.admin import AdminController
from bodhi.metrics import MetricsController
from bodhi.model import (Package, PackageBuild, PackageUpdate, Release,
                         Bugzilla, CVE, Comment)
from bodhi.search import SearchController
from bodhi.widgets import CommentForm, OkCancelForm, CommentCaptchaForm
from bodhi.exceptions import (DuplicateEntryError, InvalidRequest,
                              PostgresIntegrityError, SQLiteIntegrityError,
                              InvalidUpdateException)

log = logging.getLogger(__name__)

class Root(controllers.RootController):

    new = NewUpdateController()
    admin = AdminController()
    search = SearchController()
    rss = Feed("rss2.0")
    metrics = MetricsController()

    comment_form = CommentForm()
    comment_captcha_form = CommentCaptchaForm()
    ok_cancel_form = OkCancelForm()

    def exception(self, tg_exceptions=None):
        """ Generic exception handler """
        log.error("Exception thrown: %s" % str(tg_exceptions))
        flash_log(str(tg_exceptions))
        if 'tg_format' in cherrypy.request.params and \
                cherrypy.request.params['tg_format'] == 'json':
            return dict()
        raise redirect("/")

    @expose(template='bodhi.templates.welcome')
    def index(self):
        """
        The main dashboard.  Here we generate the DataGrids for My Updates and 
        the latest comments.
        """
        RESULTS, FIELDS, GRID = range(3)
        updates = None

        # { 'Title' : [SelectResults, [(row, row_callback),]], ... }
        grids = {
            'comments' : [
                Comment.select(Comment.q.author != 'bodhi',
                               orderBy=Comment.q.timestamp).reversed(),
                [
                    ('Update', make_update_link),
                    ('Comment', lambda row: row.text),
                    ('From', lambda row: row.anonymous and 'Anonymous Tester' or
                                         row.author),
                    ('Karma', make_karma_icon)
                ]
            ],
       }

        if identity.current.anonymous:
            updates = 'latest'
            grids['latest'] = [
                PackageUpdate.select(
                    orderBy=PackageUpdate.q.date_submitted
                ).reversed(),
                [
                    ('Update', make_update_link),
                    ('Release', lambda row: row.release.long_name),
                    ('Status', lambda row: row.status),
                    ('Type', make_type_icon),
                    ('Request', make_request_icon),
                    ('Karma', make_karma_icon),
                    ('Submitter', lambda row: row.submitter),
                    ('Age', lambda row: row.get_submitted_age()),
                ]
            ]
        else:
            updates = 'mine'
            grids['mine'] = [
                PackageUpdate.select(
                    PackageUpdate.q.submitter == identity.current.user_name,
                    orderBy=PackageUpdate.q.date_pushed
                ).reversed(),
                [
                    ('Update', make_update_link),
                    ('Release', lambda row: row.release.long_name),
                    ('Status', lambda row: row.status),
                    ('Type', make_type_icon),
                    ('Request', make_request_icon),
                    ('Karma', make_karma_icon),
                    ('Age', lambda row: row.get_submitted_age()),
                ]
            ]

        for key, value in grids.items():
            if not value[RESULTS].count():
                grids[key].append(None)
                continue
            if value[RESULTS].count() > 5:
                value[RESULTS] = value[RESULTS][:10]
            value[RESULTS] = list(value[RESULTS])
            grids[key].append(DataGrid(name=key, fields=value[FIELDS],
                                       default=value[RESULTS]))

        return dict(now=datetime.utcnow(), updates=grids[updates][GRID],
                    comments=grids['comments'][GRID])

    @expose(template='bodhi.templates.pkgs')
    def pkgs(self, **kwargs):
        return dict()

    @expose(template="bodhi.templates.login", allow_json=True)
    def login(self, forward_url=None, previous_url=None, *args, **kw):
        if not identity.current.anonymous and identity.was_login_attempted() \
           and not identity.get_identity_errors():
            if request_format() == 'json':
                return dict(user=identity.current.user)
            raise redirect(forward_url)

        forward_url=None
        previous_url= cherrypy.request.path

        if identity.was_login_attempted():
            msg=_("The credentials you supplied were not correct or "
                  "did not grant access to this resource.")
        elif identity.get_identity_errors():
            msg=_("You must provide your credentials before accessing "
                  "this resource.")
        else:
            msg=_("Please log in.")
            forward_url= cherrypy.request.headers.get("Referer", "/")

        # This seems to be the cause of some bodhi-client errors
        cherrypy.response.status=403
        return dict(message=msg, previous_url=previous_url, logging_in=True,
                    original_parameters=cherrypy.request.params,
                    forward_url=forward_url)

    @expose()
    def logout(self):
        identity.current.logout()
        raise redirect('/')

    @expose(template="bodhi.templates.list", allow_json=True)
    @paginate('updates', limit=20, max_limit=50, allow_limit_override=True)
    @validate(validators={
            'release': validators.UnicodeString(),
            'bugs': validators.UnicodeString(),
            'cves': validators.UnicodeString(),
            'status': validators.UnicodeString(),
            'type_': validators.UnicodeString(),
            'package': validators.UnicodeString(),
            'mine': validators.StringBool(),
            'get_auth': validators.StringBool(),
            'username': validators.UnicodeString(),
            })
    def list(self, release=None, bugs=None, cves=None, status=None, type_=None,
             package=None, mine=False, get_auth=False, username=None, **kw):
        """ Return a list of updates based on given parameters """
        log.debug('list(%s)' % locals())
        query = []
        updates = []
        orderBy = PackageUpdate.q.date_submitted

        # If no arguments are specified, return the most recent updates
        if not release and not bugs and not cves and not status and not type_ \
           and not package and not mine and not username:
            log.debug("No arguments, returning latest")
            updates = PackageUpdate.select(orderBy=orderBy).reversed()
            num_items = updates.count()
            return dict(updates=updates, num_items=num_items,
                        title="%d %s found" % (num_items, num_items == 1 and
                                               'update' or 'updates'))

        try:
            if release:
                # TODO: if a specific release is requested along with get_auth,
                #       and it is not found in PackageUpdate we should add.
                #       another value to the output which indicates if the.
                #       logged in user is allowed to create a new update for.
                #       this package
                rel = Release.byName(release.upper())
                query.append(PackageUpdate.q.releaseID == rel.id)
            if status:
                query.append(PackageUpdate.q.status == status)
                if status == 'stable':
                    orderBy = PackageUpdate.q.date_pushed
            if type_:
                query.append(PackageUpdate.q.type == type_)
            if mine:
                query.append(
                    PackageUpdate.q.submitter == identity.current.user_name)
            if username:
                query.append(PackageUpdate.q.submitter == username)

            updates = PackageUpdate.select(AND(*query),
                                           orderBy=orderBy).reversed()

            # The package argument may be an update, build or package.
            if package:
                try:
                    update = PackageUpdate.byTitle(package)
                    if not release and not status and not type_:
                        updates = [update]
                    else:
                        if update in updates:
                            updates = [update] # There can be only one
                        else:
                            updates = []
                except SQLObjectNotFound:
                    try:
                        pkg = Package.byName(package)
                        if not release and not status and not type_:
                            updates = [pkg for pkg in pkg.updates()]
                        else:
                            updates = filter(lambda up: up in updates,
                                             pkg.updates())
                    except SQLObjectNotFound:
                        try:
                            build = PackageBuild.byNvr(package)
                            if not release and not status and not type_:
                                updates = build.updates
                            else:
                                results = []
                                for update in updates:
                                    if build in update.builds:
                                        results.append(update)
                                updates = results
                        except SQLObjectNotFound:
                            updates = []

            # TODO: This filtering is extremely inefficient
            # we should/could make these filters mutually exclusive, and
            # simply make them queries

            # Filter results by Bugs and/or CVEs
            if bugs:
                results = []
                for bug in map(Bugzilla.byBz_id, map(int, bugs.split(','))):
                    map(results.append,
                        filter(lambda x: bug in x.bugs, updates))
                updates = results
            if cves:
                results = []
                for cve in map(CVE.byCve_id, cves.split(',')):
                    map(results.append,
                        filter(lambda x: cve in x.cves, updates))
                updates = results
        except SQLObjectNotFound, e:
            flash_log(e)
            if request_format() == 'json':
                return dict(updates=[])

        # if get_auth is True add can_modify flag and check if the current user
        # is allowed to modify the request
        if get_auth:
            results = []
            for up in updates:
                can_modify = False
                if not identity.current.anonymous:
                    people, groups = get_pkg_pushers(up.builds[0].package.name,
                            up.release.id_prefix.capitalize(),
                            up.release.get_version())
                    if (identity.current.user_name in people[0]):
                        can_modify = True
                dict_up = up.__json__()
                dict_up['can_modify'] = can_modify
                results.append(dict_up)
            updates = results

        if isinstance(updates, list): num_items = len(updates)
        else: num_items = updates.count()

        return dict(updates=updates, num_items=num_items,
                    title="%d %s found" % (num_items, num_items == 1 and
                                           'update' or 'updates'))

    @expose(template="bodhi.templates.mine", allow_json=True)
    @identity.require(identity.not_anonymous())
    @paginate('updates', limit=20, max_limit=20, allow_limit_override=True)
    def mine(self):
        """ List all updates submitted by the current user """
        updates = PackageUpdate.select(
                       PackageUpdate.q.submitter == identity.current.user_name,
                    orderBy=PackageUpdate.q.date_submitted).reversed()
        return dict(updates=request_format() == 'json' and 
                    map(unicode, updates) or updates, title='%s\'s updates' %
                    identity.current.user_name, num_items=updates.count())

    @expose(allow_json=True)
    @identity.require(identity.not_anonymous())
    def request(self, action, update):
        """
        Request that a specified action be performed on a given update.
        Action must be one of: 'testing', 'stable', 'unpush' or 'obsolete'.
        """
        log.debug('request(%s)' % locals())
        try:
            update = PackageUpdate.byTitle(update)
            update.set_request(action)
        except SQLObjectNotFound:
            flash_log("Cannot find update %s for action: %s" % (update, action))
            if request_format() == 'json': return dict()
            raise redirect('/')
        except InvalidRequest, e:
            flash_log(str(e))
        if request_format() == 'json': return dict(update=update)
        raise redirect(update.get_url())

    @expose()
    @identity.require(identity.not_anonymous())
    def revoke(self, update):
        """ Revoke a push request for a specified update """
        update = PackageUpdate.byTitle(update)
        if not util.authorized_user(update, identity):
            flash_log("Unauthorized to revoke request for %s" % update.title)
            raise redirect(update.get_url())
        flash_log("%s request revoked" % update.request.title())
        mail.send_admin('revoke', update)
        update.request = None
        raise redirect(update.get_url())

    @expose(allow_json=True)
    @identity.require(identity.not_anonymous())
    def delete(self, update):
        """ Delete an update.

        Arguments
        :update: The title of the update to delete

        """
        try:
            update = PackageUpdate.byTitle(update)
            if not util.authorized_user(update, identity):
                flash_log("Cannot delete an update you did not submit")
                if request_format() == 'json': return dict()
                raise redirect(update.get_url())
            if not update.pushed:
                mail.send_admin('deleted', update)
                msg = "Deleted %s" % update.title
                map(lambda x: x.destroySelf(), update.comments)
                map(lambda x: x.destroySelf(), update.builds)
                update.destroySelf()
                flash_log(msg)
            else:
                flash_log("Cannot delete a pushed update")
        except SQLObjectNotFound:
            flash_log("Update %s does not exist" % update)
        if request_format() == 'json': return dict()
        raise redirect("/")

    @identity.require(identity.not_anonymous())
    @expose(template='bodhi.templates.form')
    def edit(self, update):
        """ Edit an update """
        update = PackageUpdate.byTitle(update)
        if not util.authorized_user(update, identity):
            flash_log("Cannot edit an update you did not submit")
            raise redirect(update.get_url())
        values = {
                'builds'    : {'text':update.title, 'hidden':update.title},
                'release'   : update.release.long_name,
                'testing'   : update.status == 'testing',
                'request'   : str(update.request).title(),
                'type_'     : update.type,
                'notes'     : update.notes,
                'bugs'      : update.get_bugstring(),
                'edited'    : update.title,
                'close_bugs': update.close_bugs,
                'stable_karma' : update.builds[0].package.stable_karma,
                'unstable_karma' : update.builds[0].package.unstable_karma,
                'suggest_reboot' : update.builds[0].package.suggest_reboot,
                'autokarma' : update.stable_karma != 0 and update.unstable_karma != 0,
        }
        log.debug("values = %s" % values)
        if update.status == 'testing':
            flash("Editing this update will move it back to a pending state.")
        return dict(form=update_form, values=values, action=url("/save"),
                    title='Edit Update')

    @expose(allow_json=True)
    @json_redirect
    @error_handler(new.index)
    @validate(form=update_form)
    @identity.require(identity.not_anonymous())
    def save(self, builds, type_, notes, bugs, close_bugs=False, edited=False,
             request='testing', suggest_reboot=False, inheritance=False,
             autokarma=True, stable_karma=3, unstable_karma=-3, **kw):
        """ Save an update.

        This entails either creating a new update, or editing an existing one.
        To edit an existing update, you must specify the update's original
        title in the ``edited`` keyword argument.

        Arguments:
        :builds: A list of koji builds for this update.
        :release: The release that this update is for.
        :type_: The type of this update: ``security``, ``bugfix``,
            ``enhancement``, and ``newpackage``.
        :bugs: A list of Red Hat Bugzilla ID's associated with this update.
        :notes: Details as to why this update exists.
        :request: Request for this update to change state, either to
            ``testing``, ``stable``, ``unpush``, ``obsolete`` or None.
        :suggest_reboot: Suggest that the user reboot after update.
        :inheritance: Follow koji build inheritance, which may result in this
            update being pushed out to additional releases.
        :autokarma: Allow bodhi to automatically change the state of this
            update based on the ``karma`` from user feedback.  It will
            push your update to ``stable`` once it reaches the ``stable_karma``
            and unpush your update when reaching ``unstable_karma``.
        :stable_karma: The upper threshold for marking an update as ``stable``.
        :unstable_karma: The lower threshold for unpushing an update.
        :edited: The update title of the existing update that we are editing.

        """
        log.debug('save(%s)' % locals())

        note = []      # Messages to flash to the user
        updates = []   # PackageUpdate objects 
        releases = {}  # { Release : [build, ...] }
        buildinfo = {} # { nvr : { 'nvr' : (n, v, r), 'people' : [person, ...],
                       #           'releases' : set(Release, ...),
                       #           'build' : PackageBuild } }

        if not bugs: bugs = []
        if request == 'None': request = None
        if request: request = request.lower()
        koji = buildsys.get_session()

        # Parameters used to re-populate the update form if something fails
        params = {
                'builds.text' : ' '.join(builds),
                'type'        : type_,
                'bugs'        : ' '.join(map(str, bugs)),
                'notes'       : notes,
                'edited'      : edited,
                'close_bugs'  : close_bugs and 'True' or '',
                'autokarma'   : autokarma,
                'stable_karma': stable_karma,
                'unstable_karma': unstable_karma,
        }

        # Basic sanity checks
        if type_ not in config.get('update_types'):
            flash_log('Unknown update type: %s.  Valid types are: %s' % (
                      type_, config.get('update_types')))
            raise InvalidUpdateException(params)
        if request not in ('testing', 'stable', None):
            flash_log('Unknown request: %s.  Valid requests are: testing, ' 
                      'stable, None' % request)
        if stable_karma < 1:
            flash_log("Stable karma must be at least 1.")
            raise InvalidUpdateException(params)
        if stable_karma <= unstable_karma:
            flash_log("Stable karma must be higher than unstable karma.")
            raise InvalidUpdateException(params)

        # Make sure this update doesn't already exist
        if not edited:
            for build in builds:
                try:
                    b = PackageBuild.byNvr(build)
                    if request_format() == 'json':
                        flash_log("%s update already exists!" % build)
                        return dict()
                    else:
                        flash_log("%s update already exists!" % 
                                  link(build, b.get_url()))
                        raise redirect('/new', **params)
                except SQLObjectNotFound:
                    pass

        # Make sure the submitter has commit access to these builds
        for build in builds:
            people = None
            groups = None
            buildinfo[build] = {
                    'nvr'       : util.get_nvr(build),
                    'releases'  : set()
            }
            pkg = buildinfo[build]['nvr'][0]
            try:
                # Grab a list of committers.  Note that this currently only
                # gets people who can commit to the devel branch of the
                # Fedora collection.
                people, groups = get_pkg_pushers(pkg)
                people = people[0] # we only care about committers, not watchers
                buildinfo[build]['people'] = people
            except urllib2.URLError:
                flash_log("Unable to access the package database.  Please "
                          "notify an administrator in #fedora-admin")
                raise InvalidUpdateException(params)

            # Verify that the user is either in the committers list, or is
            # a member of a groups that has privileges to commit to this package
            if not identity.current.user_name in people and \
               not filter(lambda group: group in identity.current.groups,
                          config.get('admin_groups').split()) and \
               not filter(lambda x: x in identity.current.groups, groups[0]):
                flash_log("%s does not have commit access to %s" % (
                          identity.current.user_name, pkg))
                raise InvalidUpdateException(params)

        # If we're editing an update, unpush it first so we can assume all
        # of the builds are tagged as update candidates
        if edited:
            try:
                edited = PackageUpdate.byTitle(edited)
            except SQLObjectNotFound:
                flash_log("Cannot find update '%s' to edit" % edited)
                raise InvalidUpdateException(params)
            if edited.status == 'stable':
                flash_log("Cannot edit stable updates.  Contact release "
                          "engineering at %s about unpushing this update." %
                          config.get('release_team_address'))
                raise InvalidUpdateException(params)
            edited.unpush()

        # Make sure all builds are tagged appropriately.  We also determine
        # which builds get pushed for which releases, based on the tag.
        for build in builds:
            valid = False
            try:
                tags = [tag['name'] for tag in koji.listTags(build)]
            except GenericError:
                flash_log("Invalid build: %s" % build)
                raise InvalidUpdateException(params)

            # Determine which release this build is a candidate for
            for tag in tags:
                dist = tag.split('-updates-candidate')
                if len(dist) == 2: # candidate tag
                    rel = Release.selectBy(dist_tag=dist[0])
                    if rel.count():
                        rel = rel[0]
                        log.debug("Adding %s for %s" % (rel.name, build))
                        if not releases.has_key(rel):
                            releases[rel] = []
                        if build not in releases[rel]:
                            releases[rel].append(build)
                        buildinfo[build]['releases'].add(rel)
                        valid = True
                    else:
                        log.error("Cannot find release for %s" % dist[0])

            # if we're using build inheritance, iterate over each release
            # looking to see if the latest build in its candidate tag 
            # matches the user-specified build
            if inheritance:
                log.info("Following build inheritance")
                for rel in Release.select():
                    b = koji.listTagged(rel.dist_tag + '-updates-candidate',
                                        inherit=True, latest=True,
                                        package=buildinfo[build]['nvr'][0])[0]
                    if b['nvr'] == build:
                        log.info("Adding %s for inheritance" % rel.name)
                        if not releases.has_key(rel):
                            releases[rel] = []
                        if build not in releases[rel]:
                            releases[rel].append(build)
                        buildinfo[build]['releases'].add(rel)
                        valid = True

            # If all of the builds are not properly tagged, then complain.
            if not valid:
                flash_log("%s not tagged as an update candidate" % build)
                raise InvalidUpdateException(params)

            kojiBuild = koji.getBuild(build)
            kojiBuild['nvr'] = "%s-%s-%s" % (kojiBuild['name'],
                                             kojiBuild['version'],
                                             kojiBuild['release'])

            # Check for broken update paths
            log.info("Checking for broken update paths")
            for release in buildinfo[build]['releases']:
                tags = ['dist-rawhide', release.dist_tag,
                        release.dist_tag + '-updates']
                for tag in tags:
                    pkg = buildinfo[build]['nvr'][0]
                    for oldBuild in koji.listTagged(tag, package=pkg,
                                                    latest=True):
                        if rpm.labelCompare(util.build_evr(kojiBuild),
                                            util.build_evr(oldBuild)) < 0:
                            flash_log("Broken update path: %s is older "
                                      "than %s in %s" % (kojiBuild['nvr'],
                                      oldBuild['nvr'], tag))
                            raise redirect('/new', **params)

        # Create all of the PackageBuild objects, obsoleting any older updates
        for build in builds:
            nvr = buildinfo[build]['nvr']
            try:
                package = Package.byName(nvr[0])
            except SQLObjectNotFound:
                package = Package(name=nvr[0])
            if suggest_reboot:
                package.suggest_reboot = True

            # Update our ACL cache for this pkg
            package.committers = buildinfo[build]['people']

            # If new karma thresholds are specified, save them
            if not autokarma:
                stable_karma = unstable_karma = 0
            if package.stable_karma != stable_karma:
                package.stable_karma = stable_karma
            if package.unstable_karma != stable_karma:
                package.unstable_karma = unstable_karma

            # Create or fetch the PackageBuild object for this build
            try:
                pkgBuild = PackageBuild.byNvr(build)
            except SQLObjectNotFound:
                pkgBuild = PackageBuild(nvr=build, package=package)
            buildinfo[build]['build'] = pkgBuild

            # Obsolete any older pending/testing updates.
            # If a build is associated with multiple updates, make sure that
            # all updates are safe to obsolete, or else just skip it.
            for oldBuild in package.builds:
                obsoletable = False
                for update in oldBuild.updates:
                    if update.status not in ('pending', 'testing') or \
                       update.request or \
                       update.release not in buildinfo[build]['releases'] or \
                       update in pkgBuild.updates or \
                       (edited and oldBuild in edited.builds):
                        obsoletable = False
                        break
                    if rpm.labelCompare(util.get_nvr(oldBuild.nvr), nvr) < 0:
                        log.debug("%s is obsoletable" % oldBuild.nvr)
                        obsoletable = True
                if obsoletable:
                    for update in oldBuild.updates:
                        # Have the newer update inherit the older updates bugs
                        for bug in update.bugs:
                            bugs.append(unicode(bug.bz_id))
                        # Also inherit the older updates notes as well
                        notes += '\n' + update.notes
                        update.obsolete(newer=build)
                    note.append('This update has obsoleted %s, and has '
                                'inherited its bugs and notes.' % oldBuild.nvr)

        # Create or modify the necessary PackageUpdate objects
        for release, builds in releases.items():
            if edited:
                update = edited
                log.debug("Editing update %s" % edited.title)
                update.set(release=release, date_modified=datetime.utcnow(),
                           notes=notes, type=type_, title=','.join(builds),
                           close_bugs=close_bugs)

                # Remove any unnecessary builds
                for build in update.builds:
                    if build.nvr not in edited.title:
                        log.debug("Removing unnecessary build: %s" % build.nvr)
                        update.removePackageBuild(build)
                        if len(build.updates) == 0:
                            build.destroySelf()
            else:
                try:
                    type_ = type_.encode('utf8') # hack, for ticket #288
                    update = PackageUpdate(title=','.join(builds),
                                           release=release,
                                           submitter=identity.current.user_name,
                                           notes=notes, type=type_,
                                           close_bugs=close_bugs)
                except Exception, e:
                    log.exception(e)
                    raise
                log.info("Created PackageUpdate %s" % update.title)
            updates.append(update)

            # Add the PackageBuilds to our PackageUpdate
            for build in [buildinfo[build]['build'] for build in builds]:
                if build not in update.builds:
                    update.addPackageBuild(build)

            # Add/remove the necessary Bugzillas
            try:
                update.update_bugs(bugs)
            except xmlrpclib.Fault, f:
                log.exception(f)
                note.insert(0, "Unable to access one or more bugs")

            # If there are any security bugs, make sure this update is
            # properly marked as a security update
            if update.type != 'security':
                for bug in update.bugs:
                    if bug.security:
                        update.type = 'security'
                        break

            # Send out mail notifications
            if edited:
                #mail.send(update.get_maintainers(), 'edited', update)
                mail.send(update.submitter, 'edited', update)
                note.insert(0, "Update successfully edited")
            else:
                # Notify security team of newly submitted security updates
                if update.type == 'security':
                    mail.send(config.get('security_team'), 'security', update)
                #mail.send(update.get_maintainers(), 'new', update)
                mail.send(update.submitter, 'new', update)
                note.insert(0, "Update successfully created")

                # Comment on all bugs
                for bug in update.bugs:
                    bug.add_comment(update,
                        "%s has been submitted as an update for %s.\n%s" %
                            (update.title, release.long_name,
                             config.get('base_address') + url(update.get_url())))

            # If a request is specified, make it.  By default we're submitting
            # new updates directly into testing
            if request and request != update.request:
                try:
                    update.set_request(request, pathcheck=False)
                except InvalidRequest, e:
                    flash_log(str(e))
                    raise InvalidUpdateException(params)

        flash_log('. '.join(note))

        if request_format() == 'json':
            return dict(updates=updates)
        elif len(updates) > 1:
            return dict(tg_template='bodhi.templates.list',
                        updates=updates, num_items=0,
                        title='Updates sucessfully created!')
        else:
            raise redirect(updates[0].get_url())

    @expose(template='bodhi.templates.list')
    @paginate('updates', limit=20, max_limit=20, allow_limit_override=True)
    def default(self, *args, **kw):
        """
        This method allows for the following requests

            /Package.name
            /PackageUpdate.title
            /PackageBuild.nvr
            /Release.name
            /Release.name/PackageUpdate.update_id
            /Release.name/PackageUpdate.status
            /Release.name/PackageUpdate.status/PackageUpdate.title
        """
        args = list(args)
        status = 'stable'
        order = PackageUpdate.q.date_pushed
        template = 'bodhi.templates.list'
        release = None
        single = None
        query = []
        form = identity.current.anonymous and self.comment_captcha_form \
                                           or self.comment_form
        # /Package.name
        if len(args) == 1:
            try:
                package = Package.byName(args[0])
                return dict(tg_template='bodhi.templates.pkg', pkg=package,
                            updates=[])
            except SQLObjectNotFound:
                pass

            # /PackageUpdate.title
            try:
                update = PackageUpdate.byTitle(args[0])
                return dict(tg_template='bodhi.templates.show', update=update,
                            updates=[], comment_form=form,
                            values={'title': update.title})
            except SQLObjectNotFound:
                pass

            # /Build.nvr
            try:
                build = PackageBuild.byNvr(args[0])
                if not len(build.updates):
                    # no updates associated with this build
                    return dict(tg_template=template, updates=[], num_items=0,
                                title='There are no updates for %s' % build.nvr)
                elif len(build.updates) > 1:
                    # multiple updates associated with this build
                    return dict(tg_template=template, updates=build.updates,
                                num_items=len(build.updates),
                                title='Updates for %s' % build.nvr)
                # show the update associated with this build
                return dict(tg_template='bodhi.templates.show',
                            update=build.updates[0], updates=[], comment_form=form,
                            values={'title' : build.updates[0].title})
            except SQLObjectNotFound:
                pass

        # /Release.name
        try:
            release = Release.byName(args[0])
            query.append(PackageUpdate.q.releaseID == release.id)
            del args[0]
        except SQLObjectNotFound:
            pass

        # /Release.name/{PackageUpdate.updateid,PackageUpdate.status}
        if len(args):
            if args[0] in ('testing', 'stable', 'pending', 'obsolete'):
                if args[0] == 'testing':
                    template = 'bodhi.templates.testing'
                elif args[0] == 'pending':
                    template = 'bodhi.templates.pending'
                    order = PackageUpdate.q.date_submitted
                status = args[0]
                query.append(OR(PackageUpdate.q.status == status,
                                PackageUpdate.q.request != None))
            elif args[0] == 'security':
                query.append(PackageUpdate.q.type == 'security')
                query.append(PackageUpdate.q.pushed == True)
                query.append(PackageUpdate.q.status == status)
                status = 'security'
            else:
                query.append(PackageUpdate.q.updateid == args[0])
                single = True
            del args[0]
        else:
            query.append(PackageUpdate.q.status == status)

        # /Release.name/PackageUpdate.status/PackageUpdate.title
        if len(args):
            query.append(PackageUpdate.q.title == args[0])
            single = args[0]
            del args[0]

        # Run the query that we just built
        updates = PackageUpdate.select(AND(*query), orderBy=order).reversed()

        num_updates = updates.count()
        if num_updates and (num_updates == 1 or single):
            update = updates[0]
            return dict(tg_template='bodhi.templates.show', update=update,
                        updates=[], comment_form=form,
                        values={'title' : update.title})
        elif num_updates > 1:
            try:
                return dict(tg_template=template, updates=updates,
                            num_items=num_updates, title='%s %s Updates' % (
                            release.long_name, status.title()))
            except AttributeError:
                pass
        elif single and num_updates == 0:
            # A single update was specified, but not found.  Be nice and
            # attempt to find the update that the user is looking for and 
            # redirect them to it.  (Bug #426941)
            try:
                update = PackageUpdate.byTitle(single)
                raise redirect(update.get_url())
            except SQLObjectNotFound:
                pass
        else:
            return dict(tg_template=template, updates=[], num_items=0,
                        title='No updates found')

        flash_log("The path %s cannot be found" % escape(cherrypy.request.path))
        raise redirect("/")

    @expose(template='bodhi.templates.show')
    @validate(form=comment_captcha_form)
    @validate(validators={ 'karma' : validators.Int() })
    def captcha_comment(self, text, title, author, karma, captcha={},
                        tg_errors=None):
        try:
            update = PackageUpdate.byTitle(title)
        except SQLObjectNotFound:
            flash_log("The specified update does not exist")
        if tg_errors:
            if tg_errors.has_key('text'):
                flash_log("Please fill in all comment fields")
            elif tg_errors.has_key('author'):
                flash_log(tg_errors['author'])
            elif tg_errors.has_key('captcha'):
                if tg_errors['captcha'].has_key('captchainput'):
                    flash_log("Problem with captcha: %s" % tg_errors['captcha']['captchainput'])
                else:
                    flash_log("Problem with captcha: %s" % tg_errors['captcha'])
            else:
                flash_log(tg_errors)
            return dict(update=update, updates=[], 
                        values={'title':update.title, 'karma' : karma},
                        comment_form=self.comment_captcha_form)
        elif karma not in (0, 1, -1):
            flash_log("Karma must be one of (1, 0, -1)")
            return dict(update=update, updates=[],
                        values={'title' : update.title},
                        comment_form=self.comment_captcha_form)
        if text == 'None': text = None
        update.comment(text, karma, author=author, anonymous=True)
        raise redirect(update.get_url())

    @expose(allow_json=True)
    @error_handler()
    @validate(validators={'karma': validators.Int()})
    @validate(form=comment_form)
    @identity.require(identity.not_anonymous())
    def comment(self, text, title, karma=0, tg_errors=None):
        """ Add a comment to an update.

        Arguments:
        :text: The text of the comment.
        :title: The title of the update comment on.
        :karma: The karma of this comment (-1, 0, 1)

        """
        if tg_errors:
            flash_log(tg_errors)
        elif karma not in (0, 1, -1):
            flash_log("Karma must be one of (1, 0, -1), not %s" % repr(karma))
        else:
            try:
                update = PackageUpdate.byTitle(title)
                if text == 'None': text = None
                update.comment(text, karma)
                if request_format() == 'json':
                    return dict(update=unicode(update))
                raise redirect(update.get_url())
            except SQLObjectNotFound:
                flash_log("Update %s does not exist" % title)
        if request_format() == 'json': return dict()
        raise redirect('/')

    @expose(template='bodhi.templates.comments')
    @paginate('comments', limit=20, max_limit=20, allow_limit_override=True)
    def comments(self):
        data = Comment.select(Comment.q.author != 'bodhi',
                              orderBy=Comment.q.timestamp).reversed()
        return dict(comments=data, num_items=data.count())

    @expose(template='bodhi.templates.confirmation')
    @identity.require(identity.not_anonymous())
    def confirm_delete(self, nvr=None, ok=None, cancel=None):
        update = PackageUpdate.byTitle(nvr)
        if ok:
            flash(_(u"Delete completed"))
            raise redirect('/delete/%s' % update.title)
        if cancel:
            flash(_(u"Delete canceled" ))
            raise redirect(update.get_url())
        return dict(form=self.ok_cancel_form, nvr=nvr)

    #@expose(template='bodhi.templates.obsolete')
    #def obsolete_dialog(self, update):
    #    from bodhi.widgets import ObsoleteForm
    #    package = Package.byName('-'.join(update.split('-')[:-2]))
    #    builds = filter(lambda x: x.updates[0].status in ('testing', 'pending'),
    #                    package.builds)
    #    if not len(builds):
    #        return dict(dialog=None)
    #    return dict(dialog=ObsoleteForm(builds))

    #@expose("json")
    #def obsolete(self, updates, *args, **kw):
    #    """
    #    Called by our ObsoleteForm widget.  This method will
    #    request that any specified updates be marked as obsolete
    #    """
    #    log.debug("obsolete(%s, %s, %s)" % (updates, args, kw))
    #    errors = []
    #    if type(updates) != list:
    #        updates = [updates]
    #    for update in updates:
    #        up = PackageBuild.byNvr(update).update[0]
    #        if not util.authorized_user(up, identity):
    #            msg = "Unauthorized to obsolete %s" % up.title
    #            errors.append(msg)
    #            flash_log(msg)
    #        else:
    #            up.obsolete()
    #    return len(errors) and errors[0] or "Done!"

    @expose(allow_json=True)
    def dist_tags(self):
        return dict(tags=[r.dist_tag for r in Release.select()])

    @expose(allow_json=True)
    @identity.require(identity.in_group("security_respons"))
    def approve(self, update):
        """ Security response team approval for pending security updates """
        try:
            update = PackageUpdate.byTitle(update)
        except SQLObjectNotFound:
            flash_log("%s not found" % update)
            if request_format() == 'json': return dict()
            raise redirect('/')
        update.approved = datetime.utcnow()
        mail.send_admin(update.request, update)
        flash_log("%s has been approved and submitted for pushing to %s" %
                  (update.title, update.request))
        raise redirect(update.get_url())

    @expose(template="bodhi.templates.security")
    @identity.require(identity.in_group("security_respons"))
    def security(self):
        """ Return a list of security updates pending approval """
        updates = PackageUpdate.select(
                    AND(PackageUpdate.q.type == 'security',
                        PackageUpdate.q.status == 'pending',
                        PackageUpdate.q.approved == None),
                    orderBy=PackageUpdate.q.date_submitted)
        return dict(updates=updates)

    @expose(template="bodhi.templates.user")
    @paginate('updates', limit=25, max_limit=20, allow_limit_override=True)
    def user(self, username):
        """ Return a list of updates submitted by a given person """
        updates = PackageUpdate.select(PackageUpdate.q.submitter == username,
                                       orderBy=PackageUpdate.q.date_submitted)
        num_items = updates.count()
        return dict(updates=updates.reversed(),
                    title="%s's %d updates" % (username, num_items),
                    num_items=num_items)

    @expose(allow_json=True)
    def latest_builds(self, package):
        """ Get a list of the latest builds for this package.

        Returns a dictionary of the release dist tag to the latest build.
        """
        builds = {}
        koji = buildsys.get_session()
        for release in Release.select():
            for tag in ('updates-candidate', 'updates-testing', 'updates'):
                tag = '%s-%s' % (release.dist_tag, tag)
                for build in koji.getLatestBuilds(tag, package=package):
                    builds[tag] = build['nvr']
        return builds
