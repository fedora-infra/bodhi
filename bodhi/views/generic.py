import datetime
import sqlalchemy as sa

from pyramid.view import view_config, notfound_view_config
from pyramid.exceptions import HTTPNotFound

from bodhi import log, buildsys
import bodhi.models


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

    query = query.order_by(bodhi.models.Update.date_submitted.desc())
    return query.limit(5).all()


@view_config(route_name='home', renderer='home.html')
def home(request):
    """ Returns data for the frontpage """

    @request.cache.cache_on_arguments()
    def work():
        top_testers = get_top_testers(request)
        critpath_updates = get_latest_updates(request, True, False)
        security_updates = get_latest_updates(request, False, True)

        return {
            "top_testers": top_testers,
            "critpath_updates": critpath_updates,
            "security_updates": security_updates,
        }

    return work()


@view_config(route_name='latest_candidates', renderer='json')
def latest_candidates(request):
    """
    For a given `package`, this method returns the most recent builds tagged
    into the Release.candidate_tag for all Releases.
    """
    result = []
    koji = request.koji
    db = request.db
    pkg = request.params.get('package')
    log.debug('latest_candidate(%r)' % pkg)
    if pkg:
        koji.multicall = True

        for release in db.query(bodhi.models.Release).all():
            koji.listTagged(release.candidate_tag, package=pkg, latest=True)

        results = koji.multiCall()

        for build in results:
            if build and build[0] and build[0][0]:
                result.append(build[0][0]['nvr'])

    log.debug(result)
    return result
