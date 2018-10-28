# -*- coding: utf-8 -*-
# Copyright © 2013-2017 Red Hat, Inc. and others.
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
"""A set of API schemas to validate input and generate documentation."""
import re
import os

import colander

from bodhi.server import util
from bodhi.server.config import config
from bodhi.server.models import (
    ContentType,
    ReleaseState,
    UpdateRequest,
    UpdateSeverity,
    UpdateStatus,
    UpdateSuggestion,
    UpdateType,
)
from bodhi.server.validators import validate_csrf_token


CVE_REGEX = re.compile(r"CVE-[0-9]{4,4}-[0-9]{4,}")

# Retrieving list of templates from filesystem for `mail_template` validation in SaveReleaseSchema
template_directory = util.get_absolute_path(config.get('mail.templates_basepath'))
MAIL_TEMPLATES = [os.path.splitext(file)[0] for file in os.listdir(template_directory)]


class CSRFProtectedSchema(colander.MappingSchema):
    """A mixin class to validate csrf tokens."""

    csrf_token = colander.SchemaNode(
        colander.String(),
        name="csrf_token",
        validator=validate_csrf_token,
    )


class Bugs(colander.SequenceSchema):
    """A SequenceSchema to validate a list of Bug objects."""

    bug = colander.SchemaNode(colander.String(), missing=None)


class Builds(colander.SequenceSchema):
    """A SequenceSchema to validate a list of Build objects."""

    build = colander.SchemaNode(colander.String())


class CVE(colander.String):
    """A String schema to validate a CVE."""

    def deserialize(self, node, cstruct):
        """Parse a CVE out of a given API CVE parameter."""
        value = super(CVE, self).deserialize(node, cstruct)

        if CVE_REGEX.match(value) is None:
            raise colander.Invalid(node, '"%s" is not a valid CVE id' % value)

        return value


class CVEs(colander.SequenceSchema):
    """A SequenceSchema to validate a list of CVE objects."""

    cve = colander.SchemaNode(CVE())


class Packages(colander.SequenceSchema):
    """A SequenceSchema to validate a list of Package objects."""

    package = colander.SchemaNode(colander.String())


class Users(colander.SequenceSchema):
    """A SequenceSchema to validate a list of User objects."""

    user = colander.SchemaNode(colander.String())


class Releases(colander.SequenceSchema):
    """A SequenceSchema to validate a list of Release objects."""

    release = colander.SchemaNode(colander.String())


class ReleaseIds(colander.SequenceSchema):
    """A SequenceSchema to validate a list of Release ID objects."""

    release_id = colander.SchemaNode(colander.Integer())


class Groups(colander.SequenceSchema):
    """A SequenceSchema to validate a list of Group objects."""

    group = colander.SchemaNode(colander.String())


class Updates(colander.SequenceSchema):
    """A SequenceSchema to validate a list of Update objects."""

    update = colander.SchemaNode(colander.String())


class Tests(colander.SequenceSchema):
    """A SequenceSchema to validate a list of Test objects."""

    test = colander.SchemaNode(colander.String())


class BugFeedback(colander.MappingSchema):
    """A schema for BugFeedback to be provided via API parameters."""

    bug_id = colander.SchemaNode(colander.Integer())
    karma = colander.SchemaNode(
        colander.Integer(),
        validator=colander.Range(min=-1, max=1),
        missing=0,
    )


class BugFeedbacks(colander.SequenceSchema):
    """A SequenceSchema to validate a list of BugFeedback objects."""

    bug_feedback = BugFeedback()


class TestcaseFeedback(colander.MappingSchema):
    """A schema for TestcaseFeedback to be provided via API parameters."""

    testcase_name = colander.SchemaNode(colander.String())
    karma = colander.SchemaNode(
        colander.Integer(),
        validator=colander.Range(min=-1, max=1),
        missing=0,
    )


class TestcaseFeedbacks(colander.SequenceSchema):
    """A SequenceSchema to validate a list of TestcaseFeedback objects."""

    testcase_feedback = TestcaseFeedback()


class SaveCommentSchema(CSRFProtectedSchema, colander.MappingSchema):
    """An API schema for bodhi.server.services.comments.new_comment()."""

    def deserialize(self, cstruct):
        """Unflatten comment before parsing into Schema."""
        appstruct = SaveCommentSchema().unflatten(cstruct)
        return super(SaveCommentSchema, self).deserialize(appstruct)

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
    """An API schema for bodhi.server.services.updates.new_update()."""

    builds = Builds(colander.Sequence(accept_scalar=True),
                    preparer=[util.splitter])

    bugs = Bugs(colander.Sequence(accept_scalar=True), missing=None, preparer=[util.splitter])

    close_bugs = colander.SchemaNode(
        colander.Boolean(),
        missing=True,
    )
    type = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf(list(UpdateType.values())),
    )
    request = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf(list(UpdateRequest.values())),
        missing='testing',
    )
    severity = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf(list(UpdateSeverity.values())),
        missing='unspecified',
    )
    notes = colander.SchemaNode(
        colander.String(),
        validator=colander.Length(min=2),
        missing_msg='A description is required for the update.'
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
        validator=colander.OneOf(list(UpdateSuggestion.values())),
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
    """A mixin class used by schemas to validate the ``display_user`` API parameter."""

    display_user = colander.SchemaNode(
        colander.Boolean(true_choices=('true', '1')),
        location="querystring",
        missing=True,
    )


class PaginatedSchema(colander.MappingSchema):
    """A mixin class used by schemas to provide pagination support for API endpoints."""

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
    """A mixin class used by schemas to provide search support for API endpoints."""

    like = colander.SchemaNode(
        colander.String(),
        location="querystring",
        missing=None,
        preparer=[lambda x: x.strip() if x else x],
    )

    search = colander.SchemaNode(
        colander.String(),
        location="querystring",
        missing=None,
        preparer=[lambda x: x.strip() if x else x],
    )


class ListReleaseSchema(PaginatedSchema):
    """
    An API schema for listing releases.

    This schema is used by bodhi.server.services.releases.query_releases_html() and
    bodhi.server.services.releases.query_releases_json().
    """

    ids = ReleaseIds(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )

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

    state = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf(list(ReleaseState.values())),
        missing=None,
    )

    exclude_archived = colander.SchemaNode(
        colander.Boolean(true_choices=('true', '1')),
        location="querystring",
        missing=None,
    )


class SaveReleaseSchema(CSRFProtectedSchema, colander.MappingSchema):
    """An API schema for bodhi.server.services.releases.save_release()."""

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
        validator=colander.OneOf(list(ReleaseState.values())),
        missing="disabled",
    )
    edited = colander.SchemaNode(
        colander.String(),
        missing=None,
    )
    mail_template = colander.SchemaNode(
        colander.String(),
        missing="fedora_errata_template",
        validator=colander.OneOf(MAIL_TEMPLATES)
    )


class ListStackSchema(PaginatedSchema, SearchableSchema):
    """An API schema for bodhi.server.services.stacks.query_stacks()."""

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
    """An API schema for bodhi.server.services.stacks.save_stack()."""

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
    """An API schema for bodhi.server.services.user.query_users()."""

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
    """An API schema for bodhi.server.services.updates.query_updates()."""

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

    active_releases = Releases(
        colander.Boolean(true_choices=('true', '1')),
        location="querystring",
        missing=False,
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
        validator=colander.OneOf(list(UpdateRequest.values())),
    )

    severity = colander.SchemaNode(
        colander.String(),
        location="querystring",
        missing=None,
        validator=colander.OneOf(list(UpdateSeverity.values())),
    )

    status = colander.SchemaNode(
        colander.String(),
        location="querystring",
        missing=None,
        validator=colander.OneOf(list(UpdateStatus.values())),
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
        validator=colander.OneOf(list(UpdateSuggestion.values())),
    )

    type = colander.SchemaNode(
        colander.String(),
        location="querystring",
        missing=None,
        validator=colander.OneOf(list(UpdateType.values())),
    )

    content_type = colander.SchemaNode(
        colander.String(),
        location="querystring",
        missing=None,
        validator=colander.OneOf(list(ContentType.values())),
    )

    user = Users(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )

    updateid = Builds(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )


class ListPackageSchema(PaginatedSchema, SearchableSchema):
    """An API schema for bodhi.server.services.packages.query_packages()."""

    name = colander.SchemaNode(
        colander.String(),
        location="querystring",
        missing=None,
    )


class ListBuildSchema(PaginatedSchema):
    """An API schema for bodhi.server.services.builds.query_builds()."""

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
    """An API schema for bodhi.server.services.updates.set_request()."""

    request = colander.SchemaNode(
        colander.String(),
        validator=colander.OneOf(list(UpdateRequest.values())),
    )


class ListCommentSchema(PaginatedSchema, SearchableSchema):
    """An API schema for bodhi.server.services.comments.query_comments()."""

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

    user = Users(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )

    update_owner = Users(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )

    ignore_user = Users(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
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
    """An API schema for bodhi.server.services.overrides.query_overrides()."""

    builds = Builds(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )

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

    user = Users(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[util.splitter],
    )


class SaveOverrideSchema(CSRFProtectedSchema, colander.MappingSchema):
    """An API schema for bodhi.server.services.overrides.save_override()."""

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


class WaiveTestResultsSchema(CSRFProtectedSchema, colander.MappingSchema):
    """An API schema for bodhi.server.services.updates.waive_test_results()."""

    comment = colander.SchemaNode(
        colander.String(),
        missing=None,
    )
    tests = Tests(colander.Sequence(accept_scalar=True), missing=None, preparer=[util.splitter])


class GetTestResultsSchema(CSRFProtectedSchema, colander.MappingSchema):
    """An API schema for bodhi.server.services.updates.get_test_results()."""

    alias = Builds(
        colander.Sequence(accept_scalar=True),
        missing=None,
    )
