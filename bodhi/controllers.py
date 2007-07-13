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

import sys
import rpm
import mail
import time
import logging
import cherrypy

from kid import Element
from koji import GenericError
from sqlobject import SQLObjectNotFound
from sqlobject.sqlbuilder import AND, OR

from turbogears import (controllers, expose, validate, redirect, identity,
                        paginate, flash, error_handler, validators, config, url,
                        exception_handler)
from turbogears.widgets import TableForm, TextArea, HiddenField, DataGrid

from bodhi import buildsys, util
from bodhi.rss import Feed
from bodhi.new import NewUpdateController, update_form
from bodhi.admin import AdminController
from bodhi.model import (Package, PackageBuild, PackageUpdate, Release,
                         Bugzilla, CVE, Comment)
from bodhi.search import SearchController
from bodhi.xmlrpc import XmlRpcController
from bodhi.widgets import CommentForm
from bodhi.exceptions import (RPMNotFound, DuplicateEntryError,
                              PostgresIntegrityError, SQLiteIntegrityError)

from os.path import isfile, join

log = logging.getLogger(__name__)

from bodhi.errorcatcher import ErrorCatcher

def make_update_link(obj):
    update = hasattr(obj, 'get_url') and obj or obj.update
    link = Element('a', href=url(update.get_url()))
    link.text = update.title
    return link

class Root(controllers.RootController):

    new = NewUpdateController()
    admin = AdminController()
    search = SearchController()
    rpc = XmlRpcController()
    rss = Feed()

    comment_form = CommentForm()

    def exception(self, tg_exceptions=None):
        """ Generic exception handler """
        log.error("Exception thrown: %s" % str(tg_exceptions))
        from bodhi.util import ErrorFormatter
        log.error(dir(tg_exceptions))
        log.error(type(tg_exceptions))
        log.error(tg_exceptions)
        log.error(ErrorFormatter().format(sys.exc_info()))
        flash(str(tg_exceptions))
        raise redirect("/")

    @identity.require(identity.not_anonymous())
    @expose(template='bodhi.templates.welcome')
    def index(self):
        comments = Comment.select(orderBy=Comment.q.timestamp)
        num_comments = comments.count()
        if num_comments:
            if num_comments > 5: comments = comments[:5]
            else: comments = list(comments)
            comment_grid = DataGrid(fields=[('Update', make_update_link),
                                            ('From', lambda row: row.author),
                                            ('Comment', lambda row: row.text)],
                                    default=comments)
        else:
            comment_grid = None

        updates = PackageUpdate.select(orderBy=PackageUpdate.q.date_pushed)
        num_updates = updates.count()
        if num_updates:
            if num_updates > 5: updates = updates[:5]
            else: updates = list(updates)
            update_grid = DataGrid(fields=[('Update', make_update_link),
                                           ('Type', lambda row: row.type),
                                           ('From', lambda row: row.submitter)],
                                   default=updates)
        else:
            update_grid = None

        return dict(now=time.ctime(), update_grid=update_grid,
                    comment_grid=comment_grid)

    @expose(template='bodhi.templates.pkgs')
    @paginate('pkgs', default_order='name', limit=20, allow_limit_override=True)
    def pkgs(self):
        pkgs = Package.select()
        return dict(pkgs=pkgs, num_pkgs=pkgs.count())

    @expose(template="bodhi.templates.login")
    def login(self, forward_url=None, previous_url=None, *args, **kw):
        if not identity.current.anonymous \
            and identity.was_login_attempted() \
            and not identity.get_identity_errors():
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

        cherrypy.response.status=403
        return dict(message=msg, previous_url=previous_url, logging_in=True,
                    original_parameters=cherrypy.request.params,
                    forward_url=forward_url)
    @expose()
    def logout(self):
        identity.current.logout()
        raise redirect('/')

    @identity.require(identity.not_anonymous())
    @expose(template="bodhi.templates.list")
    @paginate('updates', limit=20, allow_limit_override=True)
    def list(self):
        """ List all pushed updates """
        updates = PackageUpdate.select(
                       PackageUpdate.q.status == 'stable',
                       orderBy=PackageUpdate.q.update_id).reversed()
        return dict(updates=updates, num_items=updates.count())

    @expose(template="bodhi.templates.list")
    @identity.require(identity.not_anonymous())
    @paginate('updates', limit=20, allow_limit_override=True)
    def mine(self):
        """ List all updates submitted by the current user """
        updates = PackageUpdate.select(
                    OR(PackageUpdate.q.submitter == util.displayname(identity),
                       PackageUpdate.q.submitter == identity.current.user_name),
                    orderBy=PackageUpdate.q.date_pushed).reversed()
        return dict(updates=updates, num_items=updates.count())

    @identity.require(identity.not_anonymous())
    @expose(template='bodhi.templates.show')
    def show(self, update):
        update = PackageUpdate.byTitle(update)
        update.comments.sort(lambda x, y: cmp(x.timestamp, y.timestamp))
        return dict(update=update, comment_form=self.comment_form)

    @expose()
    @identity.require(identity.not_anonymous())
    def revoke(self, nvr):
        """ Revoke a push request for a specified update """
        update = PackageUpdate.byTitle(nvr)
        if not util.authorized_user(update, identity):
            flash("Cannot revoke an update you did not submit")
            raise redirect(update.get_url())
        flash("%s request revoked" % update.request.title())
        mail.send_admin('revoke', update)
        update.request = None
        raise redirect(update.get_url())

    @expose()
    @identity.require(identity.not_anonymous())
    def move(self, nvr):
        update = PackageUpdate.byTitle(nvr)
        if not util.authorized_user(update, identity):
            flash("Cannot move an update you did not submit")
            raise redirect(update.get_url())
        update.request = 'move'
        flash("Requested that %s be pushed to %s-updates" % (nvr,
              update.release.name))
        mail.send_admin('move', update)
        raise redirect(update.get_url())

    @expose()
    @identity.require(identity.not_anonymous())
    def push(self, nvr):
        """ Submit an update for pushing """
        update = PackageUpdate.byTitle(nvr)
        repo = '%s-updates' % update.release.name
        if not util.authorized_user(update, identity):
            flash("Cannot push an update you did not submit")
            raise redirect(update.get_url())
        if update.type == 'security':
            # Bypass updates-testing
            update.request = 'move'
        else:
            update.request = 'push'
            repo += '-testing'
        msg = "%s has been submitted for pushing to %s" % (nvr, repo)
        log.debug(msg)
        flash(msg)
        mail.send_admin('push', update)
        raise redirect(update.get_url())

    @expose()
    @identity.require(identity.not_anonymous())
    def unpush(self, nvr):
        """ Submit an update for unpushing """
        update = PackageUpdate.byTitle(nvr)
        if not util.authorized_user(update, identity):
            flash("Cannot unpush an update you did not submit")
            raise redirect(update.get_url())
        update.request = 'unpush'
        msg = "%s has been submitted for unpushing" % nvr
        log.debug(msg)
        flash(msg)
        mail.send_admin('unpush', update)
        raise redirect(update.get_url())

    @expose()
    @exception_handler(exception)
    @identity.require(identity.not_anonymous())
    def delete(self, update):
        """ Delete a pending update """
        update = PackageUpdate.byTitle(update)
        if not util.authorized_user(update, identity):
            flash("Cannot delete an update you did not submit")
            raise redirect(update.get_url())
        if not update.pushed:
            map(lambda x: x.destroySelf(), update.comments)
            map(lambda x: x.destroySelf(), update.builds)
            update.destroySelf()
            mail.send_admin('deleted', update)
            msg = "Deleted %s" % update.title
            log.debug(msg)
            flash(msg)
        else:
            flash("Cannot delete a pushed update")
        raise redirect("/pending")

    @identity.require(identity.not_anonymous())
    @expose(template='bodhi.templates.form')
    def edit(self, update):
        """ Edit an update """
        update = PackageUpdate.byTitle(update)
        if not util.authorized_user(update, identity):
            flash("Cannot edit an update you did not submit")
            raise redirect(update.get_url())
        values = {
                'build'     : {'text':update.title, 'hidden':update.title},
                'release'   : update.release.long_name,
                'testing'   : update.status == 'testing',
                'type'      : update.type,
                'notes'     : update.notes,
                'bugs'      : update.get_bugstring(),
                'cves'      : update.get_cvestring(),
                'edited'    : update.title
        }
        return dict(form=update_form, values=values, action=url("/save"))

    @expose()
    @error_handler(new.index)
    @validate(form=update_form)
    @identity.require(identity.not_anonymous())
    def save(self, build, builds, edited, notes, bugs, release,
             type, cves, **kw):
        """
        Save an update.  This includes new updates and edited.
        """
        print "kw = " % kw
        print "save(%s, %s, %s, %s, %s, %s, %s, %s)" % (build, builds, edited,
                                                        notes, bugs, release,
                                                        type, cves)
        if not builds: builds = []
        builds = filter(lambda x: x != u"", [build] + builds)
        flash(builds)

        if not builds:
            flash("Please enter a package-version-release")
            raise redirect('/new')

        # TODO: make this possible
        if edited and edited not in builds:
            flash("You cannot change the package n-v-r after submission")
            raise redirect('/edit/%s' % edited)
        for build in builds:
            if len(build.split('-')) < 3:
                flash("Package must be in name-version-release format")
                raise redirect('/new')

        release = Release.select(Release.q.long_name == release)[0]
        bugs = map(int, bugs.replace(',', ' ').split())
        cves = cves.replace(',', ' ').split()
        update_builds = []
        note = ''

        if not edited: # new update
            koji = buildsys.get_session()
            for build in builds:
                name = util.get_nvr(build)[0]

                # Make sure selected release matches tag for this build
                tag_matches = False
                candidate = '%s-updates-candidate' % release.dist_tag
                try:
                    for tag in koji.listTags(build):
                        log.debug(" * %s" % tag['name'])
                        if tag['name'] == candidate:
                            log.debug("%s built with tag %s" % (build,
                                                                tag['name']))
                            tag_matches = True
                            break
                except GenericError, e:
                    flash("Invalid build: %s" % build)
                    raise redirect('/new')
                if not tag_matches:
                    flash("%s build is not tagged with %s" % (build, candidate))
                    raise redirect('/new')

                # Get the package; if it doesn't exist, create it.
                try:
                    package = Package.byName(name)
                except SQLObjectNotFound:
                    package = Package(name=name)

                ## TODO: FIXME
                #
                # Check for broken update paths.  Make sure this package is
                # newer than the previously released package on this release,
                # as well as on all older releases
                #rel = release
                #while True:
                #    log.debug("Checking for broken update paths in %s" %
                #              rel.name)
                #    for up in PackageUpdate.select(
                #            AND(PackageUpdate.q.releaseID == rel.id,
                #                PackageUpdate.q.packageID == package.id)):
                #        if rpm.labelCompare(util.get_nvr(build),
                #                            util.get_nvr(up.nvr)) < 0:
                #            msg = "Broken update path: %s is older than "
                #                  "existing update %s" % (build, up.nvr)
                #            log.debug(msg)
                #            flash(msg)
                #            raise redirect('/new')
                #    try:
                #        # Check the the previous release
                #        rel = Release.byName(rel.name[:-1] +
                #                             str(int(rel.name[-1]) - 1))
                #    except SQLObjectNotFound:
                #        break

                try:
                    pkgBuild = PackageBuild(nvr=build, package=package)
                    update_builds.append(pkgBuild)
                except (PostgresIntegrityError, SQLiteIntegrityError,
                        DuplicateEntryError):
                    flash("Update for %s already exists" % build)
                    raise redirect('/new')

            try:
                # Create a new update
                p = PackageUpdate(title=','.join(builds), release=release,
                                  submitter=identity.current.user_name,
                                  #subitter=util.displayname(identity),
                                  notes=notes, type=type)
                map(p.addPackageBuild, update_builds)

            except RPMNotFound:
                flash("Cannot find SRPM for update")
                raise redirect('/new')
            except (PostgresIntegrityError, SQLiteIntegrityError,
                    DuplicateEntryError):
                flash("Update for %s already exists" % builds)
                raise redirect('/new')
            log.info("Adding new update %s" % builds)
        else: # edited update
            from datetime import datetime
            log.info("Edited update %s" % edited)
            p = PackageUpdate.byTitle(edited)
            if p.release != release:
                flash("Cannot change update release after submission")
                raise redirect(p.get_url())
            p.set(release=release, date_modified=datetime.now(), notes=notes,
                  type=type)

        # Add/remove the necessary Bugzillas and CVEs
        p.update_bugs(bugs)
        p.update_cves(cves)

        # If there are any CVEs or security bugs, make sure this update is
        # marked as security
        if p.type != 'security':
            for bug in p.bugs:
                if bug.security:
                    p.type = 'security'
                    note += '; Security bug provided, changed update type ' + \
                            'to security'
        if p.cves != [] and (p.type != 'security'):
            p.type = 'security'
            note += '; CVEs provided, changed update type to security'
        if p.type == 'security' and p.request == 'push':
            p.request = 'move'

        if edited:
            mail.send(p.submitter, 'edited', p)
            flash("Update successfully edited" + note)
        else:
            # Notify security team of newly submitted updates
            if p.type == 'security':
                mail.send(config.get('security_team'), 'new', p)
            mail.send(p.submitter, 'new', p)
            flash("Update successfully created" + note)

        raise redirect(p.get_url())

    @expose(template='bodhi.templates.list')
    @identity.require(identity.not_anonymous())
    @paginate('updates', limit=20, allow_limit_override=True)
    def default(self, *args, **kw):
        """
        This method allows for /[(pending|testing)/]<release>[/<update>]
        requests.
        """
        args = [arg for arg in args]
        status = 'stable'
        order = PackageUpdate.q.date_pushed
        template = 'bodhi.templates.list'

        if len(args) and args[0] == 'testing':
            status = 'testing'
            template = 'bodhi.templates.testing'
            del args[0]
        if len(args) and args[0] == 'pending':
            status = 'pending'
            template = 'bodhi.templates.pending'
            order = PackageUpdate.q.date_submitted
            del args[0]
        if not len(args): # /(testing|pending)
            updates = PackageUpdate.select(PackageUpdate.q.status == status,
                                           orderBy=order).reversed()
            return dict(updates=updates, tg_template=template,
                        num_items=updates.count())

        try:
            release = Release.byName(args[0])
            try:
                update = PackageUpdate.select(
                            AND(PackageUpdate.q.releaseID == release.id,
                                PackageUpdate.q.title == args[1],
                                PackageUpdate.q.status == status))[0]
                update.comments.sort(lambda x, y: cmp(x.timestamp, y.timestamp))
                return dict(tg_template='bodhi.templates.show',
                            update=update, updates=[],
                            comment_form=self.comment_form,
                            values={'title' : update.title})
            except SQLObjectNotFound:
                flash("Update %s not found" % args[1])
                raise redirect('/')
            except IndexError: # /[testing/]<release>
                updates = PackageUpdate.select(
                            AND(PackageUpdate.q.releaseID == release.id,
                                PackageUpdate.q.status == status),
                            orderBy=order).reversed()
                return dict(updates=updates, num_items=updates.count(),
                            tg_template=template)
        except SQLObjectNotFound:
            pass

        # /pkg
        try:
            pkg = Package.byName(args[0])
            return dict(tg_template='bodhi.templates.pkg', pkg=pkg, updates=[])
        except SQLObjectNotFound:
            pass

        flash("The path %s cannot be found" % cherrypy.request.path)
        raise redirect("/")

    @expose()
    @error_handler()
    @validate(form=comment_form)
    @validate(validators={ 'karma' : validators.Int() })
    @identity.require(identity.not_anonymous())
    def comment(self, text, title, karma, tg_errors=None):
        update = PackageUpdate.byTitle(title)
        if tg_errors:
            flash(tg_errors)
        else:
            comment = Comment(text=text, karma=karma,
                              author=identity.current.user_name,
                              update=update)
            update.karma += karma
            mail.send(update.submitter, 'comment', update)
        raise redirect(update.get_url())

    @expose(template='bodhi.templates.text')
    def mail_notice(self, nvr, *args, **kw):
        update = PackageUpdate.byTitle(nvr)
        (subject, body) = mail.get_template(update)
        return dict(text=body, title=subject)
