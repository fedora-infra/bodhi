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

import re

import colander

from bodhi.server import util
from bodhi.server.models import (ReleaseState, UpdateRequest, UpdateSeverity, UpdateStatus,
                                 UpdateSuggestion, UpdateType)
from bodhi.server.validators import validate_csrf_token


CVE_REGEX = re.compile(r"CVE-[0-9]{4,4}-[0-9]{4,}")


class CSRFProtectedSchema(colander.MappingSchema):
    csrf_token = colander.SchemaNode(
        colander.String(),
        name="csrf_token",
        validator=validate_csrf_token,
    )


class Bugs(colander.SequenceSchema):
    bug = colander.SchemaNode(colander.String(), missing=None)


class Builds(colander.SequenceSchema):
    build = colander.SchemaNode(colander.String())


class CVE(colander.String):
    def deserialize(self, node, cstruct):
        value = super(CVE, self).deserialize(node, cstruct)

        if CVE_REGEX.match(value) is None:
            raise colander.Invalid(node, '"%s" is not a valid CVE id' % value)

        return value


class CVEs(colander.SequenceSchema):
    cve = colander.SchemaNode(CVE())


class Packages(colander.SequenceSchema):
    package = colander.SchemaNode(colander.String())


class Releases(colander.SequenceSchema):
    release = colander.SchemaNode(colander.String())


class Groups(colander.SequenceSchema):
    group = colander.SchemaNode(colander.String())


class Updates(colander.SequenceSchema):
    update = colander.SchemaNode(colander.String())


class BugFeedback(colander.MappingSchema):
    bug_id = colander.SchemaNode(colander.Integer())
    karma = colander.SchemaNode(
        colander.Integer(),
        validator=colander.Range(min=-1, max=1),
        missing=0,
    )


class BugFeedbacks(colander.SequenceSchema):
    bug_feedback = BugFeedback()


class TestcaseFeedback(colander.MappingSchema):
    testcase_name = colander.SchemaNode(colander.String())
    karma = colander.SchemaNode(
        colander.Integer(),
        validator=colander.Range(min=-1, max=1),
        missing=0,
    )


class TestcaseFeedbacks(colander.SequenceSchema):
    testcase_feedback = TestcaseFeedback()


class SaveCommentSchema(CSRFProtectedSchema, colander.MappingSchema):
    update = colander.SchemaNode(colander.String())
    text = colander.SchemaNode(
        colander.String(),
        missing='',
    )
    karma = colander.SchemaNode(
        colander.Integer(),
        validator=colander.Range(min=-1, max=1),
        missing=0,
    )
    karma_critpath = colander.SchemaNode(
        colander.Integer(),
        validator=colander.Range(min=-1, max=1),
        missing=0,
    )
    bug_feedback = BugFeedbacks(missing=[])
    testcase_feedback = TestcaseFeedbacks(missing=[])

    # Optional
    captcha_key = colander.SchemaNode(colander.String(), missing=None)
    captcha_value = colander.SchemaNode(colander.String(), missing=None)
    email = colander.SchemaNode(
        colander.String(),
        validator=colander.Email(),
        missing=None,
    )


class SaveUpdateSchema(CSRFProtectedSchema, colander.MappingSchema):
    builds = Builds(colander.Sequence(accept_scalar=True),
                    preparer=[util.splitter])

    bugs = Bugs(colander.Sequence(accept_scalar=True), missing=None, preparer=[util.splitter])

    close_bugs = colander.SchemaNode(
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
        validator=colander.Length(min=2),
    )
    autokarma = colander.SchemaNode(
        colander.Boolean(),
        missing=True,
    )
    stable_karma = colander.SchemaNode(
        colander.Integer(),
        validator=colander.Range(min=1),
        missing=3,
    )
    unstable_karma = colander.SchemaNode(
        colander.Integer(),
        validator=colander.Range(max=-1),
        missing=-3,
    )
    suggest = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf(UpdateSuggestion.values()),
        missing='unspecified',
    )
    edited = colander.SchemaNode(
        colander.String(),
        missing='',
    )
    requirements = colander.SchemaNode(
        colander.String(),
        missing=None,
    )
    require_bugs = colander.SchemaNode(
        colander.Boolean(),
        missing=True,
    )
    require_testcases = colander.SchemaNode(
        colander.Boolean(),
        missing=True,
    )


class Cosmetics(colander.MappingSchema):
    display_user = colander.SchemaNode(
        colander.Boolean(true_choices=('true', '1')),
        location="querystring",
        missing=True,
    )


class PaginatedSchema(colander.MappingSchema):
    chrome = colander.SchemaNode(
        colander.Boolean(true_choices=('true', '1')),
        location="querystring",
        missing=True,
    )

    page = colander.SchemaNode(
        colander.Integer(),
        validator=colander.Range(min=1),
        location="querystring",
        missing=1,
    )

    rows_per_page = colander.SchemaNode(
        colander.Integer(),
        validator=colander.Range(min=1, max=1000),
        location="querystring",
        missing=20,
    )


class SearchableSchema(colander.MappingSchema):
    like = colander.SchemaNode(
        colander.String(),
        location="querystring",
        missing=None,
    )


class ListReleaseSchema(PaginatedSchema):
    name = colander.SchemaNode(
        colander.String(),
        location="querystring",
        missing=None,
    )

    updates = Updates(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )

    packages = Packages(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )


class SaveReleaseSchema(CSRFProtectedSchema, colander.MappingSchema):
    name = colander.SchemaNode(
        colander.String(),
    )
    long_name = colander.SchemaNode(
        colander.String(),
    )
    version = colander.SchemaNode(
        colander.String(),
        missing=None,
    )
    branch = colander.SchemaNode(
        colander.String(),
    )
    id_prefix = colander.SchemaNode(
        colander.String(),
    )
    dist_tag = colander.SchemaNode(
        colander.String(),
    )
    stable_tag = colander.SchemaNode(
        colander.String(),
    )
    testing_tag = colander.SchemaNode(
        colander.String(),
    )
    candidate_tag = colander.SchemaNode(
        colander.String(),
    )
    pending_signing_tag = colander.SchemaNode(
        colander.String(),
        missing="",
    )
    pending_testing_tag = colander.SchemaNode(
        colander.String(),
        missing="",
    )
    pending_stable_tag = colander.SchemaNode(
        colander.String(),
        missing="",
    )
    override_tag = colander.SchemaNode(
        colander.String(),
    )
    state = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf(ReleaseState.values()),
        missing="disabled",
    )
    edited = colander.SchemaNode(
        colander.String(),
        missing=None,
    )


class ListStackSchema(PaginatedSchema, SearchableSchema):
    name = colander.SchemaNode(
        colander.String(),
        location="querystring",
        missing=None,
    )

    packages = Packages(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )


class SaveStackSchema(CSRFProtectedSchema, colander.MappingSchema):
    name = colander.SchemaNode(
        colander.String(),
    )

    packages = Packages(
        colander.Sequence(accept_scalar=True),
        missing=None,
        preparer=[util.splitter],
    )

    description = colander.SchemaNode(
        colander.String(),
        missing=None,
    )

    requirements = colander.SchemaNode(
        colander.String(),
        missing=None,
    )


class ListUserSchema(PaginatedSchema, SearchableSchema):
    name = colander.SchemaNode(
        colander.String(),
        location="querystring",
        missing=None,
    )

    groups = Groups(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )

    updates = Updates(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )

    packages = Packages(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )


class ListUpdateSchema(PaginatedSchema, SearchableSchema, Cosmetics):
    alias = Builds(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )

    approved_since = colander.SchemaNode(
        colander.DateTime(),
        location="querystring",
        missing=None,
    )

    approved_before = colander.SchemaNode(
        colander.DateTime(),
        location="querystring",
        missing=None,
    )

    bugs = Bugs(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )

    builds = Builds(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )

    critpath = colander.SchemaNode(
        colander.Boolean(true_choices=('true', '1')),
        location="querystring",
        missing=None,
    )

    cves = CVEs(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )

    locked = colander.SchemaNode(
        colander.Boolean(true_choices=('true', '1')),
        location="querystring",
        missing=None,
    )

    modified_since = colander.SchemaNode(
        colander.DateTime(),
        location="querystring",
        missing=None,
    )

    modified_before = colander.SchemaNode(
        colander.DateTime(),
        location="querystring",
        missing=None,
    )

    packages = Packages(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )

    pushed = colander.SchemaNode(
        colander.Boolean(true_choices=('true', '1')),
        location="querystring",
        missing=None,
    )

    pushed_since = colander.SchemaNode(
        colander.DateTime(),
        location="querystring",
        missing=None,
    )

    pushed_before = colander.SchemaNode(
        colander.DateTime(),
        location="querystring",
        missing=None,
    )

    releases = Releases(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )

    # This singular version of the plural "releases" is purely for bodhi1
    # backwards compat (mostly for RSS feeds) - threebean
    release = colander.SchemaNode(
        colander.String(),
        location="querystring",
        missing=None,
    )

    request = colander.SchemaNode(
        colander.String(),
        location="querystring",
        missing=None,
        validator=colander.OneOf(UpdateRequest.values()),
    )

    severity = colander.SchemaNode(
        colander.String(),
        location="querystring",
        missing=None,
        validator=colander.OneOf(UpdateSeverity.values()),
    )

    status = colander.SchemaNode(
        colander.String(),
        location="querystring",
        missing=None,
        validator=colander.OneOf(UpdateStatus.values()),
    )

    submitted_since = colander.SchemaNode(
        colander.DateTime(),
        location="querystring",
        missing=None,
    )

    submitted_before = colander.SchemaNode(
        colander.DateTime(),
        location="querystring",
        missing=None,
    )

    suggest = colander.SchemaNode(
        colander.String(),
        location="querystring",
        missing=None,
        validator=colander.OneOf(UpdateSuggestion.values()),
    )

    type = colander.SchemaNode(
        colander.String(),
        location="querystring",
        missing=None,
        validator=colander.OneOf(UpdateType.values()),
    )

    user = colander.SchemaNode(
        colander.String(),
        location="querystring",
        missing=None,
    )

    updateid = Builds(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )


class ListPackageSchema(PaginatedSchema, SearchableSchema):
    name = colander.SchemaNode(
        colander.String(),
        location="querystring",
        missing=None,
    )


class ListBuildSchema(PaginatedSchema):
    nvr = colander.SchemaNode(
        colander.String(),
        location="querystring",
        missing=None,
    )

    packages = Packages(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )

    releases = Releases(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )

    updates = Updates(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )


class UpdateRequestSchema(CSRFProtectedSchema, colander.MappingSchema):
    request = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf(UpdateRequest.values()),
    )


class ListCommentSchema(PaginatedSchema, SearchableSchema):
    updates = Updates(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )

    packages = Packages(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )

    user = colander.SchemaNode(
        colander.String(),
        location="querystring",
        missing=None,
    )

    update_owner = colander.SchemaNode(
        colander.String(),
        location="querystring",
        missing=None,
    )

    ignore_user = colander.SchemaNode(
        colander.String(),
        location="querystring",
        missing=None,
    )

    anonymous = colander.SchemaNode(
        colander.Boolean(true_choices=('true', '1')),
        location="querystring",
        missing=None,
    )

    since = colander.SchemaNode(
        colander.DateTime(),
        location="querystring",
        missing=None,
    )


class ListOverrideSchema(PaginatedSchema, SearchableSchema, Cosmetics):
    expired = colander.SchemaNode(
        colander.Boolean(true_choices=('true', '1')),
        location="querystring",
        missing=None,
    )

    packages = Packages(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )

    releases = Releases(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )

    user = colander.SchemaNode(
        colander.String(),
        location="querystring",
        missing=None,
    )


class SaveOverrideSchema(CSRFProtectedSchema, colander.MappingSchema):
    nvr = colander.SchemaNode(
        colander.String(),
    )

    notes = colander.SchemaNode(
        colander.String(),
        validator=colander.Length(min=2),
    )

    expiration_date = colander.SchemaNode(
        colander.DateTime(default_tzinfo=None),
    )

    expired = colander.SchemaNode(
        colander.Boolean(),
        missing=False,
    )

    edited = colander.SchemaNode(
        colander.String(),
        missing=None,
    )
