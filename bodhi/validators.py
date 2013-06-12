import rpm
import logging
import colander

from kitchen.iterutils import iterate

from bodhi.models import Release, Package, Build
from bodhi.models import UpdateType, UpdateSeverity, UpdateSuggestion, UpdateRequest
from bodhi.util import get_nvr, get_pkg_pushers

log = logging.getLogger(__name__)


def build_splitter(value):
    """Parse a string or list of comma or space delimited builds"""
    builds = []
    for v in iterate(value):
        for build in v.replace(',', ' ').split():
            builds.append(build)
    return builds


def validate_nvrs(node, builds, kw):
    nvrs = []
    for build in builds:
        try:
            name, version, release = get_nvr(build)
            if '' in (name, version, release):
                raise ValueError
            nvrs.append((name, version, release))
        except:
            raise colander.Invalid(node, 'Invalid build not in '
                                   'name-version-release format: %s' % build)


def validate_tags(node, build, tags, kw):
    """ Ensure everything is tagged properly """
    # TODO: if we're editing and update, allow testing tags
    candidate_tags = kw['tag_types']['candidate']
    valid = False
    for tag in tags:
        if tag['name'] in candidate_tags:
            valid = True
            break
    if not valid:
        raise colander.Invalid(node, 'Invalid tag: {} tagged with '
                               '{}'.format(build, candidate_tags))


def validate_acls(node, build, tags, kw):
    """Ensure this user has commit privs to these builds or is an admin"""
    settings = kw['settings']
    session = kw['session']
    tag_rels = kw['tag_rels']
    user = kw['user']
    acl_system = settings['acl_system']
    package = build[0]
    committers = []
    watchers = []
    groups = []
    notify_groups = []

    if acl_system == 'pkgdb':
        pkgdb_args = {'collectionName': 'Fedora', 'collectionVersion': 'devel'}
        for tag in tags:
            release = session.query(Release) \
                    .filter_by(name=tag_rels[tag['name']]).one()
            pkgdb_args['collectionName'] = release.collection_name
            pkgdb_args['collectionVersion'] = str(release.get_version())
            break
        try:
            people, groups = get_pkg_pushers(package, **pkgdb_args)
            committers, watchers = people
            groups, notify_groups = groups
        except Exception, e:
            log.exception(e)
            raise colander.Invalid(node, "Unable to access the Package Database. "
                                   "Please try again later.")
    elif acl_system == 'dummy':
        people, groups = (['guest'], ['guest']), (['guest'], ['guest'])
        committers, watchers = people
    else:
        log.warn('No bodhi acl_system configured')

    if user.name not in committers:
        # Allow certain groups to push updates for any package
        admin_groups = settings['admin_packager_groups'].split()
        groups = [group.name for group in user.groups]
        for group in admin_groups:
            if group in groups:
                log.debug('{} is in {} admin group'.format(user.name, group))
                break
        else:
            raise colander.Invalid(node, "{} does not have commit access to {}".format(user.name, package))


def validate_version(node, nvr, kw):
    """ Ensure no builds are older than any that we know of """
    session = kw['session']
    pkg = session.query(Package).filter_by(name=nvr[0]).first()
    if pkg:
        last = session.query(Build).filter_by(package=pkg) \
                      .order_by(Build.id.desc()).limit(1).first()
        if last:
            if rpm.labelCompare(nvr, get_nvr(last.nvr)) < 0:
                raise colander.Invalid(node, 'Invalid build: {} is older than '
                                       '{}'.format('-'.join(nvr), last.nvr))


def validate_uniqueness(node, build, builds, nvr):
    """ Check for multiple builds from the same package """
    seen_build = 0
    for other_build in builds:
        other_build_nvr = get_nvr(other_build)
        if build == other_build:
            seen_build += 1
            if seen_build > 1:
                raise colander.Invalid(node, 'Duplicate builds: {}'.format(build))
            continue
        if nvr[0] == other_build_nvr[0]:
            raise colander.Invalid(node, "Multiple {} builds specified: {} & "
                                   "{}".format(nvr[0], build, other_build))


def validate_unique_builds(node, build, kw):
    # If we're editing an update, don't check for duplicate builds
    session = kw['session']
    if kw.get('edited'):
        log.debug('Editing update; skipping validate_unique_builds')
        return
    if session.query(Build).filter_by(nvr=build).first():
        raise colander.Invalid(node, "Update for {} already exists".format(build))


class UpdateSchema(colander.MappingSchema):

    @colander.instantiate(
        colander.Sequence(accept_scalar=True),
        preparer=[build_splitter]
    )
    class builds(colander.SequenceSchema):
        build = colander.SchemaNode(
            colander.String(),
            title='Build name-version-release',
        )

    @colander.deferred
    def validator(node, kw):
        def _validate_builds(node, cstruct):
            koji = kw['koji']
            builds = cstruct['builds']
            validate_nvrs(node, builds, kw)
            for build in builds:
                validate_unique_builds(node, build, kw)
                nvr = get_nvr(build)
                validate_version(node, nvr, kw)
                validate_uniqueness(node, build, builds, nvr)
                tags = koji.listTags(build)
                validate_tags(node, build, tags, kw)
                validate_acls(node, nvr, tags, kw)
        return _validate_builds

    bugs = colander.SchemaNode(
        colander.String(),
        missing='',
    )
    closebugs = colander.SchemaNode(
        colander.Boolean(),
        missing=True,
    )
    type = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf(UpdateType.values()),
    )
    request = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf(UpdateRequest.values()),
        missing='testing',
    )
    severity = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf(UpdateSeverity.values()),
        missing='unspecified',
    )
    notes = colander.SchemaNode(
        colander.String(),
        validator=colander.Length(min=10),
    )
    autokarma = colander.SchemaNode(
        colander.Boolean(),
        missing=True,
    )
    stablekarma = colander.SchemaNode(
        colander.Integer(),
        validator=colander.Range(min=1),
        missing=3,
    )
    unstablekarma = colander.SchemaNode(
        colander.Integer(),
        validator=colander.Range(max=-1),
        missing=-3,
    )
    suggest = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf(UpdateSuggestion.values()),
        missing='unspecified',
    )
