import json

from pyramid.view import view_config

import bodhi.models as m


@view_config(route_name='metrics', renderer='metrics.html')
def metrics(request):
    db = request.db
    data, ticks = [], []

    update_types = {
        'bugfix': 'Bug fixes',
        'enhancement': 'Enhancements',
        'security': 'Security updates',
        'newpackage': 'New packages'
    }

    releases = db.query(m.Release).filter(m.Release.name.like('F%')).all()

    for i, release in enumerate(sorted(releases, cmp=lambda x, y:
            cmp(int(x.version_int), int(y.version_int)))):
        ticks.append([i, release.name])

    for update_type, label in update_types.items():
        d = []
        type = m.UpdateType.from_string(update_type)
        for i, release in enumerate(releases):
            num = db.query(m.Update).filter_by(
                release=release,
                type=type,
                status=m.UpdateStatus.stable
            ).count()
            d.append([i, num])
        data.append(dict(data=d, label=label))

    return {'data': json.dumps(data), 'ticks': json.dumps(ticks)}
