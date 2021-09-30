# Copyright © 2007-2019 Red Hat, Inc. and others.
#
# This file is part of Bodhi.
#
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
"""A collection of validators for Bodhi requests."""

from datetime import date, datetime, timedelta
from functools import wraps

from pyramid.exceptions import HTTPNotFound, HTTPBadRequest
from pyramid.httpexceptions import HTTPFound, HTTPNotImplemented
from sqlalchemy.sql import or_, and_
import colander
import koji
import pyramid.threadlocal
import rpm

from bodhi.server.config import config
from bodhi.server.exceptions import BodhiException
from . import buildsys, log
from .models import (
    Build,
    Bug,
    Comment,
    ContentType,
    Group,
    Package,
    PackageManager,
    Release,
    RpmBuild,
    ReleaseState,
    TestCase,
    TestGatingStatus,
    Update,
    UpdateStatus,
    UpdateRequest,
    UpdateSeverity,
    UpdateType,
    UpdateSuggestion,
    User,
)
from .util import (
    splitter,
    tokenize,
    taskotron_results,
)


csrf_error_message = """CSRF tokens do not match.  This happens if you have
the page open for a long time. Please reload the page and try to submit your
data again. Make sure to save your input somewhere before reloading.
""".replace('\n', ' ')


def postschema_validator(f):
    """
    Modify a validator function, so that it is skipped if schema validation already failed.

    Args:
        f (callable): The function we are wrapping.
    Returns:
        callable: The wrapped function.
    """
    @wraps(f)
    def validator(request, **kwargs):
        """
        Run the validator, but only if there aren't errors and there is validated data.

        Args:
            request (pyramid.request.Request): The current web request.
            kwargs (dict): The other arguments to pass on to the wrapped validator.
        """
        # The check on request.errors is to make sure we don't bypass other checks without
        # failing the request
        if len(request.validated) == 0 and len(request.errors) > 0:
            return

        f(request, **kwargs)

    return validator


# This one is a colander validator which is different from the cornice
# validators defined elsewhere.
def validate_csrf_token(node, value):
    """
    Ensure that the value is the expected CSRF token.

    Args:
        node (colander.SchemaNode): The Colander Schema Node that validates the token.
        value (str): The value of the CSRF to be validated.
    Raises:
        colander.Invalid: If the CSRF token does not match the expected value.
    """
    request = pyramid.threadlocal.get_current_request()
    expected = request.session.get_csrf_token()
    if value != expected:
        raise colander.Invalid(node, csrf_error_message)


def cache_tags(request, build):
    """
    Cache the tags for a koji build.

    Args:
        request (pyramid.request.Request): The current request.
        build (str): The NVR of the build to cache.
    Returns:
        list or None: The list of tags, or None if there was a failure communicating with koji.
    """
    if build in request.buildinfo and 'tags' in request.buildinfo[build]:
        return request.buildinfo[build]['tags']
    tags = None
    try:
        tags = [tag['name'] for tag in request.koji.listTags(build)]
        if len(tags) == 0:
            request.errors.add('body', 'builds',
                               'Cannot find any tags associated with build: %s' % build)
    except koji.GenericError:
        request.errors.add('body', 'builds',
                           'Invalid koji build: %s' % build)
    # This might end up setting tags to None. That is expected, and indicates it failed.
    request.buildinfo[build]['tags'] = tags + request.from_tag_inherited
    return tags + request.from_tag_inherited


def cache_release(request, build):
    """
    Cache the builds release from the request.

    Args:
        request (pyramid.request.Request): The current request.
        build (str): The NVR of the build to cache.
    Returns:
        Release or None: The release object, or None if no release can be matched to the tags
            associated with the build.
    """
    if build in request.buildinfo and 'release' in request.buildinfo[build]:
        return request.buildinfo[build]['release']
    tags = cache_tags(request, build)
    if tags is None:
        return None
    build_rel = Release.from_tags(tags, request.db)
    if not build_rel:
        msg = 'Cannot find release associated with ' + \
            'build: {}, tags: {}'.format(build, tags)
        log.warning(msg)
        request.errors.add('body', 'builds', msg)
    # This might end up setting build_rel to None. That is expected, and indicates it failed.
    request.buildinfo[build]['release'] = build_rel
    return build_rel


def cache_nvrs(request, build):
    """
    Cache the NVR from the given build on the request, and the koji getBuild() response.

    Args:
        request (pyramid.request.Request): The current request.
        build (str): The NVR of the build to cache.
    Raises:
        ValueError: If the build could not be found in koji.
        koji.GenericError: If an error was thrown by koji's getBuild() call.
    """
    if build in request.buildinfo and 'nvr' in request.buildinfo[build]:
        return
    if build not in request.buildinfo:
        request.buildinfo[build] = {}

    # Request info from koji, used to split NVR and determine type
    # We use Koji's information to get the NVR split, because modules can have dashes in their
    # stream.
    kbinfo = request.koji.getBuild(build)
    if not kbinfo:
        request.buildinfo[build]['info'] = None
        request.buildinfo[build]['nvr'] = None
        raise ValueError('Build %s did not exist' % build)
    request.buildinfo[build]['info'] = kbinfo
    request.buildinfo[build]['nvr'] = kbinfo['name'], kbinfo['version'], kbinfo['release']


@postschema_validator
def validate_build_nvrs(request, **kwargs):
    """
    Ensure that the given builds reference valid Build objects.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
    for build in request.validated.get('builds') or []:  # cope with builds being None
        try:
            cache_nvrs(request, build)
            if request.validated.get('from_tag'):
                n, v, r = request.buildinfo[build]['nvr']
                release = request.db.query(Release).filter(or_(Release.name == r,
                                                               Release.name == r.upper(),
                                                               Release.version == r)).first()
                if release and release.composed_by_bodhi:
                    request.errors.add(
                        'body', 'builds',
                        f"Can't create update from tag for release"
                        f" '{release.name}' composed by Bodhi.")
        except ValueError:
            request.validated['builds'] = []
            request.errors.add('body', 'builds', 'Build does not exist: %s' % build)
            return
        except koji.GenericError:
            log.exception("Error retrieving koji build for %s" % build)
            request.validated['builds'] = []
            request.errors.add('body', 'builds',
                               'Koji error getting build: %s' % build)
            return


@postschema_validator
def validate_builds_or_from_tag_exist(request, **kwargs):
    """
    Ensure that at least one of the builds or from_tag parameters exist in the request.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
    builds = request.validated.get('builds')
    from_tag = request.validated.get('from_tag')

    if builds is None and from_tag is None:
        request.errors.add('body', 'builds,from_tag',
                           "You must specify either builds or from_tag.")

    if builds is not None:
        if not isinstance(builds, list):
            request.errors.add('body', 'builds', "The builds parameter must be a list.")
        elif len(builds) == 0:
            request.errors.add('body', 'builds', "You may not specify an empty list of builds.")

    if from_tag is not None:
        if not isinstance(from_tag, str):
            request.errors.add('body', 'from_tag', "The from_tag parameter must be a string.")
        elif len(from_tag.strip()) == 0:
            request.errors.add('body', 'from_tag', "You may not specify an empty from_tag.")


@postschema_validator
def validate_builds(request, **kwargs):
    """
    Ensure that the builds parameter is valid for the request.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
    edited = request.validated.get('edited')
    user = User.get(request.user.name)
    builds = request.validated.get('builds') or []  # cope with builds set to None

    if edited:
        up = request.db.query(Update).filter_by(alias=edited).first()
        if not up:
            request.errors.add('body', 'builds',
                               'Cannot find update to edit: %s' % edited)
            return

        # Allow admins to edit stable updates
        user_groups = set([group.name for group in user.groups])
        admin_groups = set(config['admin_packager_groups'])
        if not user_groups & admin_groups:
            if up.status is UpdateStatus.stable:
                request.errors.add('body', 'builds',
                                   'Cannot edit stable updates')

        for nvr in builds:
            # Ensure it doesn't already exist in another update
            build = request.db.query(Build).filter_by(nvr=nvr).first()
            if build and build.update is not None and up.alias != build.update.alias:
                request.errors.add('body', 'builds',
                                   "Update for {} already exists".format(nvr))

        return

    for nvr in builds:
        build = request.db.query(Build).filter_by(nvr=nvr).first()
        if build and build.update is not None:
            if build.update.status != UpdateStatus.unpushed:
                request.errors.add('body', 'builds',
                                   "Update for {} already exists".format(nvr))
                return


@postschema_validator
def validate_build_tags(request, **kwargs):
    """
    Ensure that all of the referenced builds are tagged as candidates.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
    tag_types, tag_rels = Release.get_tags(request.db)
    edited = request.validated.get('edited')
    release = None
    if edited:
        valid_tags = tag_types['candidate'] + tag_types['testing']
        update = request.db.query(Update).filter_by(alias=edited).first()
        if not update:
            # No need to tack on any more errors here, since they should have
            # already been added by `validate_builds`
            return

        release = update.release
    else:
        valid_tags = tag_types['candidate']

    from_tag = request.validated.get('from_tag')
    if from_tag:
        valid_tags.append(from_tag)

    for build in request.validated.get('builds') or []:
        valid = False
        tags = cache_tags(request, build)
        if tags is None:
            return
        build_rel = cache_release(request, build)
        if build_rel is None:
            return

        # Disallow adding builds for a different release
        if edited:
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


@postschema_validator
def validate_tags(request, **kwargs):
    """
    Ensure that the referenced tags are valid Koji tags.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
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


@postschema_validator
def validate_acls(request, **kwargs):
    """
    Ensure the user has privs to create or edit an update.

    There are two different code-paths that could pass through this validator:
    one of them is for submitting something new with a list of builds or a
    side-tag (a new update, or editing an update by changing the list of builds).
    The other is for changing the request on an existing update -- where an update
    alias has been passed to us. The latter is also used to check if a user has
    enough privs to display the edit form page in webUI.

    We need to validate that the user has commit rights on all the build
    (either the explicitly listed ones or on the ones associated with the
    pre-existing update). If a provenpackager added a build for which the
    former update submitter doesn't have commit rights, the original submitter
    will lose their privs to edit the update.

    In case of a side-tag update, we don't validate against the builds,
    but we require the submitter to be whom created the side-tag.
    The 'sidetag_owner' field is set by `validate_from_tag()`.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
    if not request.user:
        # If you're not logged in, obviously you don't have ACLs.
        request.errors.add('cookies', 'user', 'No ACLs for anonymous user')
        return
    user = User.get(request.user.name)
    user_groups = [group.name for group in user.groups]
    acl_system = config.get('acl_system')

    builds = None
    sidetag = None
    if 'builds' in request.validated:
        builds = request.validated['builds']

    if 'update' in request.validated:
        if request.validated['update'].release.state == ReleaseState.archived:
            request.errors.add('body', 'update', 'cannot edit Update for an archived Release')
            return
        builds = request.validated['update'].builds
        sidetag = request.validated['update'].from_tag

    if not builds and not sidetag:
        log.warning("validate_acls was passed data with nothing to validate.")
        request.errors.add('body', 'builds', 'ACL validation mechanism was '
                           'unable to determine ACLs.')
        return

    # Allow certain groups to push updates for any package
    admin_groups = config['admin_packager_groups']
    for group in admin_groups:
        if group in user_groups:
            log.debug(f'{user.name} is in {group} admin group')
            return

    # Make sure the user is in the mandatory packager groups. This is a
    # safeguard in the event a user has commit access on the ACL system
    # but isn't part of the mandatory groups.
    mandatory_groups = config['mandatory_packager_groups']
    for mandatory_group in mandatory_groups:
        if mandatory_group not in user_groups:
            error = (f'{user.name} is not a member of "{mandatory_group}", which is a '
                     f'mandatory packager group')
            request.errors.add('body', 'builds', error)
            return

    # If we try to create or edit a side-tag update, check if user owns the side-tag
    # The 'sidetag_owner' field is set by `validate_from_tag()`.
    if request.validated.get('from_tag') is not None:
        log.debug('Using side-tag validation method')
        sidetag = request.validated.get('from_tag')
        # the validate_from_tag() must have set the sidetag_owner field
        sidetag_owner = request.validated.get('sidetag_owner', None)
        if sidetag_owner is None:
            error = ('Update appear to be from side-tag, but we cannot determine '
                     'the side-tag owner')
            request.errors.add('body', 'builds', error)
            return

        if sidetag_owner != user.name:
            request.errors.add('body',
                               'builds',
                               f'{user.name} does not own {sidetag} side-tag')
            request.errors.status = 403
        return
    elif 'update' in request.validated and sidetag:
        # This is a simplified check to avoid quering Koji for the side-tag owner
        # The user whom created the update is surely the one owning the side-tag
        update = request.validated['update']
        if user == update.user:
            log.debug(f'{user.name} owns {update.alias} side-tag update')
        else:
            request.errors.add('body',
                               'builds',
                               f'{user.name} does not own {sidetag} side-tag')
            request.errors.status = 403
        return

    # For normal updates, check against every build
    log.debug('Using builds validation method')
    for build in builds:
        # The whole point of the blocks inside this conditional is to determine
        # the "release" and "package" associated with the given build.  For raw
        # (new) builds, we have to do that by hand.  For builds that have been
        # previously associated with an update, we can just look it up no prob.
        if 'builds' in request.validated:
            # Split out NVR data unless its already done.
            cache_nvrs(request, build)

            buildinfo = request.buildinfo[build]

            # Figure out what kind of package this should be
            try:
                ContentType.infer_content_class(
                    base=Package, build=buildinfo['info'])
            except Exception as e:
                error = 'Unable to infer content_type.  %r' % str(e)
                log.exception(error)
                request.errors.add('body', 'builds', error)
                if isinstance(e, NotImplementedError):
                    request.errors.status = HTTPNotImplemented.code
                return

            # Get the Package and Release objects
            package = Package.get_or_create(request.db, buildinfo)
            release = cache_release(request, build)
            if release is None:
                return
        elif 'update' in request.validated:
            buildinfo = request.buildinfo[build.nvr]

            # Easy to find the release and package since they're associated
            # with a pre-stored Build obj.
            package = build.package
            release = build.update.release

        # Now that we know the release and the package associated with this
        # build, we can ask our ACL system about it.
        has_access = False
        if acl_system == 'pagure':
            # Verify user's commit access
            try:
                has_access = package.hascommitaccess(user.name, release.branch)
            except RuntimeError as error:
                # If it's a RuntimeError, then the error will be logged
                # and we can return the error to the user as is
                log.error(error)
                request.errors.add('body', 'builds', str(error))
                return
            except Exception as error:
                # This is an unexpected error, so let's log it and give back
                # a generic error to the user
                log.exception(error)
                error_msg = ('Unable to access Pagure to check ACLs. '
                             'Please try again later.')
                request.errors.add('body', 'builds', error_msg)
                return
            people = [user.name]
            if has_access:
                # Retrieve people to be informed of the update
                try:
                    people = package.get_pkg_committers_from_pagure()[0]
                except Exception:
                    # This will simply mean no email will be posted to affected users
                    # Just log it.
                    log.warning(f'Unable to retrieve committers list from Pagure '
                                f'for {package.name}.')
        elif acl_system == 'dummy':
            committers = ['ralph', 'bowlofeggs', 'guest']
            if config['acl_dummy_committer']:
                committers.append(config['acl_dummy_committer'])
            if user.name in committers:
                has_access = True
            people = committers
        else:
            log.warning('No acl_system configured')
            people = None

        buildinfo['people'] = people

        if not has_access:
            request.errors.add('body', 'builds',
                               f'{user.name} does not have commit access to {package.name}')
            request.errors.status = 403


@postschema_validator
def validate_build_uniqueness(request, **kwargs):
    """
    Check for multiple builds from the same package and same release.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
    builds = request.validated.get('builds', [])
    if not builds:  # validate_build_nvrs failed
        return
    seen_build = set()
    seen_packages = set()
    for build in builds:
        rel = cache_release(request, build)
        if not rel:
            return
        if build in seen_build:
            request.errors.add('body', 'builds', f'Duplicate builds: {build}')
            return
        seen_build.add(build)

        pkg = Package.get_or_create(request.db, request.buildinfo[build])
        if (pkg, rel) in seen_packages:
            request.errors.add(
                'body', 'builds', f'Multiple {pkg.name} builds specified in {rel.name}')
            return
        seen_packages.add((pkg, rel))


@postschema_validator
def validate_enums(request, **kwargs):
    """
    Convert from strings to our enumerated types.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
    for param, enum in (("request", UpdateRequest),
                        ("severity", UpdateSeverity),
                        ("status", UpdateStatus),
                        ("suggest", UpdateSuggestion),
                        ("type", UpdateType),
                        ("content_type", ContentType),
                        ("state", ReleaseState),
                        ("package_manager", PackageManager),
                        ("gating", TestGatingStatus)):
        value = request.validated.get(param)
        if value is None:
            continue

        if isinstance(value, str):
            request.validated[param] = enum.from_string(value)
        else:
            for index, item in enumerate(value):
                value[index] = enum.from_string(item)
            request.validated[param] = value


@postschema_validator
def validate_packages(request, **kwargs):
    """
    Make sure referenced packages exist.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
    packages = request.validated.get("packages")
    if packages is None:
        return

    bad_packages = []
    validated_packages = []

    for p in packages:
        package = Package.get(p)

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


@postschema_validator
def validate_updates(request, **kwargs):
    """
    Make sure referenced updates exist.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
    updates = request.validated.get("updates")
    if updates is None:
        return

    db = request.db
    bad_updates = []
    validated_updates = []

    for u in updates:
        update = db.query(Update).filter(Update.alias == u).first()

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


@postschema_validator
def validate_groups(request, **kwargs):
    """
    Make sure the referenced groups exist.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
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


@postschema_validator
def validate_release(request, **kwargs):
    """
    Make sure the referenced release exists.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
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


@postschema_validator
def validate_releases(request, **kwargs):
    """
    Make sure referenced releases exist.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
    releases = request.validated.get("releases")
    if releases is None:
        return

    db = request.db
    bad_releases = []
    validated_releases = []

    if '__current__' in releases:
        releases.remove('__current__')
        active_releases = db.query(Release).filter(Release.state == ReleaseState.current).all()
        validated_releases.extend(active_releases)

    if '__pending__' in releases:
        releases.remove('__pending__')
        active_releases = db.query(Release).filter(Release.state == ReleaseState.pending).all()
        validated_releases.extend(active_releases)

    if '__archived__' in releases:
        releases.remove('__archived__')
        active_releases = db.query(Release).filter(Release.state == ReleaseState.archived).all()
        validated_releases.extend(active_releases)

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


@postschema_validator
def validate_bugs(request, **kwargs):
    """
    Ensure that the list of bugs are all valid integers.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
    bugs = request.validated.get('bugs')
    if bugs:
        try:
            request.validated['bugs'] = list(map(int, bugs))
        except ValueError:
            request.errors.add("querystring", "bugs",
                               "Invalid bug ID specified: {}".format(bugs))


@postschema_validator
def validate_severity(request, **kwargs):
    """
    Ensure that severity is specified for a 'security' update.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
    type = request.validated.get('type')
    severity = request.validated.get('severity')

    if type == UpdateType.security and severity == UpdateSeverity.unspecified:
        request.errors.add("body", "severity",
                           "Must specify severity for a security update")


@postschema_validator
def validate_update(request, **kwargs):
    """
    Make sure the requested update exists.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
    idx = request.validated.get('update')
    update = Update.get(idx)

    if update:
        request.validated['update'] = update
    else:
        request.errors.add('url', 'update',
                           'Invalid update specified: %s' % idx)
        request.errors.status = HTTPNotFound.code


def ensure_user_exists(param, request):
    """
    Ensure the user referenced by param exists and if it does replace it with the User object.

    Args:
        param (string): Request parameter that references a username to be validated.
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
    users = request.validated.get(param)
    if users is None:
        return

    db = request.db
    bad_users = []
    validated_users = []

    for u in users:
        user = db.query(User).filter_by(name=u).first()

        if not user:
            bad_users.append(u)
        else:
            validated_users.append(user)

    if bad_users:
        request.errors.add('querystring', param,
                           "Invalid users specified: {}".format(
                               ", ".join(bad_users)))
    else:
        request.validated[param] = validated_users


def validate_username(request, **kwargs):
    """
    Make sure the referenced user exists.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
    return ensure_user_exists("user", request)


def validate_update_owner(request, **kwargs):
    """
    Make sure the referenced update owner is an existing user.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
    return ensure_user_exists("update_owner", request)


def validate_ignore_user(request, **kwargs):
    """
    Make sure the ignore_user parameter references an existing user.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
    return ensure_user_exists("ignore_user", request)


@postschema_validator
def validate_update_id(request, **kwargs):
    """
    Ensure that a given update id exists.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
    update = Update.get(request.matchdict['id'])
    if update:
        request.validated['update'] = update
    else:
        package = Package.get(request.matchdict['id'])
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
    # not, then request.validated['update'] will be a str object.
    # So.. we have to handle either situation.  It is, however, not our
    # responsibility to put the update object back in the request.validated
    # dict.  Note, for speed purposes, sqlalchemy should cache this for us.
    if not isinstance(update, Update) and update is not None:
        update = Update.get(update)

    return update


@postschema_validator
def validate_bug_feedback(request, **kwargs):
    """
    Ensure that bug feedback references bugs associated with the given update.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
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


@postschema_validator
def validate_testcase_feedback(request, **kwargs):
    """
    Ensure that the referenced test case exists and is associated with the referenced package.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
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
    # not, then request.validated['update'] will be a str object.
    # So.. we have to handle either situation.  It is, however, not our
    # responsibility to put the update object back in the request.validated
    # dict.  Note, for speed purposes, sqlalchemy should cache this for us.
    if not isinstance(update, Update):
        update = Update.get(update)
        if not update:
            request.errors.add('url', 'id', 'Invalid update')
            request.errors.status = HTTPNotFound.code
            return

    # Get all TestCase names associated to the Update
    allowed_testcases = [tc.name
                         for build in update.builds
                         for tc in build.testcases
                         if len(build.testcases) > 0]

    bad_testcases = []
    validated = []

    for item in feedback:
        name = item.pop('testcase_name')
        testcase = TestCase.get(name)

        if not testcase or testcase.name not in allowed_testcases:
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


def validate_comment_id(request, **kwargs):
    """
    Ensure that a given comment id exists.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
    idx = request.matchdict['id']

    try:
        idx = int(idx)
    except ValueError:
        request.errors.add('url', 'id', 'Comment id must be an int')
        request.errors.status = HTTPBadRequest.code
        return

    comment = Comment.get(request.matchdict['id'])

    if comment:
        request.validated['comment'] = comment
    else:
        request.errors.add('url', 'id', 'Invalid comment id')
        request.errors.status = HTTPNotFound.code


@postschema_validator
def validate_override_builds(request, **kwargs):
    """
    Ensure that the override builds are properly referenced.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
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
    """
    Workhorse function for validate_override_builds.

    Args:
        request (pyramid.request.Request): The current request.
        nvr (str): The NVR for a :class:`Build`.
        db (sqlalchemy.orm.session.Session): A database session.
    Returns:
        bodhi.server.models.Build: A build that matches the given nvr.
    """
    build = Build.get(nvr)
    if build is not None:
        if not request.validated['edited'] and \
                build.update is not None and \
                build.update.test_gating_status == TestGatingStatus.failed:
            request.errors.add("body", "nvr", "Cannot create a buildroot override"
                               " if build's test gating status is failed.")
            return

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

        if not build.release.override_tag:
            request.errors.add("body", "nvr", "Cannot create a buildroot override because the"
                               " release associated with the build does not support it.")
            return

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

        build_info = request.koji.getBuild(nvr)
        package = Package.get_or_create(db,
                                        {'nvr': (build_info['name'],
                                                 build_info['version'],
                                                 build_info['release']),
                                         'info': build_info})

        build_class = ContentType.infer_content_class(
            base=Build, build=build_info)
        build = build_class(nvr=nvr, release=release, package=package)
        db.add(build)
        db.flush()

    return build


@postschema_validator
def validate_eol_date(request, **kwargs):
    """
    Ensure the end-of-life date is in the right format.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
    eol_date = request.validated.get('eol')
    if eol_date is None:
        return

    if not date(2100, 1, 1) > eol_date > date(1999, 1, 1):
        request.errors.add(
            'body',
            'eol',
            'End-of-life date may not be in the right range of years (2000-2100)')

        return


@postschema_validator
def validate_expiration_date(request, **kwargs):
    """
    Ensure the expiration date is in the future.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
    expiration_date = request.validated.get('expiration_date')

    if expiration_date is None:
        return

    expiration_date = expiration_date.date()
    now = datetime.utcnow().date()

    if expiration_date <= now:
        request.errors.add('body', 'expiration_date',
                           'Expiration date in the past')
        return

    days = config.get('buildroot_limit')
    limit = now + timedelta(days=days)
    if expiration_date > limit:
        request.errors.add('body', 'expiration_date',
                           'Expiration date may not be longer than %i' % days)
        return


@postschema_validator
def validate_override_notes(request, **kwargs):
    """
    Ensure the override notes is less than 500 chars.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
    notes = request.validated.get('notes')

    if notes is None:
        return

    if len(notes) > 2000:
        request.errors.add('body', 'notes',
                           'Notes may not contain more than 2000 chars')
        return

    request.validated['notes'] = notes


def _get_valid_requirements(request, requirements):
    """
    Return a list of valid testcases from taskotron.

    Args:
        request (pyramid.request.Request): The current request.
        requirements (list): A list of strings that identify test cases.
    Returns:
        generator: An iterator over the test case names that exist in taskotron.
    """
    if not requirements:
        return

    testcases = ','.join(requirements)
    for testcase in taskotron_results(config, 'testcases',
                                      max_queries=None, limit=100,
                                      name=testcases):
        yield testcase['name']


@postschema_validator
def validate_requirements(request, **kwargs):
    """
    Validate the requirements parameter for the stack.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
    requirements = request.validated.get('requirements')

    if requirements is None:  # None is okay
        request.validated['requirements'] = None
        return

    requirements = list(tokenize(requirements))
    valid_requirements = _get_valid_requirements(request, requirements)

    for requirement in requirements:
        if requirement not in valid_requirements:
            request.errors.add(
                'querystring', 'requirements',
                "Required check doesn't exist : %s" % requirement)
            request.errors.status = HTTPBadRequest.code
            return


@postschema_validator
def validate_request(request, **kwargs):
    """
    Ensure that this update is newer than whatever is in the requested state.

    Args:
        request (pyramid.request.Request): The current request.
        kwargs (dict): The kwargs of the related service definition. Unused.
    """
    log.debug('validating request')
    update = request.validated['update']
    db = request.db

    if request.validated['request'] == UpdateRequest.stable:
        target = UpdateStatus.stable
    elif request.validated['request'] is UpdateRequest.testing:
        target = UpdateStatus.testing
    else:
        # obsolete, unpush, revoke...
        return

    for build in update.builds:
        other_builds = db.query(RpmBuild).join(Update).filter(
            and_(Build.package == build.package, RpmBuild.nvr != build.nvr, Update.status == target,
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


@postschema_validator
def validate_from_tag(request: pyramid.request.Request, **kwargs: dict):
    """Check that an existing from_tag is valid and set `builds`.

    Ensure that `from_tag` is a valid Koji tag and set `builds` to latest
    builds from this tag if unset.

    Args:
        request: The current request.
        kwargs: The kwargs of the related service definition. Unused.
    """
    koji_tag = request.validated.get('from_tag')

    if koji_tag:
        # check if any existing updates use this side tag
        update = request.db.query(Update).filter_by(from_tag=koji_tag).first()
        if update:
            if request.validated.get('edited') == update.alias:
                # existing update found, but it is the one we are editing, so keep going
                pass
            else:
                request.errors.add('body', 'from_tag', "Update already exists using this side tag")
                # don't run any more validators
                request.validated = []
                return

        koji_client = buildsys.get_session()
        taginfo = koji_client.getTag(koji_tag)

        if not taginfo:
            request.errors.add('body', 'from_tag', "The supplied from_tag doesn't exist.")
            return

        # prevent user from creating an update if tag is not a side tag
        if not taginfo.get('extra', {}).get('sidetag'):
            request.errors.add('body', 'from_tag', "The supplied tag is not a side tag.")
            return

        # store side-tag owner name to be validated in ACLs
        request.validated['sidetag_owner'] = taginfo.get('extra', {}).get('sidetag_user', None)

        # add all the inherited tags of a sidetag to from_tag_inherited
        for tag in koji_client.getFullInheritance(koji_tag):
            request.from_tag_inherited.append(tag['name'])

        if request.validated.get('builds'):
            # Builds were specified explicitly, flag that `builds` wasn't filled from the Koji tag.
            request.validated['builds_from_tag'] = False
        else:
            # Builds weren't specified explicitly, pull the list of latest NVRs here, as it is
            # necessary for later validation of ACLs pertaining the respective components.
            try:
                request.validated['builds'] = [
                    b['nvr'] for b in koji_client.listTagged(koji_tag, latest=True)
                ]
            except koji.GenericError as e:
                if "invalid taginfo" in str(e).lower():
                    request.errors.add('body', 'from_tag', "The supplied from_tag doesn't exist.")
                else:
                    raise BodhiException("Encountered error while requesting tagged builds from "
                                         f"Koji: '{e}'") from e
            else:  # no Koji error, request.validated['builds'] was filled
                if not request.validated['builds']:
                    request.errors.add('body', 'from_tag',
                                       "The supplied from_tag doesn't contain any builds.")
                else:
                    # Flag that `builds` was filled from the Koji tag.
                    request.validated['builds_from_tag'] = True
