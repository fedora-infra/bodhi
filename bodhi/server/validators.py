# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from datetime import datetime, timedelta

from pyramid.exceptions import HTTPNotFound, HTTPBadRequest
from pyramid.httpexceptions import HTTPFound
from sqlalchemy.sql import or_, and_
import colander
import koji
import pyramid.threadlocal
import rpm

from . import captcha
from . import log
from .models import (Release, Package, Build, Update, UpdateStatus,
                     UpdateRequest, UpdateSeverity, UpdateType,
                     UpdateSuggestion, User, Group, Comment,
                     Bug, TestCase, ReleaseState, Stack)
from .util import get_nvr, splitter, tokenize, taskotron_results


csrf_error_message = """CSRF tokens do not match.  This happens if you have
the page open for a long time. Please reload the page and try to submit your
data again. Make sure to save your input somewhere before reloading.
""".replace('\n', ' ')


# This one is a colander validator which is different from the cornice
# validators defined elsehwere.
def validate_csrf_token(node, value):
    request = pyramid.threadlocal.get_current_request()
    expected = request.session.get_csrf_token()
    if value != expected:
        raise colander.Invalid(node, csrf_error_message)


def cache_nvrs(request, build):
    if build in request.buildinfo and 'nvr' in request.buildinfo[build]:
        return
    if build not in request.buildinfo:
        request.buildinfo[build] = {}
    name, version, release = get_nvr(build)
    request.buildinfo[build]['nvr'] = name, version, release
    if '' in (name, version, release):
        raise ValueError


def validate_nvrs(request):
    for build in request.validated.get('builds', []):
        try:
            cache_nvrs(request, build)
        except:
            request.validated['builds'] = []
            request.errors.add('body', 'builds', 'Build not in '
                               'name-version-release format: %s' % build)
            return


def validate_builds(request):
    edited = request.validated.get('edited')
    settings = request.registry.settings
    user = User.get(request.user.name, request.db)

    if not request.validated.get('builds', []):
        request.errors.add('body', 'builds', "You may not specify an empty list of builds.")
        return

    if edited:
        up = request.db.query(Update).filter_by(title=edited).first()
        if not up:
            request.errors.add('body', 'builds',
                               'Cannot find update to edit: %s' % edited)
            return

        # Allow admins to edit stable updates
        user_groups = set([group.name for group in user.groups])
        admin_groups = set(settings['admin_packager_groups'].split())
        if not user_groups & admin_groups:
            if up.status is UpdateStatus.stable:
                request.errors.add('body', 'builds',
                                   'Cannot edit stable updates')

        for nvr in request.validated.get('builds', []):
            # If the build is new
            if nvr not in edited:
                # Ensure it doesn't already exist
                build = request.db.query(Build).filter_by(nvr=nvr).first()
                if build and build.update is not None:
                    request.errors.add('body', 'builds',
                                       "Update for {} already exists".format(nvr))

        return

    for nvr in request.validated.get('builds', []):
        build = request.db.query(Build).filter_by(nvr=nvr).first()
        if build and build.update is not None:
            request.errors.add('body', 'builds',
                               "Update for {} already exists".format(nvr))
            return


def validate_build_tags(request):
    """ Ensure that all of the builds are tagged as candidates """
    tag_types, tag_rels = Release.get_tags(request.db)
    edited = request.validated.get('edited')
    release = None
    if edited:
        valid_tags = tag_types['candidate'] + tag_types['testing']
        update = request.db.query(Update).filter_by(title=edited).first()
        if not update:
            # No need to tack on any more errors here, since they should have
            # already been added by `validate_builds`
            return

        release = update.release
        if not release:
            # If the edited update has no release, something went wrong a while
            # ago.  We're already in a corrupt state.  We can't perform the
            # check further down as to whether or not the user is submitting
            # builds that do or do not match the release of this update...
            # because we don't know the release of this update.
            request.errors.add('body', 'edited',
                               'Pre-existing update %s has no associated '
                               '"release" object.  Please submit a ticket to '
                               'resolve this.' % edited)
            return
    else:
        valid_tags = tag_types['candidate']

    for build in request.validated.get('builds', []):
        valid = False
        try:
            tags = request.buildinfo[build]['tags'] = [
                tag['name'] for tag in request.koji.listTags(build)
            ]
        except koji.GenericError:
            request.errors.add('body', 'builds',
                               'Invalid koji build: %s' % build)
            return

        # Disallow adding builds for a different release
        if edited:
            try:
                build_rel = Release.from_tags(tags, request.db)
                if not build_rel:
                    raise KeyError("Couldn't find release from build tags")
            except KeyError:
                if tags:
                    msg = 'Cannot find release associated with build: ' + \
                        '{}, tags: {}'.format(build, tags)
                else:
                    msg = 'Cannot find any tags associated with build: ' + \
                        '{}'.format(build)
                log.warn(msg)
                request.errors.add('body', 'builds', msg)
                return

            if build_rel is not release:
                request.errors.add('body', 'builds', 'Cannot add a %s build to an %s update' % (
                    build_rel.name, release.name))
                return

        for tag in tags:
            if tag in valid_tags:
                valid = True
                break
        if not valid:
            request.errors.add(
                'body', 'builds',
                'Invalid tag: {} not tagged with any of the following tags {}'.format(
                    build, valid_tags))


def validate_tags(request):
    """Ensure that all the tags are valid Koji tags"""
    tag_types, tag_rels = Release.get_tags(request.db)

    for tag_type in tag_types:
        tag_name = request.validated.get("%s_tag" % tag_type)

        if not tag_name:
            continue

        try:
            request.koji.getTag(tag_name, strict=True)
            request.validated["%s_tag" % tag_type] = tag_name

        except Exception:
            request.errors.add('body', "%s_tag" % tag_type,
                               'Invalid tag: %s' % tag_name)


def validate_acls(request):
    """Ensure this user has commit privs to these builds or is an admin"""
    if not request.user:
        # If you're not logged in, obviously you don't have ACLs.
        request.errors.add('session', 'user', 'No ACLs for anonymous user')
        return
    db = request.db
    user = User.get(request.user.name, request.db)
    settings = request.registry.settings
    committers = []
    watchers = []
    groups = []
    notify_groups = []

    # There are two different code-paths that could pass through this validator
    # One of them is for submitting something new with a list of builds (a new
    # update, or editing an update by changing the list of builds).  The other
    # is for changing the request on an existing update -- where an update
    # title has been passed to us, but not a list of builds.
    # We need to validate that the user has commit rights on all the build
    # (either the explicitly listed ones or on the ones associated with the
    # pre-existing update).. and so we'll do some conditional branching below
    # to handle those two scenarios.

    # This can get confusing.
    # TODO -- we should break these two roles out into two different clearly
    # defined validator functions like `validate_acls_for_builds` and
    # `validate_acls_for_update`.

    builds = None
    if 'builds' in request.validated:
        builds = request.validated['builds']

    if 'update' in request.validated:
        builds = request.validated['update'].builds

    if not builds:
        log.error("validate_acls was passed data with nothing to validate.")
        request.errors.add('body', 'builds', 'ACL validation mechanism was '
                           'unable to determine ACLs.')
        return

    for build in builds:
        # The whole point of the blocks inside this conditional is to determine
        # the "release" and "package" associated with the given build.  For raw
        # (new) builds, we have to do that by hand.  For builds that have been
        # previously associated with an update, we can just look it up no prob.
        if 'builds' in request.validated:
            # Split out NVR data unless its already done.
            try:
                cache_nvrs(request, build)
            except ValueError:
                error = 'Problem caching NVRs when validating ACLs.'
                log.exception(error)
                request.errors.add('body', 'builds', error)
                return

            buildinfo = request.buildinfo[build]

            # Get the Package object
            package_name = buildinfo['nvr'][0]
            package = db.query(Package).filter_by(name=package_name).first()
            if not package:
                package = Package(name=package_name)
                db.add(package)
                db.flush()

            # Determine the release associated with this build
            tags = buildinfo.get('tags', [])
            try:
                release = Release.from_tags(tags, db)
            except KeyError:
                log.warn('Unable to determine release from '
                         'tags: %r build: %r' % (tags, build))
                request.errors.add('body', 'builds',
                                   'Unable to determine release ' +
                                   'from build: %s' % build)
                return
            buildinfo['release'] = release
            if not release:
                msg = 'Cannot find release associated with ' + \
                    'build: {}, tags: {}'.format(build, tags)
                log.warn(msg)
                request.errors.add('body', 'builds', msg)
                return
        elif 'update' in request.validated:
            buildinfo = request.buildinfo[build.nvr]

            # Easy to find the release and package since they're associated
            # with a pre-stored Build obj.
            package = build.package
            release = build.update.release

            # Some sanity checking..
            if not package:
                msg = build.nvr + ' has no package associated with it in ' + \
                    'our DB, so we cannot verify that you\'re in the ACL.'
                log.error(msg)
                request.errors.add('body', 'builds', msg)
                return
            if not release:
                msg = build.nvr + ' has no release associated with it in ' + \
                    'our DB, so we cannot verify that you\'re in the ACL.'
                log.error(msg)
                request.errors.add('body', 'builds', msg)
                return
        else:
            raise NotImplementedError()  # Should never get here.

        # Now that we know the release and the package associated with this
        # build, we can ask our ACL system about it..

        acl_system = settings.get('acl_system')
        user_groups = [group.name for group in user.groups]
        has_access = False

        # Allow certain groups to push updates for any package
        admin_groups = settings['admin_packager_groups'].split()
        for group in admin_groups:
            if group in user_groups:
                log.debug('{} is in {} admin group'.format(user.name, group))
                has_access = True
                break

        if has_access:
            continue

        if acl_system == 'pkgdb':
            try:
                people, groups = package.get_pkg_pushers(
                    release.branch, settings)
                committers, watchers = people
                groups, notify_groups = groups
            except Exception, e:
                log.exception(e)
                request.errors.add('body', 'builds',
                                   "Unable to access the Package "
                                   "Database to check ACLs. Please "
                                   "try again later.")
                return
        elif acl_system == 'dummy':
            people = (['ralph', 'bowlofeggs', 'guest'], ['guest'])
            groups = (['ralph', 'bowlofeggs', 'guest'], ['guest'])
            committers, watchers = people
        else:
            log.warn('No acl_system configured')
            people = None

        buildinfo['people'] = people

        if user.name not in committers:
            # Check if this user is in a group that has access to this package
            for group in user_groups:
                if group in groups:
                    log.debug('{} is in {} group for {}'.format(
                        user.name, group, package.name))
                    has_access = True
                    break

            if not has_access:
                request.errors.add('body', 'builds', "{} does not have commit "
                                   "access to {}".format(user.name, package.name))


def validate_uniqueness(request):
    """ Check for multiple builds from the same package and same release """
    builds = request.validated.get('builds', [])
    if not builds:  # validate_nvr failed
        return
    for build1 in builds:
        nvr1 = request.buildinfo[build1]['nvr']
        seen_build = 0
        for build2 in builds:
            nvr2 = request.buildinfo[build2]['nvr']
            if build1 == build2:
                seen_build += 1
                if seen_build > 1:
                    request.errors.add('body', 'builds', 'Duplicate builds: '
                                       '{}'.format(build1))
                    return
                continue

            release1 = nvr1[-1].split('.')[-1]
            release2 = nvr2[-1].split('.')[-1]

            if nvr1[0] == nvr2[0] and release1 == release2:
                request.errors.add(
                    'body', 'builds', "Multiple {} builds specified: {} & {}".format(
                        nvr1[0], build1, build2))
                return


def validate_enums(request):
    """Convert from strings to our enumerated types"""
    for param, enum in (("request", UpdateRequest),
                        ("severity", UpdateSeverity),
                        ("status", UpdateStatus),
                        ("suggest", UpdateSuggestion),
                        ("type", UpdateType),
                        ("state", ReleaseState)):
        value = request.validated.get(param)
        if value is None:
            continue

        request.validated[param] = enum.from_string(value)


def validate_packages(request):
    """Make sure those packages exist"""
    packages = request.validated.get("packages")
    if packages is None:
        return

    db = request.db
    bad_packages = []
    validated_packages = []

    for p in packages:
        package = Package.get(p, db)

        if not package:
            bad_packages.append(p)
        else:
            validated_packages.append(package)

    if bad_packages:
        request.errors.add('querystring', 'packages',
                           "Invalid packages specified: {}".format(
                               ", ".join(bad_packages)))
    else:
        request.validated["packages"] = validated_packages


def validate_updates(request):
    """Make sure those updates exist"""
    updates = request.validated.get("updates")
    if updates is None:
        return

    db = request.db
    bad_updates = []
    validated_updates = []

    for u in updates:
        update = db.query(Update).filter(or_(
            Update.title == u,
            Update.alias == u,
        )).first()

        if not update:
            bad_updates.append(u)
        else:
            validated_updates.append(update)

    if bad_updates:
        request.errors.add('querystring', 'updates',
                           "Invalid updates specified: {}".format(
                               ", ".join(bad_updates)))
    else:
        request.validated["updates"] = validated_updates


def validate_groups(request):
    """Make sure those groups exist"""
    groups = request.validated.get("groups")
    if groups is None:
        return

    db = request.db
    bad_groups = []
    validated_groups = []

    for g in groups:
        group = db.query(Group).filter(Group.name == g).first()

        if not group:
            bad_groups.append(g)
        else:
            validated_groups.append(group)

    if bad_groups:
        request.errors.add('querystring', 'groups',
                           "Invalid groups specified: {}".format(
                               ", ".join(bad_groups)))
    else:
        request.validated["groups"] = validated_groups


def validate_release(request):
    """Make sure this singular release exists"""
    releasename = request.validated.get("release")
    if releasename is None:
        return

    db = request.db
    release = db.query(Release).filter(or_(
        Release.name == releasename, Release.name == releasename.upper(),
        Release.version == releasename)).first()

    if release:
        request.validated["release"] = release
    else:
        request.errors.add("querystring", "release",
                           "Invalid release specified: {}".format(releasename))


def validate_releases(request):
    """Make sure those releases exist"""
    releases = request.validated.get("releases")
    if releases is None:
        return

    db = request.db
    bad_releases = []
    validated_releases = []

    for r in releases:
        release = db.query(Release).filter(or_(Release.name == r, Release.name == r.upper(),
                                               Release.version == r)).first()

        if not release:
            bad_releases.append(r)

        else:
            validated_releases.append(release)

    if bad_releases:
        request.errors.add('querystring', 'releases',
                           "Invalid releases specified: {}".format(
                               ", ".join(bad_releases)))

    else:
        request.validated["releases"] = validated_releases


def validate_bugs(request):
    bugs = request.validated.get('bugs')
    if bugs:
        try:
            request.validated['bugs'] = map(int, bugs)
        except ValueError:
            request.errors.add("querystring", "bugs",
                               "Invalid bug ID specified: {}".format(bugs))


def validate_username(request):
    """Make sure this user exists"""
    username = request.validated.get("user")
    if username is None:
        return

    db = request.db
    user = db.query(User).filter_by(name=username).first()

    if user:
        request.validated["user"] = user
    else:
        request.errors.add("querystring", "user",
                           "Invalid user specified: {}".format(username))


def validate_update(request):
    """Make sure this update exists"""
    idx = request.validated.get('update')
    update = Update.get(idx, request.db)

    if update:
        request.validated['update'] = update
    else:
        request.errors.add('url', 'update',
                           'Invalid update specified: %s' % idx)
        request.errors.status = HTTPNotFound.code


def validate_update_owner(request):
    """Make sure this user exists"""
    username = request.validated.get("update_owner")
    if username is None:
        return

    db = request.db
    user = db.query(User).filter_by(name=username).first()

    if user:
        request.validated["update_owner"] = user
    else:
        request.errors.add("querystring", "update_owner",
                           "Invalid user specified: {}".format(username))


def validate_ignore_user(request):
    """Make sure this user exists"""
    username = request.validated.get("ignore_user")
    if username is None:
        return

    db = request.db
    user = db.query(User).filter_by(name=username).first()

    if user:
        request.validated["ignore_user"] = user
    else:
        request.errors.add("querystring", "ignore_user",
                           "Invalid user specified: {}".format(username))


def validate_update_id(request):
    """Ensure that a given update id exists"""
    update = Update.get(request.matchdict['id'], request.db)
    if update:
        request.validated['update'] = update
    else:
        package = Package.get(request.matchdict['id'], request.db)
        if package:
            query = dict(packages=package.name)
            location = request.route_url('updates', _query=query)
            raise HTTPFound(location=location)

        request.errors.add('url', 'id', 'Invalid update id')
        request.errors.status = HTTPNotFound.code


def _conditionally_get_update(request):
    update = request.validated['update']

    # This may or may not be true.. if a *different* validator runs first, then
    # request.validated['update'] will be an Update object.  But if it does
    # not, then request.validated['update'] will be a unicode object.
    # So.. we have to handle either situation.  It is, however, not our
    # responsibility to put the update object back in the request.validated
    # dict.  Note, for speed purposes, sqlalchemy should cache this for us.
    if not isinstance(update, Update) and update is not None:
        update = Update.get(update, request.db)

    return update


def validate_bug_feedback(request):
    """Ensure that a given update id exists"""
    feedback = request.validated.get('bug_feedback')
    if feedback is None:
        return

    update = _conditionally_get_update(request)
    if not update:
        request.errors.add('url', 'id', 'Invalid update')
        request.errors.status = HTTPNotFound.code
        return

    db = request.db
    bad_bugs = []
    validated = []

    for item in feedback:
        bug_id = item.pop('bug_id')
        bug = db.query(Bug).filter(Bug.bug_id == bug_id).first()

        if not bug or update not in bug.updates:
            bad_bugs.append(bug_id)
        else:
            item['bug'] = bug
            validated.append(item)

    if bad_bugs:
        request.errors.add('querystring', 'bug_feedback',
                           "Invalid bug ids specified: {}".format(
                               ", ".join(map(str, bad_bugs))))
    else:
        request.validated["bug_feedback"] = validated


def validate_testcase_feedback(request):
    """Ensure that a given update id exists"""
    feedback = request.validated.get('testcase_feedback')
    if feedback is None:
        return

    update = request.validated['update']
    if not update:
        request.errors.add('url', 'id', 'Invalid update')
        request.errors.status = HTTPNotFound.code
        return

    # This may or may not be true.. if a *different* validator runs first, then
    # request.validated['update'] will be an Update object.  But if it does
    # not, then request.validated['update'] will be a unicode object.
    # So.. we have to handle either situation.  It is, however, not our
    # responsibility to put the update object back in the request.validated
    # dict.  Note, for speed purposes, sqlalchemy should cache this for us.
    if not isinstance(update, Update):
        update = Update.get(update, request.db)
        if not update:
            request.errors.add('url', 'id', 'Invalid update')
            request.errors.status = HTTPNotFound.code
            return

    packages = [build.package for build in update.builds]

    db = request.db
    bad_testcases = []
    validated = []

    for item in feedback:
        name = item.pop('testcase_name')
        testcase = db.query(TestCase).filter(TestCase.name == name).first()

        if not testcase or testcase.package not in packages:
            bad_testcases.append(name)
        else:
            item['testcase'] = testcase
            validated.append(item)

    if bad_testcases:
        request.errors.add('querystring', 'testcase_feedback',
                           "Invalid testcase names specified: {}".format(
                               ", ".join(bad_testcases)))
    else:
        request.validated["testcase_feedback"] = validated


def validate_comment_id(request):
    """Ensure that a given comment id exists"""
    idx = request.matchdict['id']

    try:
        idx = int(idx)
    except ValueError:
        request.errors.add('url', 'id', 'Comment id must be an int')
        request.errors.status = HTTPBadRequest.code
        return

    comment = Comment.get(request.matchdict['id'], request.db)

    if comment:
        request.validated['comment'] = comment
    else:
        request.errors.add('url', 'id', 'Invalid comment id')
        request.errors.status = HTTPNotFound.code


def validate_override_builds(request):
    """ Ensure that the build is properly tagged """
    nvrs = splitter(request.validated['nvr'])
    db = request.db

    if not nvrs:
        request.errors.add('body', 'nvr',
                           'A comma-separated list of NVRs is required.')
        return

    if len(nvrs) != 1 and request.validated['edited']:
        request.errors.add('body', 'nvr', 'Cannot combine multiple NVRs '
                           'with editing a buildroot override.')
        return

    builds = []
    for nvr in nvrs:
        result = _validate_override_build(request, nvr, db)
        if not result:
            # Then there was some error.
            return
        builds.append(result)

    request.validated['builds'] = builds


def _validate_override_build(request, nvr, db):
    """ Workhorse function for validate_override_builds """
    build = Build.get(nvr, db)
    if build is not None:
        if not build.release:
            # Oddly, the build has no associated release.  Let's try to figure
            # that out and apply it.
            tag_types, tag_rels = Release.get_tags(request.db)
            valid_tags = tag_types['candidate'] + tag_types['testing']

            tags = [tag['name'] for tag in request.koji.listTags(nvr)
                    if tag['name'] in valid_tags]

            release = Release.from_tags(tags, db)

            if release is None:
                request.errors.add('body', 'nvr', 'Invalid build.  Couldn\'t '
                                   'determine release from koji tags.')
                return

            build.release = release

        for tag in build.get_tags():
            if tag in (build.release.candidate_tag, build.release.testing_tag):
                # The build is tagged as a candidate or testing
                break

        else:
            # The build is tagged neither as a candidate or testing, it can't
            # be in a buildroot override
            request.errors.add('body', 'nvr', 'Invalid build.  It must be '
                               'tagged as either candidate or testing.')
            return

    else:
        tag_types, tag_rels = Release.get_tags(request.db)
        valid_tags = tag_types['candidate'] + tag_types['testing']

        try:
            tags = [tag['name'] for tag in request.koji.listTags(nvr)
                    if tag['name'] in valid_tags]
        except Exception as e:
            request.errors.add('body', 'nvr', "Couldn't determine koji tags "
                               "for %s, %r" % (nvr, str(e)))
            return

        release = Release.from_tags(tags, db)

        if release is None:
            request.errors.add('body', 'nvr', 'Invalid build')
            return

        pkgname, version, rel = get_nvr(nvr)
        package = Package.get(pkgname, db)
        if not package:
            package = Package(name=pkgname)
            db.add(package)
            db.flush()

        build = Build(nvr=nvr, release=release, package=package)
        db.add(build)
        db.flush()

    return build


def validate_expiration_date(request):
    """Ensure the expiration date is in the future"""
    expiration_date = request.validated.get('expiration_date')

    if expiration_date is None:
        return

    now = datetime.utcnow()

    if expiration_date <= now:
        request.errors.add('body', 'expiration_date',
                           'Expiration date in the past')
        return

    settings = request.registry.settings
    days = int(settings.get('buildroot_limit', 31))
    limit = now + timedelta(days=days)
    if expiration_date > limit:
        request.errors.add('body', 'expiration_date',
                           'Expiration date may not be longer than %i' % days)
        return

    request.validated['expiration_date'] = expiration_date


def validate_captcha(request):
    """ A validator for our captcha. """

    settings = request.registry.settings
    data = request.validated

    email = data.get('email', None)
    author = email or (request.user and request.user.name)
    anonymous = bool(email) or not author

    key = data.pop('captcha_key')
    value = data.pop('captcha_value')

    if anonymous and settings.get('captcha.secret'):
        if not key:
            request.errors.add('body', 'captcha_key',
                               'You must provide a captcha_key.')
            request.errors.status = HTTPBadRequest.code
            return

        if not value:
            request.errors.add('body', 'captcha_value',
                               'You must provide a captcha_value.')
            request.errors.status = HTTPBadRequest.code
            return

        if 'captcha' not in request.session:
            request.errors.add('session', 'captcha',
                               'Captcha cipher not in the session (replay).')
            request.errors.status = HTTPBadRequest.code
            return

        if request.session['captcha'] != key:
            request.errors.add(
                'session', 'captcha', 'No captcha session cipher match (replay). %r %r' % (
                    request.session['captcha'], key))
            request.errors.status = HTTPBadRequest.code
            return

        if not captcha.validate(request, key, value):
            request.errors.add('body', 'captcha_value',
                               'Incorrect response to the captcha.')
            request.errors.status = HTTPBadRequest.code
            return

        # Nuke this to stop replay attacks.  Once valid, never again.
        del request.session['captcha']


def validate_stack(request):
    """Make sure this singular stack exists"""
    name = request.matchdict.get('name')
    stack = Stack.get(name, request.db)
    if stack:
        request.validated['stack'] = stack
    else:
        request.errors.add('querystring', 'stack',
                           'Invalid stack specified: {}'.format(name))
        request.errors.status = HTTPNotFound.code


def _get_valid_requirements(request):
    """ Returns a list of valid testcases from taskotron. """
    for testcase in taskotron_results(request.registry.settings, 'testcases'):
        yield testcase['name']


def validate_requirements(request):
    requirements = request.validated.get('requirements')

    if requirements is None:  # None is okay
        request.validated['requirements'] = None
        return

    requirements = tokenize(requirements)
    valid_requirements = _get_valid_requirements(request)

    for requirement in requirements:
        if requirement not in valid_requirements:
            request.errors.add(
                'querystring', 'requirements',
                'Invalid requirement specified: %s.  Must be one of %s' % (
                    requirement, ", ".join(valid_requirements)))
            request.errors.status = HTTPBadRequest.code
            return


def validate_request(request):
    """
    Ensure that this update is newer than whatever is in the requested state
    """
    log.debug('validating request')
    update = request.validated['update']
    db = request.db

    if 'request' not in request.validated:
        # Invalid request. Let the colander error from our schemas.py bubble up.
        return
    if request.validated['request'] is UpdateRequest.stable:
        target = UpdateStatus.stable
    elif request.validated['request'] is UpdateRequest.testing:
        target = UpdateStatus.testing
    else:
        # obsolete, unpush, revoke...
        return

    for build in update.builds:
        other_builds = db.query(Build).join(Update).filter(
            and_(Build.package == build.package, Build.nvr != build.nvr, Update.status == target,
                 Update.release == update.release)).all()
        for other_build in other_builds:

            log.info('Checking against %s' % other_build.nvr)

            if rpm.labelCompare(other_build.evr, build.evr) > 0:
                log.debug('%s is older than %s', build.evr, other_build.evr)
                request.errors.add(
                    'querystring', 'update',
                    'Cannot submit %s %s to %s since it is older than %s' % (
                        build.package.name, build.evr, target.description, other_build.evr))
                request.errors.status = HTTPBadRequest.code
                return
