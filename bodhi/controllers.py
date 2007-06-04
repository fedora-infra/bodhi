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
import util
import logging
import cherrypy

from koji import GenericError
from sqlobject import SQLObjectNotFound
from sqlobject.sqlbuilder import AND, OR

from turbogears import (controllers, expose, validate, redirect, identity,
                        paginate, flash, error_handler, validators, config, url,
                        exception_handler)
from turbogears.widgets import TableForm, TextArea, HiddenField

from bodhi.new import NewUpdateController, update_form
from bodhi.admin import AdminController
from bodhi.model import Package, PackageUpdate, Release, Bugzilla, CVE, Comment
from bodhi.search import SearchController
from bodhi.xmlrpc import XmlRpcController
from bodhi import buildsys
from bodhi.exceptions import RPMNotFound

from os.path import isfile, join

try:
    from sqlobject.dberrors import DuplicateEntryError
except ImportError:
    # Handle pre-DuplicateEntryError versions of SQLObject
    class DuplicateEntryError(Exception): pass

from psycopg2 import IntegrityError as PostgresIntegrityError
try:
    from pysqlite2.dbapi2 import IntegrityError as SQLiteIntegrityError
except:
    from sqlite import IntegrityError as SQLiteIntegrityError

log = logging.getLogger(__name__)

class Root(controllers.RootController):

    new = NewUpdateController()
    admin = AdminController()
    search = SearchController()
    rpc = XmlRpcController()

    comment_form = TableForm(fields=[TextArea(name='text', label='',
                                              validator=validators.NotEmpty(),
                                              rows=3, cols=40),
                                     HiddenField(name='nvr')],
                             submit_text='Add Comment', action=url('/comment'))

    def exception(self, tg_exceptions=None):
        """ Generic exception handler """
        log.error("Exception thrown: %s" % str(tg_exceptions))
        flash(str(tg_exceptions))
        raise redirect("/")

    @identity.require(identity.not_anonymous())
    @expose(template='bodhi.templates.welcome')
    def index(self):
        return dict()

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
                    OR(PackageUpdate.q.submitter == '%s <%s>' % (
                            identity.current.user.display_name,
                            identity.current.user.user['email']),
                       PackageUpdate.q.submitter == identity.current.user_name),
                    orderBy=PackageUpdate.q.date_pushed).reversed()
        return dict(updates=updates, num_items=updates.count())

    @identity.require(identity.not_anonymous())
    @expose(template='bodhi.templates.show')
    def show(self, update):
        update = PackageUpdate.byNvr(update)
        return dict(update=update, comment_form=self.comment_form)

    @expose()
    @identity.require(identity.not_anonymous())
    @exception_handler(exception)
    def revoke(self, nvr):
        """ Revoke a push request for a specified update """
        update = PackageUpdate.byNvr(nvr)
        flash("%s request revoked" % update.request)
        mail.send_admin('revoke', update)
        update.request = None
        raise redirect(update.get_url())

    @expose()
    @identity.require(identity.not_anonymous())
    @exception_handler(exception)
    def move(self, nvr):
        update = PackageUpdate.byNvr(nvr)
        update.request = 'move'
        flash("Requested that %s be pushed to %s-updates" % (nvr,
              update.release.name))
        mail.send_admin('move', update)
        raise redirect(update.get_url())

    @expose()
    @identity.require(identity.not_anonymous())
    @exception_handler(exception)
    def push(self, nvr):
        """ Submit an update for pushing """
        update = PackageUpdate.byNvr(nvr)
        repo = '%s updates' % update.release.name
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
    @exception_handler(exception)
    def unpush(self, nvr):
        """ Submit an update for unpushing """
        update = PackageUpdate.byNvr(nvr)
        update.request = 'unpush'
        msg = "%s has been submitted for unpushing" % nvr
        log.debug(msg)
        flash(msg)
        mail.send_admin('unpush', update)
        raise redirect(update.get_url())

    @expose()
    @identity.require(identity.not_anonymous())
    @exception_handler(exception)
    def delete(self, update):
        """ Delete a pending update """
        update = PackageUpdate.byNvr(update)
        if not update.pushed:
            map(lambda x: x.destroySelf(), update.comments)
            update.destroySelf()
            mail.send_admin('deleted', update)
            msg = "Deleted %s" % update.nvr
            log.debug(msg)
            flash(msg)
        else:
            flash("Cannot delete a pushed update")
        raise redirect("/pending")

    @identity.require(identity.not_anonymous())
    @expose(template='bodhi.templates.form')
    def edit(self, update):
        """ Edit an update """
        update = PackageUpdate.byNvr(update)
        values = {
                'nvr'       : {'text': update.nvr, 'hidden' : update.nvr},
                'release'   : update.release.long_name,
                'testing'   : update.status == 'testing',
                'type'      : update.type,
                'embargo'   : update.embargo,
                'notes'     : update.notes,
                'bugs'      : update.get_bugstring(),
                'cves'      : update.get_cvestring(),
                'edited'    : update.nvr
        }
        return dict(form=update_form, values=values, action=url('/save'))

    @expose()
    @error_handler(new.index)
    @validate(form=update_form)
    @identity.require(identity.not_anonymous())
    def save(self, release, bugs, cves, edited, **kw):
        """
        Save an update.  This includes new updates and edited.
        """
        log.debug("save(%s, %s, %s, %s, %s)" % (release, bugs, cves, edited,kw))
        kw['nvr'] = kw['nvr']['text']
        if not kw['nvr'] or kw['nvr'] == '':
            flash("Please enter a package-version-release")
            raise redirect('/new')
        if edited and kw['nvr'] != edited:
            flash("You cannot change the package n-v-r after submission")
            raise redirect('/edit/%s' % edited)

        release = Release.select(Release.q.long_name == release)[0]
        bugs = map(int, bugs.replace(',', ' ').split())
        cves = cves.replace(',', ' ').split()
        note = ''

        if not edited: # new update
            name = util.get_nvr(kw['nvr'])[0]

            # Make sure selected release matches tag for this build
            koji = buildsys.get_session()
            tag_matches = False
            candidate = '%s-updates-candidate' % release.dist_tag
            try:
                for tag in koji.listTags(kw['nvr']):
                    log.debug(" * %s" % tag['name'])
                    if tag['name'] == candidate:
                        log.debug("%s built with tag %s" % (kw['nvr'],
                                                            tag['name']))
                        tag_matches = True
                        break
            except GenericError, e:
                flash("Invalid build: %s" % kw['nvr'])
                raise redirect('/new')
            if not tag_matches:
                flash("%s build is not tagged with %s" % (kw['nvr'], candidate))
                raise redirect('/new')

            # Get the package; if it doesn't exist, create it.
            try:
                package = Package.byName(name)
            except SQLObjectNotFound:
                package = Package(name=name)

            # Check for broken update paths.  Make sure this package is newer
            # than the previously released package on this release, as
            # well as on all older releases
            rel = release
            while True:
                log.debug("Checking for broken update paths in %s" % rel.name)
                for up in PackageUpdate.select(
                        AND(PackageUpdate.q.releaseID == rel.id,
                            PackageUpdate.q.packageID == package.id)):
                    if rpm.labelCompare(util.get_nvr(kw['nvr']),
                                        util.get_nvr(up.nvr)) < 0:
                        msg = "Broken update path: %s is older than existing" \
                              " update %s" % (kw['nvr'], up.nvr)
                        log.debug(msg)
                        flash(msg)
                        raise redirect('/new')
                try:
                    # Check the the previous release
                    rel = Release.byName(rel.name[:-1] +
                                         str(int(rel.name[-1]) - 1))
                except SQLObjectNotFound:
                    break

            try:
                # Create a new update
                p = PackageUpdate(package=package, release=release,
                                  submitter='%s <%s>' % (
                                      identity.current.user.display_name,
                                      identity.current.user.user['email']),
                                  **kw)
            except RPMNotFound:
                flash("Cannot find SRPM for update")
                raise redirect('/new')
            except (PostgresIntegrityError, SQLiteIntegrityError,
                    DuplicateEntryError):
                flash("Update for %s already exists" % kw['nvr'])
                raise redirect('/new')
            log.info("Adding new update %s" % kw['nvr'])
        else: # edited update
            from datetime import datetime
            log.info("Edited update %s" % edited)
            p = PackageUpdate.byNvr(edited)
            if p.release != release:
                flash("Cannot change update release after submission")
                raise redirect(p.get_url())
            p.set(release=release, date_modified=datetime.now(), **kw)
            p.update_bugs(bugs)
            p.update_cves(cves)

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
            if p.type == 'security':
                mail.send(config.get('security_team'), 'new', p,
                          sender=p.submitter)
            mail.send(p.submitter, 'new', p)
            flash("Update successfully created" + note)

        raise redirect(p.get_url())

    #@exception_handler(exception)
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
                                PackageUpdate.q.nvr == args[1],
                                PackageUpdate.q.status == status))[0]
                return dict(tg_template='bodhi.templates.show',
                            update=update, updates=[],
                            comment_form=self.comment_form,
                            values={'nvr' : update.nvr})
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
    @identity.require(identity.not_anonymous())
    @exception_handler(exception)
    def comment(self, text, nvr, tg_errors=None):
        update = PackageUpdate.byNvr(nvr)
        if tg_errors:
            flash(tg_errors['text'])
        else:
            comment = Comment(text=text, author='%s &lt;%s&gt;' % (
                              identity.current.user.display_name,
                              identity.current.user.user['email']),
                              update=update)
            mail.send(update.submitter, 'comment', update)
            flash("Successfully added comment to %s update" % nvr)
        raise redirect(update.get_url())

    @expose(template='bodhi.templates.text')
    def mail_notice(self, nvr, *args, **kw):
        update = PackageUpdate.byNvr(nvr)
        (subject, body) = mail.get_template(update)
        return dict(text=body, title=subject)
