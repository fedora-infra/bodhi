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

from new import NewUpdateController, update_form
from admin import AdminController
from model import Package, PackageUpdate, Release, Bugzilla, CVE
from buildsys import SRPMNotFound
from sqlobject import SQLObjectNotFound
from turbogears import (controllers, expose, validate, redirect, identity,
                        paginate, flash, error_handler)

from pysqlite2.dbapi2 import IntegrityError

log = logging.getLogger(__name__)

class Root(controllers.RootController):

    new = NewUpdateController()
    admin = AdminController()

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
        updates=PackageUpdate.select(PackageUpdate.q.pushed==True).reversed()
        return dict(updates=updates)

    @identity.require(identity.not_anonymous())
    @expose(template="bodhi.templates.list")
    @paginate('updates', default_order='update_id', limit=15)
    def pending(self):
        """ List all updates that are in a pending state """
        updates = PackageUpdate.select(PackageUpdate.q.pushed==False)
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
        return dict(update=update)

    @expose()
    @identity.require(identity.not_anonymous())
    def push(self, nvr):
        """
        Submit an update for pushing.
        """
        try:
            up = PackageUpdate.byNvr(nvr)
            up.needs_push = True
            flash("%s has been submitted for pushing" % nvr)
            mail.send_admin('push', up)
        except SQLObjectNotFound:
            flash("Update %s not found" % nvr)
        raise redirect('/show/%s' % nvr)

    @expose()
    @identity.require(identity.not_anonymous())
    def unpush(self, nvr):
        """
        Submit an update for unpushing
        """
        try:
            up = PackageUpdate.byNvr(nvr)
            up.needs_unpush = True
            up.sync()
            flash("%s has been submitted for unpushing" % nvr)
            mail.send_admin('unpush', up)
        except SQLObjectNotFound:
            flash("Update %s not found" % nvr)
        raise redirect('/show/%s' % nvr)

    @expose()
    @identity.require(identity.not_anonymous())
    def delete(self, update):
        """
        Delete a pending update
        """
        try:
            up = PackageUpdate.byNvr(update)
        except SQLObjectNotFound:
            flash("Update %s not found" % update)
            raise redirect("/list")
        if not up.pushed:
            log.debug("Deleting update %s" % up.nvr)
            up.destroySelf()
            mail.send_admin('deleted', up)
            flash("%s deleted" % update)
        else:
            flash("Cannot delete a pushed update")
        raise redirect("/list")

    @identity.require(identity.not_anonymous())
    @expose(template='bodhi.templates.form')
    def edit(self, update):
        """
        Edit an update
        """
        try:
            up = PackageUpdate.byNvr(update)
        except SQLObjectNotFound:
            flash("Update %s not found")
            raise redirect("/list")
        values = {
                'nvr'       : {'text': up.nvr, 'hidden' : up.nvr},
                'release'   : up.release.long_name,
                'testing'   : up.testing,
                'type'      : up.type,
                'embargo'   : up.embargo,
                'notes'     : up.notes,
                'bugs'      : up.get_bugstring(),
                'cves'      : up.get_cvestring(),
                'edited'    : up.nvr
        }
        return dict(form=update_form, values=values, action='/save')

    @expose()
    @error_handler(new.index)
    @validate(form=update_form)
    @identity.require(identity.not_anonymous())
    def save(self, release, bugs, cves, edited, **kw):
        """
        Save an update.  This includes new updates and edited.
        Most of these checks should eventually make their way into the NewUpdateSchema
        validators.
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
            try:
                name = util.get_nvr(kw['nvr'])[0]
                try:
                    package = Package.byName(name)
                except SQLObjectNotFound:
                    package = Package(name=name)
                p = PackageUpdate(package=package, release=release,
                                  submitter=identity.current.user_name, **kw)
            except IndexError:
                flash("Package needs to be in name-ver-rel format")
                raise redirect('/new')
            except IntegrityError:
                flash("Update for %s already exists" % kw['nvr'])
                raise redirect('/new')
            except SRPMNotFound:
                flash("Cannot find SRPM for update")
                raise redirect('/new')
            except Exception, e:
                msg = "Unknown exception thrown: %s" % str(e)
                log.error(msg)
                flash(msg)
                raise redirect('/new')
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
                raise redirect('/')
            if bz.security:
                log.info("Bug #s tagged with Security keyword; changing update type")
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
        if p.cves != [] and not p.security:
            p.security = True
            note += '; CVEs provided, changed update type to security'

        if edited:
            flash("Update successfully edited" + note)
            mail.send_admin('edited', p)
        else:
            flash("Update successfully added" + note)
            mail.send_admin('new', p)

        raise redirect('/show/%s' % p.nvr)
