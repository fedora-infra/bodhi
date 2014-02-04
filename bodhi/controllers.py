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
import time
import logging
import cherrypy
import xmlrpclib
import textwrap

from cgi import escape
from koji import GenericError, TagError
from datetime import datetime
from sqlobject import SQLObjectNotFound
from sqlobject.sqlbuilder import AND, OR

from turbogears import (controllers, expose, validate, redirect, identity,
                        paginate, flash, error_handler, validators, config)
from turbogears import url as tg_url
from turbogears.widgets import DataGrid

try:
    from fedora.tg.tg1utils import request_format
except ImportError:
    from fedora.tg.util import request_format

from fedora.tg.controllers import login as fc_login
from fedora.tg.controllers import logout as fc_logout

from bodhi import buildsys, util
from bodhi.rss import Feed
from bodhi.new import NewUpdateController, update_form
from bodhi.util import make_update_link, make_type_icon, make_karma_icon, link, make_release_link, make_submitter_link
from bodhi.util import flash_log, get_pkg_pushers, make_request_icon
from bodhi.util import json_redirect, url, get_nvr
from bodhi.admin import AdminController
from bodhi.metrics import MetricsController
from bodhi.model import (Package, PackageBuild, PackageUpdate, Release,
                         Bugzilla, CVE, Comment)
from bodhi.search import SearchController
from bodhi.overrides import BuildRootOverrideController
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
    override = BuildRootOverrideController()

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

        notice = config.get('frontpage_notice')
        if notice:
            flash(notice)

        # { 'Title' : [SelectResults, [(row, row_callback),]], ... }
        grids = {
            'comments' : [
                Comment.select(
                    AND(Comment.q.author != 'bodhi',
                        Comment.q.author != 'autoqa'),
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
                    ('Release', make_release_link),
                    ('Status', lambda row: row.status),
                    ('Type', make_type_icon),
                    ('Request', make_request_icon),
                    ('Karma', make_karma_icon),
                    ('Submitter', make_submitter_link),
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
                    ('Release', make_release_link),
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
        if config.get('identity.provider') in ('sqlobjectcsrf', 'jsonfas2'):
            data = fc_login(forward_url, previous_url, args, kw)
            data['tg_template'] = 'genshi:bodhi.templates.login'
            return data

        if not identity.current.anonymous and identity.was_login_attempted() \
           and not identity.get_identity_errors():
            if request_format() == 'json':
                return dict(user=identity.current.user)
            raise redirect(forward_url)

        forward_url=None
        previous_url= cherrypy.request.path

        if identity.was_login_attempted():
            msg="The credentials you supplied were not correct or did not grant access to this resource."
        elif identity.get_identity_errors():
            msg="You must provide your credentials before accessing this resource."
        else:
            msg="Please log in."
            forward_url= cherrypy.request.headers.get("Referer", "/")

        # This seems to be the cause of some bodhi-client errors
        cherrypy.response.status=403
        return dict(message=msg, previous_url=previous_url, logging_in=True,
                    original_parameters=cherrypy.request.params,
                    forward_url=forward_url)

    @expose(allow_json=True)
    def logout(self):
        if config.get('identity.provider') in ('sqlobjectcsrf', 'jsonfas2'):
            return fc_logout()

        identity.current.logout()
        raise redirect('/')

    @expose('json')
    @validate(validators={'builds': validators.UnicodeString()})
    def get_updates_from_builds(self, builds=''):
        """Given a list of build nvrs, return the corresponding updates.

        :builds: A space-delimited list of builds in the format of
                 name-version-release

        :returns: A dictionary in the format of {build: update_data}
        """
        updates = {}
        for build in builds.split():
            try:
                b = PackageBuild.byNvr(build)
                for update in b.updates:
                    updates[build] = update.__json__()
            except SQLObjectNotFound:
                pass
        return updates

    @expose(template="bodhi.templates.list", allow_json=True)
    @paginate('updates', limit=25, max_limit=None)
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
            'count_only': validators.StringBool(),
            'created_since': validators.UnicodeString(),
            'pushed_since': validators.UnicodeString(),
            'request': validators.UnicodeString(),
            })
    def list(self, release=None, bugs=None, cves=None, status=None, type_=None,
             package=None, mine=False, get_auth=False, username=None,
             start_date=None, end_date=None, count_only=False,
             created_since=None, pushed_since=None, modified_since=None, request=None, **kw):
        """ Return a list of updates based on given parameters """
        log.debug('list(%s)' % locals())
        query = []
        updates = []
        orderBy = PackageUpdate.q.date_submitted

        # Check the identity first of all
        if mine and identity.current.anonymous:
            cherrypy.response.status=401
            return dict(updates=[], num_items=0, title='0 updates found')

        # If no arguments are specified, return the most recent updates
        if not release and not bugs and not cves and not status and not type_ \
           and not package and not mine and not username and not created_since \
           and not pushed_since and not modified_since and not request \
           and not start_date and not end_date:
            log.debug("No arguments, returning latest")
            updates = PackageUpdate.select(orderBy=orderBy).reversed()
            num_items = updates.count()
            return dict(updates=updates, num_items=num_items,
                        title="%d %s found" % (num_items, num_items == 1 and
                                               'update' or 'updates'))

        if release:
            # TODO: if a specific release is requested along with get_auth,
            #       and it is not found in PackageUpdate we should add.
            #       another value to the output which indicates if the.
            #       logged in user is allowed to create a new update for.
            #       this package
            rel = None
            try:
                rel = Release.byName(release.upper())
            except SQLObjectNotFound:
                # Make names like EL-5 and el5 both find the right release
                for r in Release.select():
                    if r.name.upper().replace('-', '') == release.replace('-', '').upper():
                        rel = r
                        break
                if not rel:
                    # Try by dist tag
                    rel = Release.select(Release.q.dist_tag == release)
                    if rel.count():
                        rel = rel[0]
                    else:
                        err = 'Unknown release %r' % release
                        return dict(error=err, num_items=0, title=err, updates=[])
            release = rel

        # If we're looking for bugs specifically (#610)
        if bugs and not status and not type_ and not package \
                and not mine and not username and not created_since \
                and not pushed_since and not modified_since \
                and not request and not start_date and not end_date:
            updates = []
            bugs = bugs.replace('#', '').split(',')
            for bug in bugs:
                try:
                    bug = Bugzilla.byBz_id(int(bug))
                    for update in bug.updates:
                        if release:
                            if update.release != release:
                                continue
                        updates.append(update)
                except (SQLObjectNotFound, ValueError):
                    pass
            if request_format() == 'json':
                update = [update.__json__() for update in updates]
            num_items = len(updates)
            return dict(updates=updates, num_items=num_items,
                        title='%d %s found' % (num_items,
                            num_items == 1 and 'update' or 'updats'))

        try:
            if release:
                query.append(PackageUpdate.q.releaseID == release.id)
            if status:
                query.append(PackageUpdate.q.status == status)
                if status == 'stable':
                    orderBy = PackageUpdate.q.date_pushed
            if type_:
                query.append(PackageUpdate.q.type == type_)
            if request:
                query.append(PackageUpdate.q.request == request)
            if mine:
                query.append(
                    PackageUpdate.q.submitter == identity.current.user_name)
            if username:
                query.append(PackageUpdate.q.submitter == username)
            if created_since:
                created_since = datetime(*time.strptime(created_since,
                       '%Y-%m-%d %H:%M:%S')[:-2])
                query.append(PackageUpdate.q.date_submitted >= created_since)
            if modified_since:
                modified_since = datetime(*time.strptime(modified_since,
                       '%Y-%m-%d %H:%M:%S')[:-2])
                query.append(PackageUpdate.q.date_modified >= modified_since)
            if pushed_since:
                pushed_since = datetime(*time.strptime(pushed_since,
                       '%Y-%m-%d %H:%M:%S')[:-2])
                query.append(PackageUpdate.q.date_pushed >= pushed_since)
            if start_date:
                start_date = datetime(*time.strptime(start_date,
                    '%Y-%m-%d %H:%M:%S')[:-2])
                query.append(PackageUpdate.q.date_pushed >= start_date)
            if end_date:
                end_date = datetime(*time.strptime(end_date,
                    '%Y-%m-%d %H:%M:%S')[:-2])
                query.append(PackageUpdate.q.date_pushed <= end_date)

            updates = PackageUpdate.select(AND(*query),
                                           orderBy=orderBy).reversed()

            if count_only:
                return dict(num_items=updates.count(), updates=[])

            # The package argument may be an update, build or package.
            if package:
                try:
                    try:
                        update = PackageUpdate.byTitle(package)
                    except SQLObjectNotFound:
                        update = PackageUpdate.select(PackageUpdate.q.updateid==package)
                        if update.count():
                            update = update[0]
                        else:
                            raise SQLObjectNotFound
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
                            update_ids = [update.id for update in updates]
                            updates = filter(lambda up: up.id in update_ids,
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
            #if bugs:
            #    results = []
            #    for bug in map(Bugzilla.byBz_id, map(int, bugs.split(','))):
            #        map(results.append,
            #            filter(lambda x: bug in x.bugs, updates))
            #    updates = results
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
    @paginate('updates', limit=25, max_limit=None)
    def mine(self):
        """ List all updates submitted by the current user """
        updates = PackageUpdate.select(
                       PackageUpdate.q.submitter == identity.current.user_name,
                    orderBy=PackageUpdate.q.date_submitted).reversed()
        return dict(updates=updates, title='%s\'s updates' %
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
        if update.request == 'testing':
            update.remove_tag(update.release.pending_testing_tag)
        elif update.request == 'stable':
            update.remove_tag(update.release.pending_stable_tag)
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
            # Remove the appropriate pending tags
            if self.request == 'testing':
                self.remove_tag(self.release.pending_testing_tag)
            elif self.request == 'stable':
                self.remove_tag(self.release.pending_stable_tag)
            if not update.pushed:
                msg = "Deleted %s" % update.title
                update.expire_buildroot_overrides()
                update.untag()
                map(lambda x: x.destroySelf(), update.comments)
                for build in update.builds:
                    if len(build.updates) == 1:
                        build.destroySelf()
                update.destroySelf()
                flash_log(msg)
                mail.send_admin('deleted', update)
                mail.send(update.people_to_notify(), 'deleted', update)
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
                'testing'   : update.status == 'testing',
                'request'   : str(update.request).title(),
                'type_'     : update.type,
                'notes'     : update.notes,
                'bugs'      : update.get_bugstring(),
                'edited'    : update.title,
                'close_bugs': update.close_bugs,
                'stable_karma' : update.stable_karma,
                'unstable_karma' : update.unstable_karma,
                'suggest_reboot' : update.builds[0].package.suggest_reboot,
                'autokarma' : update.stable_karma != 0 and update.unstable_karma != 0,
        }
        log.debug("values = %s" % values)
        if update.status == 'testing':
            flash("Adding or removing builds from this update will move it back to a pending state.")
        return dict(form=update_form, values=values, action=url("/save"),
                    title='Edit Update')

    @expose(allow_json=True)
    @error_handler(new.index)
    @json_redirect
    @validate(form=update_form)
    @identity.require(identity.not_anonymous())
    def save(self, builds, type_, notes, bugs, close_bugs=False, edited=False,
             request='testing', suggest_reboot=False, inheritance=False,
             autokarma=False, stable_karma=3, unstable_karma=-3, **kw):
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
                'suggest_reboot': suggest_reboot and 'True' or '',
        }

        # Basic sanity checks
        if not builds:
            flash_log("Error: Didn't receive any builds")
            raise InvalidUpdateException(params)
        if not type_ or type_ not in config.get('update_types'):
            flash_log('Unknown update type: %s.  Valid types are: %s' % (
                      type_, config.get('update_types')))
            raise InvalidUpdateException(params)
        if request not in ('testing', 'stable', None):
            flash_log('Unknown request: %s.  Valid requests are: testing, '
                      'stable, None' % request)
        if autokarma:
            if stable_karma < 1:
                flash_log("Stable karma must be at least 1.")
                raise InvalidUpdateException(params)
            if stable_karma <= unstable_karma:
                flash_log("Stable karma must be higher than unstable karma.")
                raise InvalidUpdateException(params)
        if not notes or notes == "Here is where you give an explanation of your update.":
            flash_log('Error: You must supply details for this update')
            raise InvalidUpdateException(params)

        # Check for conflicting builds
        for build in builds:
            build_nvr = get_nvr(build)
            for other_build in builds:
                other_build_nvr = get_nvr(other_build)
                if build == other_build:
                    continue
                if (build_nvr[0] == other_build_nvr[0] and
                    build_nvr[2].split('.')[-1] == other_build_nvr[2].split('.')[-1]):
                    flash_log("Unable to save update with conflicting builds of "
                              "the same package: %s and %s. Please remove one "
                              "and try again." % (build, other_build))
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
                    'nvr'      : util.get_nvr(build),
                    'tags'     : [],
                    'people'   : [],
                    'releases' : set(),
            }
            pkg = buildinfo[build]['nvr'][0]
            try:
                buildinfo[build]['tags'] = [tag['name'] for tag in
                                            koji.listTags(build)]
            except GenericError:
                flash_log("Invalid build: %s" % build)
                raise InvalidUpdateException(params)
            try:
                # Grab a list of committers.
                pkgdb_args = {
                        'collectionName': 'Fedora',
                        'collectionVersion': 'devel',
                }
                tags = buildinfo[build]['tags']
                for release in Release.select():
                    if release.candidate_tag in tags or \
                       release.testing_tag in tags:
                        pkgdb_args['collectionName'] = release.collection_name
                        pkgdb_args['collectionVersion'] = str(release.get_version())
                        buildinfo[build]['release'] = release
                        break

                people, groups = get_pkg_pushers(pkg, **pkgdb_args)
                people = people[0] # we only care about committers, not watchers
                buildinfo[build]['people'] = people
            except urllib2.URLError:
                flash_log("Unable to access the package database.  Please "
                          "notify an administrator in #fedora-admin")
                raise InvalidUpdateException(params)
            except Exception, e:
                log.exception(e)
                if 'dbname' in str(e):
                    flash_log('Error: database connection limit reached.  Please try again later')
                else:
                    flash_log(str(e))
                raise InvalidUpdateException(params)

            # Verify that the user is either in the committers list, or is
            # a member of a groups that has privileges to commit to this package
            if not identity.current.user_name in people and \
               not filter(lambda x: x in identity.current.groups, groups[0]) and \
               not filter(lambda group: group in identity.current.groups,
                          config.get('admin_groups').split()):
                flash_log("%s does not have commit access to %s" % (
                          identity.current.user_name, pkg))
                raise InvalidUpdateException(params)

        # If we're editing an update, unpush it first so we can assume all
        # of the builds are tagged as update candidates
        edited_testing_update = False
        removed_builds = []
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

            # Determine which builds have been added or removed
            edited_builds = [build.nvr for build in edited.builds]
            new_builds = []
            for build in builds:
                if build not in edited_builds:
                    new_builds.append(build)
            for build in edited_builds:
                if build not in builds:
                    removed_builds.append(build)

            # If we're adding/removing builds, ensure that they aren't
            # currently being pushed
            if edited.currently_pushing:
                if new_builds or removed_builds:
                    if edited.request == 'stable':
                        flash_log('Unable to edit update that is currently '
                                  'being pushed to the stable repository')
                        raise InvalidUpdateException(params)
                    elif edited.request == 'testing':
                        flash_log('Unable to add or remove builds from an '
                                  'update that is currently being pushed to the '
                                  'testing repository')
                        log.debug('%s tagged with %s but expecting %s' % (
                            builds[0], buildinfo[builds[0]]['tags'],
                            edited.get_build_tag()))
                        raise InvalidUpdateException(params)
            else:
                if edited.get_build_tag() not in buildinfo[builds[0]]['tags'] and not edited.request:
                    log.warn('Mismatched tags for an update without a request')
                    log.debug('Implied tag: %s\nActual tags: %s' % (
                        edited.get_implied_build_tag(),
                        buildinfo[builds[0]]['tags']))

            # Add the appropriate pending tags
            for build in new_builds:
                try:
                    if edited.request == 'testing':
                        koji.tagBuild(edited.release.pending_testing_tag,
                                        build, force=True)
                    elif edited.request == 'stable':
                        koji.tagBuild(edited.release.pending_stable_tag,
                                        build, force=True)
                except (TagError, GenericError),  e:
                    log.exception(e)

            for build in removed_builds:
                try:
                    if edited.request == 'stable':
                        koji.untagBuild(edited.release.pending_stable_tag,
                                        build, force=True)
                    elif edited.request == 'testing':
                        koji.untagBuild(edited.release.pending_testing_tag,
                                        build, force=True)
                except (TagError, GenericError),e :
                    log.debug(str(e))

            # Comment on the update with details of added/removed builds
            if new_builds or removed_builds:
                comment = '%s has edited this update. ' % identity.current.user_name
                if new_builds:
                    comment += 'New build(s): %s. ' % ', '.join(new_builds)
                if removed_builds:
                    comment += 'Removed build(s): %s.' % ', '.join(removed_builds)
                edited.comment(comment, karma=0, author='bodhi')

                # Make sure all builds are tagged as updates-candidate
                # and bring the update back to a pending state
                edited.unpush()
                request = 'testing'

                # Refresh the tags for these builds
                for build in edited.builds:
                    if build.nvr in buildinfo:
                        buildinfo[build.nvr]['tags'] = [tag['name'] for tag in
                                                        koji.listTags(build.nvr)]
            else:
                # No need to change the bodhi state or koji tag
                edited_testing_update = True

        # Make sure all builds are tagged appropriately.  We also determine
        # which builds get pushed for which releases, based on the tag.
        for build in builds:
            valid = False
            tags = buildinfo[build]['tags']

            # Determine which release this build is a candidate for
            for tag in tags:
                rel = None
                for r in Release.select():
                    if edited_testing_update and tag == r.testing_tag:
                        rel = r
                        break
                    if tag == r.candidate_tag:
                        rel = r
                        break
                if rel:
                    log.debug("Adding %s for %s" % (rel.name, build))
                    if edited:
                        if edited.release != rel:
                            valid = False
                            flash_log("Cannot add a %s build to a %s update. "
                                      "Please create a new update for %s" % (
                                      rel.name, edited.release.name, build))
                            raise InvalidUpdateException(params)

                    if not releases.has_key(rel):
                        releases[rel] = []
                    if build not in releases[rel]:
                        releases[rel].append(build)
                    buildinfo[build]['releases'].add(rel)
                    valid = True
                else:
                    log.debug("%s not a candidate tag" % tag)

            # if we're using build inheritance, iterate over each release
            # looking to see if the latest build in its candidate tag
            # matches the user-specified build
            if inheritance:
                log.info("Following build inheritance")
                for rel in Release.select():
                    b = koji.listTagged(rel.candidate_tag,
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
            # OBSOLETED BY AUTOQA
            #log.info("Checking for broken update paths")
            #for release in buildinfo[build]['releases']:
            #    tags = ['dist-rawhide', release.dist_tag, release.stable_tag]
            #    for tag in tags:
            #        pkg = buildinfo[build]['nvr'][0]
            #        for oldBuild in koji.listTagged(tag, package=pkg,
            #                                        latest=True):
            #            if rpm.labelCompare(util.build_evr(kojiBuild),
            #                                util.build_evr(oldBuild)) < 0:
            #                flash_log("Broken update path: %s is older "
            #                          "than %s in %s" % (kojiBuild['nvr'],
            #                          oldBuild['nvr'], tag))
            #                raise InvalidUpdateException(params)

        # Remove the appropriate builds
        for build in removed_builds:
            b = PackageBuild.byNvr(build)
            edited.removePackageBuild(b)
            if len(b.updates) == 0:
                b.destroySelf()

        # Create all of the PackageBuild objects, obsoleting any older updates
        for build in builds:
            nvr = buildinfo[build]['nvr']
            try:
                package = Package.byName(nvr[0])
            except SQLObjectNotFound:
                package = Package(name=nvr[0])

            # Update our ACL cache for this pkg
            package.committers = buildinfo[build]['people']

            # Set the reboot suggested flag
            package.suggest_reboot = suggest_reboot

            # If new karma thresholds are specified, save them
            if not autokarma:
                stable_karma = unstable_karma = 0

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
                if oldBuild.nvr == build:
                    continue
                for update in oldBuild.updates:
                    if update.status not in ('pending', 'testing') or \
                       update.request == 'stable' or \
                       update.release not in buildinfo[build]['releases'] or \
                       update in pkgBuild.updates or \
                       (edited and oldBuild in edited.builds):
                        obsoletable = False
                        break
                    if rpm.labelCompare(util.get_nvr(oldBuild.nvr), nvr) < 0:
                        log.debug("%s is newer than %s" % (nvr, oldBuild.nvr))
                        obsoletable = True
                    # Ensure the same number of builds are present
                    if len(update.builds) != len(releases[update.release]):
                        obsoletable = False
                        break
                    # Ensure that all of the packages in the old update are
                    # present in the new one.
                    pkgs = [get_nvr(b)[0] for b in releases[update.release]]
                    for _build in update.builds:
                        if _build.package.name not in pkgs:
                            obsoletable = False
                            break
                    if update.request == 'testing':
                        # if the update has a testing request, but has yet to
                        # be pushed, obsolete it
                        if update.currently_pushing:
                            obsoletable = False
                if obsoletable:
                    log.info('%s is obsoletable' % oldBuild.nvr)
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
            try:
                # Encode our unicode strings to UTF-8 before they hit SQLObject
                # This has fixed numerous tickets, such as #288
                notes = notes.encode('utf-8', 'replace')
                type_ = type_.encode('utf8', 'replace')
            except Exception, e:
                log.exception(e)
                log.error('Unable to convert our update to utf-8; passing '
                          'unicode strings to SQLObject.')

            old_type = None
            if edited:
                old_type = edited.type
                update = edited
                log.debug("Editing update %s" % edited.title)
                update.set(release=release, date_modified=datetime.utcnow(),
                           notes=notes, type=type_, title=','.join(builds),
                           stable_karma=stable_karma, unstable_karma=unstable_karma,
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
                    update = PackageUpdate(title=','.join(builds),
                                           release=release,
                                           submitter=identity.current.user_name,
                                           notes=notes, type=type_,
                                           close_bugs=close_bugs,
                                           stable_karma=stable_karma,
                                           unstable_karma=unstable_karma)
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
                original_bugs = [bug.bz_id for bug in update.bugs]
                update.update_bugs(bugs)
            except ValueError, e:
                note.insert(0, "Unable to access one or more bugs: %s" % e)
            except Exception, e:
                log.error("Unknown exception thrown while updating bug list!")
                note.insert(0, "Unable to access one or more bugs.  Exception: %s" % e)

            # If there are any security bugs, make sure this update is
            # properly marked as a security update
            if update.type != 'security':
                for bug in update.bugs:
                    if bug.security:
                        update.type = 'security'
                        break

            # Append links to unit tests in the update notes
            if config.get('query_wiki_test_cases'):
                try:
                    test_cases = []
                    for build in update.builds:
                        test_cases.extend(build.package.get_test_cases())
                    # HACK: shove the unit tests into this PickleCol
                    if test_cases:
                        if not update.nagged:
                            nagged = {}
                        else:
                            nagged = update.nagged
                        nagged['test_cases'] = test_cases
                        update.nagged = nagged
                except Exception, e:
                    log.exception(e)

            # Send out mail notifications
            if edited:
                #mail.send(update.get_maintainers(), 'edited', update)
                mail.send(update.submitter, 'edited', update)
                note.insert(0, "Update successfully edited")

                # Update any newly added bugs
                for bug in bugs:
                    try:
                        bug = int(bug)
                    except ValueError: # bug alias
                        bugzilla = Bugzilla.get_bz()
                        bug = bugzilla.getbug(bug).bug_id
                    if bug not in original_bugs:
                        log.debug("Updating newly added bug: %s" % bug)
                        if update.release.collection_name == 'Fedora EPEL':
                            repo = 'epel-testing'
                        else:
                            repo = 'updates-testing'
                        try:
                            Bugzilla.byBz_id(bug).add_comment(update,
                                "%s has been submitted as an update for %s.\n%s"
                                % (update.get_title(delim=', '),
                                   release.long_name,
                                   config.get('base_address') +
                                   tg_url(update.get_url())))
                        except SQLObjectNotFound:
                            log.debug('Bug #%d not found in our database' % bug)

                # If this update was changed to a security update, notify
                # the security team.
                if old_type != 'security' and update.type == 'security':
                    mail.send(config.get('security_team'), 'security', update)
            else:
                # Notify security team of newly submitted security updates
                if update.type == 'security':
                    mail.send(config.get('security_team'), 'security', update)
                #mail.send(update.get_maintainers(), 'new', update)
                mail.send(update.submitter, 'new', update)
                note.insert(0, "Update successfully created")

                # Comment on all bugs
                for bug in update.bugs:
                    if update.release.collection_name == 'Fedora EPEL':
                        repo = 'epel-testing'
                    else:
                        repo = 'updates-testing'
                    bug.add_comment(update,
                        "%s has been submitted as an update for %s.\n%s" %
                            (update.title, release.long_name,
                             config.get('base_address') +
                             tg_url(update.get_url())))

            # If a request is specified, make it.  By default we're submitting
            # new updates directly into testing
            if request and request != update.request:
                try:
                    update.set_request(request, pathcheck=False)
                except InvalidRequest, e:
                    flash_log(str(e))
                    raise InvalidUpdateException(params)

            # Disable pushing critpath updates straight to stable
            # XXX: This block shouldn't be necessary, as the set_request call
            # above should handle this logic.  Keeping it here for another
            # release to see if this gets hit.
            if config.get('critpath.num_admin_approvals'):
                if (update.request == 'stable' and update.critpath and
                    not update.critpath_approved):
                    update.request = 'testing'
                    log.error("Unapproved critpath request is 'stable'.  "
                              "This shouldn't happen!")
                    note.append('This critical path update has not '
                                'yet been approved for pushing to the stable '
                                'repository.  It must first reach a karma '
                                'of %d, consisting of %d positive karma from '
                                'proventesters, along with %d additional '
                                'karma from the community.' % (
                        config.get('critpath.min_karma'),
                        config.get('critpath.num_admin_approvals'),
                        config.get('critpath.min_karma') -
                        config.get('critpath.num_admin_approvals')))

        flash_log('. '.join(note))

        if request_format() == 'json':
            return dict(updates=updates)
        elif len(updates) > 1:
            return dict(tg_template='bodhi.templates.list',
                        updates=updates, num_items=0,
                        title='Updates sucessfully created!')
        else:
            if updates:
                raise redirect(updates[0].get_url())
            else:
                raise redirect('/')

    @expose(template='bodhi.templates.list')
    @paginate('updates', limit=25, max_limit=None)
    def default(self, *args, **kw):
        """
        This method allows for the following requests

            /Package.name
            /PackageUpdate.title
            /PackageUpdate.updateid/*
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

        # /PackageUpdate.updateid/*
        if args:
            update = PackageUpdate.select(PackageUpdate.q.updateid == args[0])
            if update.count():
                update = update[0]
                return dict(tg_template='bodhi.templates.show',
                            update=update, comment_form=form,
                            updates=[], values={'title': update.title})

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
    #@validate(validators={'karma': validators.Int()})
    @validate(form=comment_captcha_form)
    def captcha_comment(self, text, title, author, karma, captcha=None,
                        tg_errors=None):
        if not captcha:
            captcha = {}
        try:
            karma = int(karma)
        except:
            karma = None
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
                if 'captcha' in tg_errors:
                    if 'author' in tg_errors:
                        flash_log('%s %s' % (tg_errors['captcha'],
                                             tg_errors['author']))
                    elif isinstance(tg_errors['captcha'], dict) and \
                            tg_errors['captcha'].has_key('captchainput'):
                        flash_log("Problem with captcha: %s" %
                                  tg_errors['captcha']['captchainput'])
                    else:
                        flash_log("Problem with captcha: %s" %
                                  tg_errors['captcha'])
                else:
                    flash_log("Problem with captcha: %s" % tg_errors)
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
        if text == 'None':
            text = None
        else:
            try: # Python 2.6+
                text = textwrap.TextWrapper(width=80,
                    break_long_words=False,
                    break_on_hyphens=False).fill(text)
            except TypeError: # Python 2.4
                text = textwrap.TextWrapper(width=80,
                    break_long_words=False).fill(text)
        update.comment(text, karma, author=author, anonymous=True)
        raise redirect(update.get_url())

    @expose(allow_json=True)
    @error_handler()
    @validate(validators={
        'karma': validators.Int(),
        'email': validators.StringBool()
    })
    @validate(form=comment_form)
    @identity.require(identity.not_anonymous())
    def comment(self, text, title, karma=0, tg_errors=None, email=True):
        """ Add a comment to an update.

        Arguments:
        :text: The text of the comment.
        :title: The title of the update comment on.
        :karma: The karma of this comment (-1, 0, 1)
        :email: Whether or not this comment should trigger email notifications

        """
        try:
            karma = int(karma)
        except:
            pass
        if tg_errors:
            flash_log(tg_errors)
        elif karma not in (0, 1, -1):
            flash_log("Karma must be one of (1, 0, -1), not %s" % repr(karma))
        else:
            try:
                try:
                    update = PackageUpdate.byTitle(title)
                except SQLObjectNotFound:
                    update = PackageUpdate.select(PackageUpdate.q.updateid == title)
                    if update.count():
                        update = update[0]
                    else:
                        raise SQLObjectNotFound
                if text == 'None':
                    text = None
                else:
                    try: # Python 2.6+
                        text = textwrap.TextWrapper(width=80,
                            break_long_words=False,
                            break_on_hyphens=False).fill(text)
                    except TypeError: # Python 2.4
                        text = textwrap.TextWrapper(width=80,
                            break_long_words=False).fill(text)
                update.comment(text, karma, email=email)
                if request_format() == 'json':
                    return dict(update=update.__json__())
                raise redirect(update.get_url())
            except SQLObjectNotFound:
                flash_log("Update %s does not exist" % title)
        if request_format() == 'json': return dict()
        raise redirect('/')

    @expose(template='bodhi.templates.comments')
    @paginate('comments', limit=25, max_limit=None)
    def comments(self, user=None):
        if user:
            data = Comment.select(Comment.q.author == user,
                                  orderBy=Comment.q.timestamp).reversed()
        else:
            data = Comment.select(Comment.q.author != 'bodhi',
                                  orderBy=Comment.q.timestamp).reversed()
        return dict(comments=data, num_items=data.count())

    @expose(template='bodhi.templates.confirmation')
    @identity.require(identity.not_anonymous())
    def confirm_delete(self, nvr=None, ok=None, cancel=None):
        update = PackageUpdate.byTitle(nvr)
        if ok:
            flash(u"Delete completed")
            raise redirect('/delete/%s' % update.title)
        if cancel:
            flash(u"Delete canceled")
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
    def candidate_tags(self):
        return dict(tags=[r.candidate_tag for r in Release.select()])

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

    @expose(template="bodhi.templates.user", allow_json=True)
    @paginate('updates', limit=25, max_limit=25)
    def user(self, username):
        """ Return a list of updates submitted by a given person """
        updates = PackageUpdate.select(PackageUpdate.q.submitter == username,
                                       orderBy=PackageUpdate.q.date_submitted)
        num_items = updates.count()
        return dict(updates=updates.reversed(),
                    username=username,
                    num_items=num_items)

    @expose(allow_json=True)
    def latest_builds(self, package):
        """ Get a list of the latest builds for this package.

        Returns a dictionary of the release dist tag to the latest build.
        """
        builds = {}
        koji = buildsys.get_session()
        for release in Release.select():
            for tag in (release.candidate_tag, release.testing_tag, release.stable_tag):
                for build in koji.getLatestBuilds(tag, package=package):
                    builds[tag] = build['nvr']
        return builds

    @expose(template='bodhi.templates.critpath', allow_json=True)
    @validate(validators={
        'untested': validators.StringBool(),
        'unapproved': validators.StringBool(),
    })
    @paginate('updates', limit=1000, max_limit=None)
    def critpath(self, untested=False, unapproved=False, release=None, *args,
            **kw):
        updates = []
        title = '%d %sCritical Path Updates'
        query = [PackageUpdate.q.status != 'obsolete']
        release_name = None
        if release and release != u'None':
            try:
                release = Release.byName(release)
            except SQLObjectNotFound:
                flash('Unknown release: %s' % release)
                raise redirect('/')
            releases = [release]
            release_name = release.name
            title = title + ' for ' + release.long_name
        else:
            releases = Release.select()
        if untested or unapproved:
            query.append(PackageUpdate.q.status != 'stable')
        for update in PackageUpdate.select(
                AND(OR(*[PackageUpdate.q.releaseID == release.id
                    for release in releases]),
                    *query),
                orderBy=PackageUpdate.q.date_submitted).reversed():
            if update.critpath:
                if untested or unapproved:
                    if not update.critpath_approved:
                        updates.append(update)
                else:
                    updates.append(update)
        num_items = len(updates)
        return dict(updates=updates, num_items=num_items,
                    title=title % (num_items, (untested or unapproved) and
                        'Unapproved ' or ''),
                    unapproved=unapproved or untested,
                    release_name=release_name)

    @expose(allow_json=True)
    def releases(self):
        return dict(releases=[release.__json__() for release in Release.select()])
