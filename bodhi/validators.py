import rpm
import tw2.core as twc

from bodhi.models import DBSession, Release, Package, Build, Update
from bodhi.util import get_nvr
from bodhi import buildsys


class BuildValidator(twc.Validator):
    required = True
    msgs = {
        'badbuild': "Invalid build. Must be in name-version-release format.",
    }

    def validate_python(self, value, state=None):
        super(BuildValidator, self).validate_python(value, state)
        builds = [pkg['package'] for pkg in value if pkg['package']]
        if not builds:
            raise twc.Validator('badbuild', self)
        for build in builds:
            try:
                name, version, release = get_nvr(build)
                if '' in (name, version, release):
                    raise ValueError
            except:
                raise twc.ValidationError('badbuild', self)

        # TODO: if we're editing and update, allow testing tags
        session = DBSession()
        candidate_tags = [r.candidate_tag for r in session.query(Release).all()]
        koji = buildsys.get_session()

        for build in builds:
            nvr = get_nvr(build)

            # Ensure everything is tagged properly.
            tags = koji.listTags(build)
            valid = False
            for tag in tags:
                if tag['name'] in candidate_tags:
                    valid = True
                    break
            if not valid:
                raise twc.ValidationError('Invalid tag: %s tagged with %s' %
                        (build, candidate_tags), self)

            # Ensure no builds are older than any that we know of
            pkg = session.query(Package).filter_by(name=nvr[0]).first()
            if pkg:
                last = session.query(Build).filter_by(package=pkg) \
                              .order_by(Build.id.desc()).limit(1).first()
                if last:
                    if rpm.labelCompare(nvr, get_nvr(last.nvr)) < 0:
                        raise twc.ValidationError(
                                'Invalid build: %s is older than %s' %
                                (build, last.nvr))

            # Check for multiple builds from the same package
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


class UpdateValidator(twc.Validator):

    def validate_python(self, value, state=None):
        super(UpdateValidator, self).validate_python(value, state)

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
