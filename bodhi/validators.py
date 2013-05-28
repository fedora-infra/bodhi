import rpm
import urllib2
import logging
import tw2.core as twc

from pyramid.threadlocal import get_current_request
from pyramid.security import authenticated_userid

from bodhi.models import DBSession, Release, Package, Build, Update
from bodhi.util import get_nvr, get_pkg_pushers
from bodhi import buildsys

log = logging.getLogger(__name__)

class BuildValidator(twc.Validator):
    required = True
    msgs = {
        'badbuild': "Invalid build. Must be in name-version-release format.",
    }

    def _validate_python(self, value, state=None):
        super(BuildValidator, self)._validate_python(value, state)

        builds = [pkg['package'] for pkg in value if pkg['package']]
        tag_types, tag_rels = Release.get_tags()
        candidate_tags = tag_types['candidate']
        koji = buildsys.get_session()
        session = DBSession()

        self.validate_builds(builds)
        for build in builds:
            nvr = get_nvr(build)
            tags = koji.listTags(build)
            self.validate_tags(build, tags, tag_types, candidate_tags, koji)
            self.validate_version(build, nvr, session)
            self.validate_uniqueness(build, builds, nvr)
            self.validate_acls(build, nvr, tags, tag_rels, session)

    def validate_builds(self, builds):
        if not builds:
            raise twc.ValidationError('badbuild', self)
        for build in builds:
            try:
                name, version, release = get_nvr(build)
                if '' in (name, version, release):
                    raise ValueError
            except:
                raise twc.ValidationError('badbuild', self)

    def validate_tags(self, build, tags, tag_types, candidate_tags, koji):
        """ Ensure everything is tagged properly """
        # TODO: if we're editing and update, allow testing tags
        valid = False
        for tag in tags:
            if tag['name'] in candidate_tags:
                valid = True
                break
        if not valid:
            raise twc.ValidationError('Invalid tag: %s tagged with %s' %
                    (build, candidate_tags), self)

    def validate_version(self, build, nvr, session):
        """ Ensure no builds are older than any that we know of """
        pkg = session.query(Package).filter_by(name=nvr[0]).first()
        if pkg:
            last = session.query(Build).filter_by(package=pkg) \
                          .order_by(Build.id.desc()).limit(1).first()
            if last:
                if rpm.labelCompare(nvr, get_nvr(last.nvr)) < 0:
                    raise twc.ValidationError(
                            'Invalid build: %s is older than %s' %
                            (build, last.nvr))

    def validate_uniqueness(self, build, builds, nvr):
        """ Check for multiple builds from the same package """
        seen_build = 0
        for other_build in builds:
            other_build_nvr = get_nvr(other_build)
            if build == other_build:
                seen_build += 1
                if seen_build > 1:
                    raise twc.ValidationError(
                            'Duplicate builds: %s' % build, self)
                continue
            if nvr[0] == other_build_nvr[0]:
                raise twc.ValidationError(
                        "Multiple %s builds specified: %s & %s" % (
                            nvr[0], build, other_build))

    def validate_acls(self, build, nvr, tags, tag_rels, session):
        """ Ensure this user has commit privs to these builds """
        pkgdb_args = {
            'collectionName': 'Fedora',
            'collectionVersion': 'devel',
        }
        for tag in tags:
            release = session.query(Release) \
                    .filter_by(name=tag_rels[tag['name']]).one()
            pkgdb_args['collectionName'] = release.collection_name
            pkgdb_args['collectionVersion'] = str(release.get_version())
            break
        try:
            people, groups = get_pkg_pushers(nvr[0], **pkgdb_args)
            committers, watchers = people
            groups, notify_groups = groups
        except Exception, e:
            log.exception(e)
            raise twc.ValidationError(
                    "Unable to access the Package Database. "
                    "Please try again later.")

        request = get_current_request()
        user = request.user
        if user.name not in committers:
            # Allow certain groups to push updates for any package
            admin_groups = request.registry.settings['admin_packager_groups'].split()
            groups = [group.name for group in request.user.groups]
            for group in admin_groups:
                if group in groups:
                    break
            else:
                raise twc.ValidationError(
                    "%s does not have commit access to %s" % (user.name, nvr[0]))


class UpdateValidator(twc.Validator):

    def _validate_python(self, value, state=None):
        super(UpdateValidator, self)._validate_python(value, state)

        # If we are not editing an update, check if it is a duplicate
        if not value['id']:
            if value['packages'] is not twc.validation.Invalid:
                session = DBSession()
                for pkg in value['packages']:
                    build = pkg['package']
                    exists = session.query(Build).filter_by(nvr=build).first()
                    if exists:
                        raise twc.ValidationError(
                                "Update for %s already exists" % build, self)
