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

import logging

from datetime import datetime, timedelta
from turbogears import (expose, paginate, validate, validators, redirect,
                        error_handler, url, flash, identity, config)
from turbogears.controllers import Controller

try:
    from fedora.tg.tg1utils import request_format
except ImportError:
    from fedora.tg.util import request_format

from bodhi.model import BuildRootOverride, Release
from bodhi.buildsys import get_session
from bodhi.util import get_nvr, get_pkg_pushers
from bodhi.widgets import BuildRootOverrideForm

log = logging.getLogger(__name__)

override_form = BuildRootOverrideForm()

class BuildRootOverrideController(Controller):

    @identity.require(identity.not_anonymous())
    @expose(template="bodhi.templates.overrides")
    @paginate('overrides', default_order='-date_submitted', 
              limit=20, max_limit=1000)
    def index(self, build=None, tg_errors=None, *args, **kw):
        if 'releng' in identity.current.groups:
            overrides = BuildRootOverride.select()
        else:
            overrides = BuildRootOverride.select(
                    BuildRootOverride.q.submitter == identity.current.user_name)
        return dict(overrides=overrides, title='Buildroot Overrides',
                    num_items=overrides.count())

    @identity.require(identity.not_anonymous())
    @expose(template="bodhi.templates.form")
    def new(self, tg_errors=None, *args, **kw):
        #if tg_errors:
        #    flash(tg_errors)
        expiration = datetime.utcnow() + \
            timedelta(days=config.get('buildroot_overrides.expire_after', 1))
        return dict(form=override_form, values={'expiration': expiration},
                    action=url('/override/save'), title='Buildroot Overrides')

    @identity.require(identity.not_anonymous())
    @expose(allow_json=True)
    def expire(self, build, *args, **kw):
        """ Expire a given override """
        override = BuildRootOverride.byBuild(build)
        try:
            override.untag()
        except Exception, e:
            log.error(str(e))
            flash(str(e))
            raise redirect('/override')
        log.info('Buildroot override %s manually expired by %s' % (
            build, identity.current.user_name))
        flash('Buildroot override for %s successful untagged' % build)
        override.destroySelf()
        if request_format() == 'json':
            return dict()
        raise redirect('/override')

    @identity.require(identity.not_anonymous())
    @expose('json')
    @validate(form=override_form)
    @error_handler(new)
    def save(self, builds, notes, expiration, *args, **kw):
        log.debug('BuildRootOverrideController.save(%s)' % builds)

        try:
            koji = get_session()
        except Exception, e:
            flash('Unable to connect to Koji')
            if request_format() == 'json':
                return dict()
            raise redirect('/override/new')

        for build in builds:
            release = None
            n, v, r = get_nvr(build)

            # Make sure the user has commit rights
            people, groups = get_pkg_pushers(n)
            if identity.current.user_name not in people[0]:
                flash("Error: You do not have commit privileges to %s" % n)
                if request_format() == 'json':
                    return dict()
                raise redirect('/override/new')

            # Make sure the build is tagged correctly
            try:
                tags = [tag['name'] for tag in koji.listTags(build)]
            except Exception, e:
                flash(str(e))
                if request_format() == 'json':
                    return dict()
                raise redirect('/override/new')
            
            # Determine the release by the tag, and sanity check the builds
            for tag in tags:
                for rel in Release.select():
                    if tag == rel.candidate_tag:
                        release = rel
                    elif tag in (rel.testing_tag, rel.stable_tag):
                        flash('Error: %s is already tagged with %s' % (
                            build, tag))
                        if request_format() == 'json':
                            return dict()
                        raise redirect('/override/new')

            if not release:
                flash('Error: Could not determine release for %s with tags %s' %
                        (build, map(str, tags)))
                if request_format() == 'json':
                    return dict()
                raise redirect('/override/new')

            # Create a new overrides object
            override = BuildRootOverride(build=build,
                    notes=notes, submitter=identity.current.user_name,
                    expiration=expiration, releaseID=release.id)

            # Tag the build
            override.tag()

        flash('Your buildroot override has been successfully tagged. '
              'It may take up to 20 minutes for the buildroot to regenerate.')
        if request_format() == 'json':
            return dict(override.__json__())
        raise redirect('/override')
