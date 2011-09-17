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
from sqlobject import AND, SQLObjectNotFound
from turbogears import (expose, paginate, validate, validators, redirect,
                        error_handler, flash, identity, config)
from turbogears.controllers import Controller
from kitchen.iterutils import iterate

try:
    from fedora.tg.tg1utils import request_format
except ImportError:
    from fedora.tg.util import request_format

from bodhi.model import BuildRootOverride, Release
from bodhi.buildsys import get_session
from bodhi.util import get_nvr, get_pkg_pushers, url
from bodhi.widgets import BuildRootOverrideForm
from bodhi.exceptions import DuplicateEntryError, PostgresIntegrityError


log = logging.getLogger(__name__)

override_form = BuildRootOverrideForm()

class BuildRootOverrideController(Controller):

    @identity.require(identity.not_anonymous())
    @expose()
    def index(self):
        raise redirect('/override/list')

    @identity.require(identity.not_anonymous())
    @expose(template="bodhi.templates.overrides", allow_json=True)
    @validate(validators={
        'build': validators.UnicodeString(),
        'mine': validators.StringBool(),
        'release': validators.UnicodeString(),
        'show_expired': validators.StringBool()
    })
    @paginate('overrides', default_order='-date_submitted', 
              limit=20, max_limit=1000)
    def list(self, build=None, tg_errors=None, mine=False, release=None, 
             show_expired=False, **kw):
        query = []
        title = '%d Buildroot Overrides'
        if mine:
            query.append(
                BuildRootOverride.q.submitter == identity.current.user_name)
            title += ' submitted by %s' % identity.current.user_name
        if release:
            rel = Release.byName(release)
            query.append(
                BuildRootOverride.q.releaseID == rel.id)
            title += ' for %s' % rel.long_name
        if not show_expired:
            query.append(
                BuildRootOverride.q.date_expired == None)

        overrides = BuildRootOverride.select(AND(*query))

        if request_format() == 'json':
            overrides = [o.__json__() for o in overrides]
            num_items = len(overrides)
        else:
            num_items = overrides.count()
        return dict(overrides=overrides,
                    title=title % num_items,
                    num_items=num_items,
                    show_expired=show_expired,
                    mine=mine)

    @identity.require(identity.not_anonymous())
    @expose(template="bodhi.templates.form")
    def new(self, tg_errors=None, *args, **kw):
        if tg_errors:
            flash(str(tg_errors))
        expiration = datetime.utcnow() + \
            timedelta(days=config.get('buildroot_overrides.expire_after', 1))
        return dict(form=override_form, values={'expiration': expiration},
                    action=url('/override/save'), title='Buildroot Overrides')

    @identity.require(identity.not_anonymous())
    @expose(allow_json=True)
    def expire(self, build, *args, **kw):
        """ Expire a given override """
        override = BuildRootOverride.byBuild(build)
        if override.date_expired:
            flash('Override %s already expired!' % build)
            if request_format() == 'json': return dict()
            raise redirect('/override')
        override.date_expired = datetime.utcnow()
        try:
            override.untag()
        except Exception, e:
            log.error(str(e))
            flash(str(e))
            raise redirect('/override')
        log.info('Buildroot override %s manually expired by %s' % (
            build, identity.current.user_name))
        flash('Buildroot override for %s successful untagged' % build)
        if request_format() == 'json': return dict()
        raise redirect('/override')

    @identity.require(identity.not_anonymous())
    @expose('json')
    @validate(form=override_form)
    @error_handler(new)
    def save(self, builds, notes, expiration=None, *args, **kw):
        log.debug(repr(locals()))
        last_release = None # for our koji wait-repo example

        if expiration:
            if datetime.utcnow() > expiration:
                flash('Cannot set an expiration in the past')
                if request_format() == 'json': return dict()
                raise redirect('/override/new')

        try:
            koji = get_session()
        except Exception, e:
            flash('Unable to connect to Koji')
            if request_format() == 'json':
                return dict()
            raise redirect('/override/new')

        for build in iterate(builds):
            release = None
            n, v, r = get_nvr(build)

            # Make sure the build is tagged correctly
            try:
                tags = [tag['name'] for tag in koji.listTags(build)]
            except Exception, e:
                flash(str(e))
                if request_format() == 'json': return dict()
                raise redirect('/override/new')

            # Determine the release by the tag, and sanity check the builds
            for tag in tags:
                for rel in Release.select():
                    if tag in (rel.candidate_tag, rel.testing_tag):
                        release = last_release = rel
                    elif tag == rel.stable_tag:
                        flash('Error: %s is already tagged with %s' % (
                            build, tag))
                        if request_format() == 'json': return dict()
                        raise redirect('/override/new')

            if not release:
                flash('Error: Could not determine release for %s with tags %s' %
                        (build, map(str, tags)))
                if request_format() == 'json': return dict()
                raise redirect('/override/new')

            # Make sure the user has commit rights to the appropriate branch
            pkgdb_args = {
                    'collectionName': 'Fedora',
                    'collectionVersion': 'devel',
            }
            pkgdb_args['collectionName'] = release.collection_name
            pkgdb_args['collectionVersion'] = str(release.get_version())

            try:
                people, groups = get_pkg_pushers(n, **pkgdb_args)
            except Exception, e:
                flash(str(e))
                if request_format() == 'json': return dict()
                raise redirect('/override/new')
            if identity.current.user_name not in people[0]:
                flash("Error: You do not have commit privileges to %s" % n)
                if request_format() == 'json': return dict()
                raise redirect('/override/new')

            # Create a new overrides object
            try:
                override = BuildRootOverride(build=build,
                        notes=notes, submitter=identity.current.user_name,
                        expiration=expiration, releaseID=release.id)
            except (DuplicateEntryError, PostgresIntegrityError):
                flash('Error: buildroot override for %r already exists' % build)
                if request_format() == 'json': return dict()
                raise redirect('/override/new')

            # Tag the build
            override.tag()

        flash('Your buildroot override has been successfully tagged. '
              'It may take up to 20 minutes for the buildroot to regenerate. '
              'You can wait for the new buildroot by running '
              '`koji wait-repo %s-build`' % last_release.dist_tag)

        if request_format() == 'json': return override.__json__()
        raise redirect('/override')

    @identity.require(identity.not_anonymous())
    @expose(template="bodhi.templates.form")
    def edit(self, build):
        """ Edit an override """
        try:
            override = BuildRootOverride.byBuild(build)
        except SQLObjectNotFound:
            flash('Cannot find override %r' % build)
            raise redirect('/override')
        values = {
                'builds': {'text': override.build, 'hidden': override.build},
                'expiration': override.expiration,
                'notes': override.notes,
                'edited': override.build,
        }
        if override.date_expired:
            flash('This override is EXPIRED. Editing it will re-enable it')
        return dict(form=override_form, values=values,
                    action=url("/override/save_edit"),
                    title='Edit Buildroot Override')

    @identity.require(identity.not_anonymous())
    @expose('json')
    @validate(validators={
        'builds': validators.UnicodeString(),
        'notes': validators.UnicodeString(),
        'expiration': validators.DateTimeConverter(format='%m/%d/%Y',
                                                   not_empty=False)
    })
    @error_handler(new)
    def save_edit_cli(self, builds, notes, expiration=None, **kw):
        log.debug(repr(locals()))
        if expiration:
            if datetime.utcnow() > expiration:
                flash('Cannot set an expiration in the past')
                if request_format() == 'json': return dict()
                raise redirect('/override/edit?build=' + builds)
        try:
            override = BuildRootOverride.byBuild(builds)
        except SQLObjectNotFound:
            flash('Cannot find override to edit %r' % builds)
            raise redirect('/override')
        override.notes = notes
        override.expiration = expiration
        if override.date_expired:
            log.debug('Retagging expired override: %s' % override.build)
            override.date_expired = None
            override.tag()
        flash('%s successfully edited' % builds)
        if request_format() == 'json': return override.__json__()
        raise redirect('/override')

    @identity.require(identity.not_anonymous())
    @expose('json')
    @validate(form=override_form)
    @error_handler(new)
    def save_edit(self, builds, notes, expiration=None, **kw):
        log.debug(repr(locals()))
        if len(builds) > 1:
            flash('Unable to add builds to an existing override')
            raise redirect('/override')
        builds = builds[0]
        if expiration:
            if datetime.utcnow() > expiration:
                flash('Cannot set an expiration in the past')
                if request_format() == 'json': return dict()
                raise redirect('/override/edit?build=' + builds)
        try:
            override = BuildRootOverride.byBuild(builds)
        except SQLObjectNotFound:
            flash('Cannot find override to edit %r' % builds)
            raise redirect('/override')
        override.notes = notes
        override.expiration = expiration
        if override.date_expired:
            log.debug('Retagging expired override: %s' % override.build)
            override.date_expired = None
            override.tag()
        flash('%s successfully edited' % builds)
        if request_format() == 'json': return override.__json__()
        raise redirect('/override')
