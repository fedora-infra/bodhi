from pyramid.view import view_config, notfound_view_config
from pyramid.exceptions import HTTPNotFound

from bodhi import log, buildsys
import bodhi.models as m


@notfound_view_config(append_slash=True)
def notfound_view(context, request):
    """ Automatically redirects to slash-appended routes.

    http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/urldispatch.html#redirecting-to-slash-appended-rou
    """
    return HTTPNotFound()


@view_config(route_name='home', renderer='home.html')
def home(request):
    return {}


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

        for release in db.query(m.Release).all():
            koji.listTagged(release.candidate_tag, package=pkg, latest=True)

        results = koji.multiCall()

        for build in results:
            if build and build[0] and build[0][0]:
                result.append(build[0][0]['nvr'])

    log.debug(result)
    return result
