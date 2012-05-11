import tw2.core as twc

from bodhi.models import DBSession, Release
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

        # Ensure everything is tagged properly.
        # TODO: if we're editing and update, allow testing tags
        session = DBSession()
        candidate_tags = [r.candidate_tag for r in session.query(Release).all()]
        print("candidate_tags = %r" % candidate_tags)
        koji = buildsys.get_session()
        for build in builds:
            tags = koji.listTags(build)
            valid = False
            for tag in tags:
                if tag['name'] in candidate_tags:
                    valid = True
                    break
            if not valid:
                raise twc.ValidationError('Invalid tag: %s tagged with %s' %
                        (build, candidate_tags), self)
