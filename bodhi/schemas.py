import colander

from kitchen.iterutils import iterate

from bodhi.models import UpdateType, UpdateSeverity, UpdateSuggestion, UpdateRequest


def splitter(value):
    """Parse a string or list of comma or space delimited builds"""
    items = []
    for v in iterate(value):
        for item in v.replace(',', ' ').split():
            items.append(item)
    return items


class Builds(colander.SequenceSchema):
    build = colander.SchemaNode(colander.String())


class SaveUpdateSchema(colander.MappingSchema):
    builds = Builds(colander.Sequence(accept_scalar=True),
                    preparer=[splitter])

    bugs = colander.SchemaNode(
        colander.String(),
        missing='',
    )
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
