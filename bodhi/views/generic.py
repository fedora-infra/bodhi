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

import datetime
import sqlalchemy as sa

from pyramid.security import authenticated_userid
from pyramid.view import view_config, notfound_view_config
from pyramid.exceptions import HTTPNotFound, HTTPForbidden

from bodhi import log
import bodhi.models
from bodhi.util import markup


@notfound_view_config(append_slash=True)
def notfound_view(context, request):
    """ Automatically redirects to slash-appended routes.

    http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/urldispatch.html#redirecting-to-slash-appended-rou
    """
    return HTTPNotFound()


def get_top_testers(request):
    db = request.db
    blacklist = request.registry.settings.get('stats_blacklist').split()
    days = int(request.registry.settings.get('top_testers_timeframe', 7))
    start_time = datetime.datetime.utcnow() - datetime.timedelta(days=days)

    query = db.query(
        bodhi.models.User,
        sa.func.count(bodhi.models.User.comments).label('count_1')
    ).join(bodhi.models.Comment)
    query = query\
        .order_by('count_1 desc')\
        .filter(bodhi.models.Comment.timestamp > start_time)

    for user in blacklist:
        query = query.filter(bodhi.models.User.name != user)

    return query\
        .group_by(bodhi.models.User)\
        .limit(5)\
        .all()


def get_latest_updates(request, critpath, security):
    db = request.db
    query = db.query(bodhi.models.Update)

    if critpath:
        query = query.filter(
            bodhi.models.Update.critpath==True)
    if security:
        query = query.filter(
            bodhi.models.Update.type==bodhi.models.UpdateType.security)

    query = query.filter(
        bodhi.models.Update.status==bodhi.models.UpdateStatus.testing)

    query = query.order_by(bodhi.models.Update.date_submitted.desc())
    return query.limit(5).all()


@view_config(route_name='home', renderer='home.html')
def home(request):
    """ Returns data for the frontpage """
    r = request

    @request.cache.cache_on_arguments()
    def work():
        top_testers = get_top_testers(request)
        critpath_updates = get_latest_updates(request, True, False)
        security_updates = get_latest_updates(request, False, True)

        return {
            "top_testers": [(obj.__json__(r), n) for obj, n in top_testers],
            "critpath_updates": [obj.__json__(r) for obj in critpath_updates],
            "security_updates": [obj.__json__(r) for obj in security_updates],
        }

    return work()


@view_config(route_name='new_update', renderer='new_update.html')
def new_update(request):
    """ Returns the new update form """
    user = authenticated_userid(request)
    if not user:
        raise HTTPForbidden("You must be logged in.")
    return dict(
        types=reversed(bodhi.models.UpdateType.values()),
        severities=reversed(bodhi.models.UpdateSeverity.values()),
        suggestions=reversed(bodhi.models.UpdateSuggestion.values()),
    )


@view_config(route_name='latest_candidates', renderer='json')
def latest_candidates(request):
    """
    For a given `package`, this method returns the most recent builds tagged
    into the Release.candidate_tag for all Releases.
    """
    koji = request.koji
    db = request.db

    @request.cache.cache_on_arguments()
    def work(pkg):
        result = []
        koji.multicall = True

        releases = db.query(bodhi.models.Release) \
                     .filter(
                         bodhi.models.Release.state.in_(
                             (bodhi.models.ReleaseState.pending,
                              bodhi.models.ReleaseState.current)))

        for release in releases:
            koji.listTagged(release.candidate_tag, package=pkg, latest=True)

        builds = koji.multiCall() or []  # Protect against None

        for build in builds:
            if isinstance(build, dict):
                continue
            if build and build[0] and build[0][0]:
                result.append({
                    'nvr': build[0][0]['nvr'],
                    'id': build[0][0]['id'],
                })
        return result


    pkg = request.params.get('package')
    log.debug('latest_candidate(%r)' % pkg)

    if not pkg:
        return []

    result = work(pkg)

    log.debug(result)
    return result


@view_config(route_name='markdowner', renderer='json')
def markdowner(request):
    """ Given some text, return the markdownified html version.

    We use this for "previews" of comments and update notes.
    """
    text = request.params.get('text')
    return dict(html=markup(request.context, text))
