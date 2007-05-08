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

import mail
import util
import logging
import cherrypy
import xmlrpclib

from sqlobject import SQLObjectNotFound
from sqlobject.dberrors import DuplicateEntryError
from sqlobject.sqlbuilder import AND

from turbogears import (controllers, expose, validate, redirect, identity,
                        paginate, flash, error_handler, validators, config)
from turbogears.widgets import TableForm, TextArea, WidgetsList, HiddenField

from bodhi.new import NewUpdateController, update_form
from bodhi.admin import AdminController
from bodhi.model import Package, PackageUpdate, Release, Bugzilla, CVE, Comment
from bodhi.search import SearchController
from bodhi.xmlrpc import XmlRpcController
from bodhi.exceptions import RPMNotFound

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
                             submit_text='Add Comment', action='/comment')
    @expose()
    @identity.require(identity.not_anonymous())
    def index(self):
        raise redirect('/list')

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
        raise redirect("/")

    @identity.require(identity.not_anonymous())
    @expose(template="bodhi.templates.list")
    @paginate('updates', default_order='update_id', limit=15)
    def list(self):
        """ List all pushed updates """
        updates = PackageUpdate.select(
                    AND(PackageUpdate.q.pushed == True,
                        PackageUpdate.q.testing == False),
                    orderBy=PackageUpdate.q.update_id).reversed()
        return dict(updates=updates)

    @expose(template="bodhi.templates.list")
    @identity.require(identity.not_anonymous())
    @paginate('updates', default_order='update_id', limit=15)
    def mine(self):
        """ List all updates submitted by the current user """
        updates = PackageUpdate.select(PackageUpdate.q.submitter ==
                                       identity.current.user_name)
        return dict(updates=updates)

    @identity.require(identity.not_anonymous())
    @expose(template='bodhi.templates.show')
    def show(self, update):
        try:
            update = PackageUpdate.byNvr(update)
        except SQLObjectNotFound:
            flash("Update %s not found" % update)
            raise redirect("/list")
        return dict(update=update, comment_form=self.comment_form)

    @expose()
    @identity.require(identity.not_anonymous())
    def revoke(self, nvr):
        """ Revoke a push request for a specified update """
        try:
            update = PackageUpdate.byNvr(nvr)
            update.request = None
            mail.send_admin('revoke', update)
            log.info("%s push revoked" % nvr)
        except SQLObjectNotFound:
            flash("Update %s not found" % update)
            raise redirect("/list")
        flash("Push request revoked")
        raise redirect(update.get_path())

    @expose()
    @identity.require(identity.not_anonymous())
    def move(self, nvr):
        try:
            update = PackageUpdate.byNvr(nvr)
            update.request = 'move'
            flash("Requested that %s be pushed to Final" % nvr)
        except SQLObjectNotFound:
            flash("Update %s not found" % nvr)
            raise redirect("/")
        raise redirect(update.get_path())

    @expose()
    @identity.require(identity.not_anonymous())
    def push(self, nvr):
        """ Submit an update for pushing """
        try:
            update = PackageUpdate.byNvr(nvr)
            update.request = 'push'
            msg = "%s has been submitted for pushing" % nvr
            log.debug(msg)
            flash(msg)
            mail.send_admin('push', update)
        except SQLObjectNotFound:
            flash("Update %s not found" % nvr)
        raise redirect(update.get_path())

    @expose()
    @identity.require(identity.not_anonymous())
    def unpush(self, nvr):
        """ Submit an update for unpushing """
        try:
            update = PackageUpdate.byNvr(nvr)
            update.request = 'unpush'
            msg = "%s has been submitted for unpushing" % nvr
            log.debug(msg)
            flash(msg)
            mail.send_admin('unpush', update)
        except SQLObjectNotFound:
            flash("Update %s not found" % nvr)
        raise redirect(update.get_path())

    @expose()
    @identity.require(identity.not_anonymous())
    def delete(self, update):
        """ Delete a pending update """
        try:
            update = PackageUpdate.byNvr(update)
        except SQLObjectNotFound:
            flash("Update %s not found" % update)
            raise redirect("/pending")
        if not update.pushed:
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
        try:
            update = PackageUpdate.byNvr(update)
        except SQLObjectNotFound:
            flash("Update %s not found")
            raise redirect("/list")
        values = {
                'nvr'       : {'text': update.nvr, 'hidden' : update.nvr},
                'release'   : update.release.long_name,
                'testing'   : update.testing,
                'type'      : update.type,
                'embargo'   : update.embargo,
                'notes'     : update.notes,
                'bugs'      : update.get_bugstring(),
                'cves'      : update.get_cvestring(),
                'edited'    : update.nvr
        }
        return dict(form=update_form, values=values, action='/save')

    @expose()
    @error_handler(new.index)
    @validate(form=update_form)
    @identity.require(identity.not_anonymous())
    def save(self, release, bugs, cves, edited, **kw):
        """
        Save an update.  This includes new updates and edited.
        """
        kw['nvr'] = kw['nvr']['text']
        if not kw['nvr'] or kw['nvr'] == '':
            flash("Please enter a package-version-release")
            raise redirect('/new')
        if edited and kw['nvr'] != edited:
            flash("You cannot change the package n-v-r after submission")
            raise redirect('/edit/%s' % edited)

        release = Release.select(Release.q.long_name == release)[0]
        note = ''

        if not edited: # new update
            name = util.get_nvr(kw['nvr'])[0]

            # Make sure selected release matches tag for this build
            koji = xmlrpclib.ServerProxy(config.get('koji_hub'),
                                         allow_none=True)
            tag_matches = False
            candidate = 'dist-%s-updates-candidate' % release.name.lower()
            try:
                for tag in koji.listTags(kw['nvr']):
                    log.debug(" * %s" % tag['name'])
                    if tag['name'] == candidate:
                        log.debug("%s built with tag %s" % (kw['nvr'],
                                                            tag['name']))
                        tag_matches = True
                        break
            except xmlrpclib.Fault:
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

            try:
                # Create a new update
                p = PackageUpdate(package=package, release=release,
                                  submitter=identity.current.user_name, **kw)
                p._build_filelist()
            except RPMNotFound:
                flash("Cannot find SRPM for update")
                raise redirect('/new')
            except (PostgresIntegrityError, SQLiteIntegrityError,
                    DuplicateEntryError):
                flash("Update for %s already exists" % kw['nvr'])
                raise redirect('/new')
            #except Exception, e:
            #    msg = "Unknown exception thrown: %s" % str(e)
            #    log.error(msg)
            #    flash(msg)
            #    raise redirect('/new')
            log.info("Adding new update %s" % kw['nvr'])
        else: # edited update
            from datetime import datetime
            log.info("Edited update %s" % edited)
            p = PackageUpdate.byNvr(edited)
            p.set(release=release, date_modified=datetime.now(), **kw)
            map(p.removeBugzilla, p.bugs)
            map(p.removeCVE, p.cves)

        # Add each bug and CVE to this package
        for bug in bugs.replace(',', ' ').split():
            bz = None
            try:
                bz = Bugzilla.byBz_id(int(bug))
            except SQLObjectNotFound:
                bz = Bugzilla(bz_id=int(bug))
            except ValueError:
                flash("Invalid bug number")
                # TODO: redirect back to the previous page
                raise redirect('/')
            if bz.security and p.type != 'security':
                p.type = 'security'
                note += '; Security bugs found, changed update type to security'
            p.addBugzilla(bz)
        for cve_id in cves.replace(',', ' ').split():
            cve = None
            try:
                cve = CVE.byCve_id(cve_id)
            except SQLObjectNotFound:
                cve = CVE(cve_id=cve_id)
            p.addCVE(cve)
        if p.cves != [] and (p.type != 'security'):
            p.type = 'security'
            note += '; CVEs provided, changed update type to security'

        if edited:
            flash("Update successfully edited" + note)
            mail.send_admin('edited', p)
        else:
            flash("Update successfully added" + note)
            mail.send_admin('new', p)

        raise redirect(p.get_path())

    @expose(template='bodhi.templates.list')
    @paginate('updates', default_order='update_id', limit=15)
    def default(self, *args, **kw):
        """
        This method allows for /[(pending|testing)/]<release>[/<update>]
        requests.
        """
        args = [arg for arg in args]
        testing = False
        pushed = True

        if len(args) and args[0] == 'testing':
            testing = True
            del args[0]
        if len(args) and args[0] == 'pending':
            pushed = False
            testing = True
            del args[0]
        if not len(args): # /(testing|pending)
            updates = PackageUpdate.select(
                        AND(PackageUpdate.q.testing == testing,
                            PackageUpdate.q.pushed == pushed),
                        orderBy=PackageUpdate.q.update_id).reversed()
            return dict(updates=updates)

        try:
            release = Release.byName(args[0])
            try:
                update = PackageUpdate.select(
                            AND(PackageUpdate.q.releaseID == release.id,
                                PackageUpdate.q.nvr == args[1],
                                PackageUpdate.q.testing == testing,
                                PackageUpdate.q.pushed == pushed))[0]
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
                                PackageUpdate.q.testing == testing,
                                PackageUpdate.q.pushed == pushed),
                            orderBy=PackageUpdate.q.update_id).reversed()
                return dict(updates=updates)
        except SQLObjectNotFound:
            pass

        flash("The path %s cannot be found" % cherrypy.request.path)
        raise redirect("/")

    @expose()
    @error_handler()
    @validate(form=comment_form)
    @identity.require(identity.not_anonymous())
    def comment(self, text, nvr, tg_errors=None):
        update = PackageUpdate.byNvr(nvr)
        if tg_errors:
            flash(tg_errors['text'])
        else:
            comment = Comment(text=text, author=identity.current.user_name,
                              update=update)
            mail.send(update.submitter, 'comment', update)
            flash("Successfully added comment to %s update" % nvr)
        raise redirect(update.get_path())
