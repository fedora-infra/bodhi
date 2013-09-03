import rpm

from sqlalchemy.sql import or_

from . import log
from .models import (Release, Package, Build, Update, UpdateStatus,
                     UpdateRequest, UpdateSeverity, UpdateType,
                     UpdateSuggestion, User)
from .util import get_nvr


def validate_nvrs(request):
    for build in request.validated.get('builds', []):
        try:
            name, version, release = get_nvr(build)
            request.buildinfo[build]['nvr'] = name, version, release
            if '' in (name, version, release):
                raise ValueError
        except:
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
        release = Release.from_tags(tags, db)
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
                people, groups = package.get_pkg_pushers(request.pkgdb)
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

def validate_releases(request):
    """Make sure those releases exist"""
    releases = request.GET.get("releases", '')
    if not releases:
        return

    releases = releases.split(',')
    db = request.db
    bad_releases = []
    validated_releases = []

    for r in releases:
        release = db.query(Release).filter(or_(Release.name==r,
                                               Release.version==r)).first()

        if not release:
            bad_releases.append(r)

        validated_releases.append(release)

    if bad_releases:
        request.errors.add('querystring', 'releases',
                           "Invalid releases specified: {}".format(
                               ", ".join(bad_releases)))

    else:
        request.validated["releases"] = validated_releases

def validate_username(request):
    """Make sure this user exists"""
    username = request.GET.get("username", "")
    if not username:
        return

    db = request.db
    user = db.query(User).filter_by(name=username).first()

    if user:
        request.validated["user"] = user

    else:
        request.errors.add("querystring", "username",
                           "Invalid username specified: {}".format(username))
