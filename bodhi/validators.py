import rpm
import logging
import colander

from bodhi import buildsys
from bodhi.models import Release, Package, Build, DBSession
from bodhi.util import get_nvr, get_pkg_pushers

log = logging.getLogger(__name__)


def validate_nvrs(request):
    for build in request.validated.get('builds', []):
        try:
            name, version, release = get_nvr(build)
            if '' in (name, version, release):
                raise ValueError
        except:
            request.errors.add('body', 'builds', 'Build not in '
                            'name-version-release format: %s' % build)
            return



def validate_builds(request):
    # If we're editing an update, don't check for duplicate builds
    if request.validated.get('edited'):
        log.debug('Editing update; skipping validate_builds')
        return
    for build in request.validated.get('builds', []):
        if request.db.query(Build).filter_by(nvr=build).first():
            request.errors.add('body', 'builds',
                            "Update for {} already exists".format(build))
            return


def validate_tags(request):
    """ Ensure that all of the builds are tagged as candidates """
    # TODO: if we're editing and update, allow testing tags
    tag_types, tag_rels = Release.get_tags()
    candidate_tags = tag_types['candidate']
    for build in request.validated.get('builds', []):
        valid = False
        tags = request.koji.listTags(build)
        for tag in tags:
            if tag['name'] in candidate_tags:
                valid = True
                break
        if not valid:
            request.errors.add('body', 'builds', 'Invalid tag: {} tagged with '
                               '{}'.format(build, candidate_tags))


def validate_acls(request):
    """Ensure this user has commit privs to these builds or is an admin"""
    tag_types, tag_rels = Release.get_tags()
    db = request.db
    user = request.user
    settings = request.registry.settings
    acl_system = settings['acl_system']
    committers = []
    watchers = []
    groups = []
    notify_groups = []

    for build in request.validated.get('builds', []):
        package = get_nvr(build)[0]

        if acl_system == 'pkgdb':
            tags = request.koji.listTags(build)
            pkgdb_args = {
                'collectionName': 'Fedora',
                'collectionVersion': 'devel'
            }
            for tag in tags:
                release = db.query(Release) \
                            .filter_by(name=tag_rels[tag['name']]).one()
                pkgdb_args['collectionName'] = release.collection_name
                pkgdb_args['collectionVersion'] = str(release.get_version())
                break
            else:
                log.debug('Cannot find release associated with {} tags {}; '
                          'defaulting to devel'.format(build))
            try:
                people, groups = get_pkg_pushers(package, **pkgdb_args)
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

        if user.name not in committers:
            has_access = False
            user_groups = [group.name for group in user.groups]

            # Check if this user is in a group that has access to this package
            for group in user_groups:
                if group in groups:
                    log.debug('{} is in {} group for {}'.format(user.name, group, package) )
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
                                   "access to {}".format(user.name, package))


def validate_version(request):
    """ Ensure no builds are older than any that we know of """
    db = request.db
    for build in request.validated.get('builds', []):
        nvr = get_nvr(build)
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
        nvr = get_nvr(build)
        seen_build = 0
        for other_build in builds:
            other_build_nvr = get_nvr(other_build)
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
