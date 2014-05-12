from sqlalchemy.sql import or_
from pyramid.exceptions import HTTPNotFound, HTTPBadRequest

from . import log
from .models import (Release, Package, Build, Update, UpdateStatus,
                     UpdateRequest, UpdateSeverity, UpdateType,
                     UpdateSuggestion, User, Group, Comment,
                     Bug, TestCase)
from .util import get_nvr

try:
    import rpm
except ImportError:
    log.warning("Could not import 'rpm'")


def validate_nvrs(request):
    for build in request.validated.get('builds', []):
        try:
            name, version, release = get_nvr(build)
            request.buildinfo[build]['nvr'] = name, version, release
            if '' in (name, version, release):
                raise ValueError
        except:
            request.validated['builds'] = []
            request.errors.add('body', 'builds', 'Build not in '
                               'name-version-release format: %s' % build)
            return


def validate_builds(request):
    edited = request.validated.get('edited')
    settings = request.registry.settings
    user = request.user

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
        return

    for build in request.validated.get('builds', []):
        if request.db.query(Build).filter_by(nvr=build).first():
            request.errors.add('body', 'builds',
                               "Update for {} already exists".format(build))
            return


def validate_tags(request):
    """ Ensure that all of the builds are tagged as candidates """
    tag_types, tag_rels = Release.get_tags()
    if request.validated.get('edited'):
        valid_tags = tag_types['candidate'] + tag_types['testing']
    else:
        valid_tags = tag_types['candidate']
    for build in request.validated.get('builds', []):
        valid = False
        tags = request.buildinfo[build]['tags'] = [
            tag['name'] for tag in request.koji.listTags(build)
        ]
        for tag in tags:
            if tag in valid_tags:
                valid = True
                break
        if not valid:
            request.errors.add('body', 'builds', 'Invalid tag: {} tagged with '
                               '{}'.format(build, valid_tags))


def validate_acls(request):
    """Ensure this user has commit privs to these builds or is an admin"""
    db = request.db
    user = request.user
    settings = request.registry.settings
    acl_system = settings['acl_system']
    committers = []
    watchers = []
    groups = []
    notify_groups = []

    for build in request.validated.get('builds', []):
        buildinfo = request.buildinfo[build]

        # Get the Package object
        package_name = buildinfo['nvr'][0]
        package = db.query(Package).filter_by(name=package_name).first()
        if not package:
            package = Package(name=package_name)
            db.add(package)
            db.flush()

        # Determine the release associated with this build
        tags = buildinfo['tags']
        try:
            release = Release.from_tags(tags, db)
        except KeyError:
            log.exception('Unable to determine release from tags')
            request.errors.add('body', 'builds', 'Unable to determine release ' +
                               'from build: %s' % build)
            return
        buildinfo['release'] = release
        if not release:
            msg = 'Cannot find release associated with tags: {}'.format(tags)
            log.warn(msg)
            request.errors.add('body', 'builds', msg)
            return

        if acl_system == 'pkgdb':
            pkgdb_args = {
                'collectionName': release.collection_name,
                'collectionVersion': release.version,
            }
            try:
                people, groups = package.get_pkg_pushers(request.pkgdb,
                                                         **pkgdb_args)
                committers, watchers = people
                groups, notify_groups = groups
            except Exception, e:
                log.exception(e)
                request.errors.add('body', 'builds', "Unable to access the Package "
                                   "Database. " "Please try again later.")
                return
        elif acl_system == 'dummy':
            people, groups = (['guest'], ['guest']), (['guest'], ['guest'])
            committers, watchers = people
        else:
            log.warn('No bodhi acl_system configured')
            people = None

        buildinfo['people'] = people

        if user.name not in committers:
            has_access = False
            user_groups = [group.name for group in user.groups]

            # Check if this user is in a group that has access to this package
            for group in user_groups:
                if group in groups:
                    log.debug('{} is in {} group for {}'.format(user.name, group, package))
                    has_access = True
                    break

            # Allow certain groups to push updates for any package
            admin_groups = settings['admin_packager_groups'].split()
            for group in admin_groups:
                if group in user_groups:
                    log.debug('{} is in {} admin group'.format(user.name, group))
                    has_access = True
                    break

            if not has_access:
                request.errors.add('body', 'builds', "{} does not have commit "
                                   "access to {}".format(user.name, package.name))


def validate_version(request):
    """ Ensure no builds are older than any that we know of """
    db = request.db
    for build in request.validated.get('builds', []):
        nvr = request.buildinfo[build]['nvr']
        pkg = db.query(Package).filter_by(name=nvr[0]).first()
        if pkg:
            last = db.query(Build).filter_by(package=pkg) \
                     .order_by(Build.id.desc()).limit(1).first()
            if last:
                if rpm.labelCompare(nvr, get_nvr(last.nvr)) < 0:
                    request.errors.add('body', 'builds', 'Invalid build: '
                                       '{} is older than ' '{}'.format(
                                           '-'.join(nvr), last.nvr))
                    return


def validate_uniqueness(request):
    """ Check for multiple builds from the same package """
    builds = request.validated.get('builds', [])
    if not builds:  # validate_nvr failed
        return
    for build in builds:
        nvr = request.buildinfo[build]['nvr']
        seen_build = 0
        for other_build in builds:
            other_build_nvr = request.buildinfo[other_build]['nvr']
            if build == other_build:
                seen_build += 1
                if seen_build > 1:
                    request.errors.add('body', 'builds', 'Duplicate builds: '
                                       '{}'.format(build))
                    return
                continue
            if nvr[0] == other_build_nvr[0]:
                request.errors.add('body', 'builds', "Multiple {} builds "
                                   "specified: {} & {}".format(nvr[0], build,
                                   other_build))
                return


def validate_enums(request):
    """Convert from strings to our enumerated types"""
    for param, enum in (("request", UpdateRequest),
                        ("severity", UpdateSeverity),
                        ("status", UpdateStatus),
                        ("suggest", UpdateSuggestion),
                        ("type", UpdateType)):
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
        package = db.query(Package).filter(Package.name==p).first()

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
            Update.title==u,
            Update.alias==u,
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
        group = db.query(Group).filter(Group.name==g).first()

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
    release = db.query(Release).filter_by(name=releasename).first()

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
        release = db.query(Release).filter(or_(Release.name == r,
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


def validate_update_id(request):
    """Ensure that a given update id exists"""
    update = Update.get(request.matchdict['id'], request.db)
    if update:
        request.validated['update'] = update
    else:
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
    if not isinstance(update, Update) and not update is None:
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
        bug = db.query(Bug).filter(Bug.bug_id==bug_id).first()

        if not bug or not update in bug.updates:
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
        testcase = db.query(TestCase).filter(TestCase.name==name).first()

        if not testcase or not testcase.package in packages:
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
