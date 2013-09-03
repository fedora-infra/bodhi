import colander

from kitchen.iterutils import iterate

from bodhi.models import (UpdateRequest, UpdateSeverity, UpdateStatus,
                          UpdateSuggestion, UpdateType)


def splitter(value):
    """Parse a string or list of comma or space delimited builds"""
    if value == colander.null:
        return

    items = []
    for v in iterate(value):
        if isinstance(v, basestring):
            for item in v.replace(',', ' ').split():
                items.append(item)

        elif v is not None:
            items.append(v)

    return items


class Bugs(colander.SequenceSchema):
    bug = colander.SchemaNode(colander.Integer(), missing=None)


class Builds(colander.SequenceSchema):
    build = colander.SchemaNode(colander.String())


class Releases(colander.SequenceSchema):
    release = colander.SchemaNode(colander.String())


class SaveUpdateSchema(colander.MappingSchema):
    builds = Builds(colander.Sequence(accept_scalar=True),
                    preparer=[splitter])

    bugs = Bugs(colander.Sequence(accept_scalar=True),
                preparer=[splitter])

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
        validator=colander.Length(min=10),
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


class ListUpdateSchema(colander.MappingSchema):
    critpath = colander.SchemaNode(
        colander.Boolean(true_choices=('true', '1')),
        location="querystring",
        missing=None,
    )

    releases = Releases(
        colander.Sequence(accept_scalar=True),
        location="querystring",
        missing=None,
        preparer=[splitter],
    )

    request = colander.SchemaNode(
        colander.String(),
        location="querystring",
        missing=None,
        validator=colander.OneOf(UpdateRequest.values()),
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
