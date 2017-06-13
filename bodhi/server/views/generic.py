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

import cornice.errors

from pyramid.settings import asbool
from pyramid.view import view_config, notfound_view_config
from pyramid.exceptions import HTTPForbidden, HTTPBadRequest
from pyramid.httpexceptions import HTTPFound

from bodhi.server import log, models
from bodhi.server.config import config
import bodhi.server.util


def get_top_testers(request):
    """
    Return a query of the 5 users that have submitted the most comments on updates
    in the last 7 days.

    Args:
        request (pyramid.request): The current web request.
    Returns:
        sqlalchemy.orm.query.Query: A SQLAlchemy query that contains the
                                  5 users that have submitted the most comments
                                  in the last 7 days, and their total number of
                                  comments in bodhi.
    """
    db = request.db
    blacklist = config.get('stats_blacklist')
    days = config.get('top_testers_timeframe')
    start_time = datetime.datetime.utcnow() - datetime.timedelta(days=days)

    query = db.query(
        models.User,
        sa.func.count(models.User.comments).label(u'count_1')
    ).join(models.Comment)
    query = query\
        .order_by(sa.text(u'count_1 desc'))\
        .filter(models.Comment.timestamp > start_time)

    for user in blacklist:
        query = query.filter(models.User.name != unicode(user))

    return query\
        .group_by(models.User)\
        .limit(5)\
        .all()


def get_latest_updates(request, critpath, security):
    """
    Return a query of the 5 most recent updates that are in Testing status, with
    optional filters to filter by if an Update is a security or critical path update.

    Args:
        request (pyramid.request): The current web request.
        critpath (boolean): If True, filter results to only return updates in the Critical Path
        security (boolean): If True, filter results to only return Security updates
    Returns:
        sqlalchemy.orm.query.Query: A SQLAlchemy query that contains the
                                  5 most recent updates that are in Testing status
    """
    db = request.db
    query = db.query(models.Update)

    if critpath:
        query = query.filter(
            models.Update.critpath == True)
    if security:
        query = query.filter(
            models.Update.type == models.UpdateType.security)

    query = query.filter(
        models.Update.status == models.UpdateStatus.testing)

    query = query.order_by(models.Update.date_submitted.desc())
    return query.limit(5).all()


def _get_status_counts(basequery, status):
    """
    Return a dictionary with the counts of objects found in the basequery,
    specified by total count, newpackage count, bugfix count, enhancement count,
    and security count. The dictionary keys will be named with the
    template {status}_{type}_total. For example, if status is
    models.UpdateStatus.stable, a dictionary with the following keys would be
    returned:
        stable_updates_total
        stable_newpackage_total
        stable_bugfix_total
        stable_enhancement_total
        stable_security_total

    Args:
        basequery (sqlalchemy.orm.query.Query):
            The basequery of updates we want to count and further filter on.
        status (bodhi.server.models.UpdateStatus):
            The update status we want to filter by in basequery
    Return:
        dict: A dictionary describing the counts of the updates, as described above.
    """
    basequery = basequery.filter(models.Update.status == status)
    return {
        '{}_updates_total'.format(status.description): basequery.count(),
        '{}_newpackage_total'.format(status.description):
            basequery.filter(models.Update.type == models.UpdateType.newpackage).count(),
        '{}_bugfix_total'.format(status.description):
            basequery.filter(models.Update.type == models.UpdateType.bugfix).count(),
        '{}_enhancement_total'.format(status.description):
            basequery.filter(models.Update.type == models.UpdateType.enhancement).count(),
        '{}_security_total'.format(status.description):
            basequery.filter(models.Update.type == models.UpdateType.security).count(),
    }


def get_update_counts(request, releaseid):
    """
    Returns counts for the various states and types of updates in the given release.

    This function returns a dictionary that tabulates the counts of the various
    types of Bodhi updates at the various states they can appear in. The
    dictionary has the following keys, with pretty self-explanatory names:

        pending_updates_total
        pending_newpackage_total
        pending_bugfix_total
        pending_enhancement_total
        pending_security_total
        testing_updates_total
        testing_newpackage_total
        testing_bugfix_total
        testing_enhancement_total
        testing_security_total
        stable_updates_total
        stable_newpackage_total
        stable_bugfix_total
        stable_enhancement_total
        stable_security_total

    Args:
        request (pyramid.util.Request): The current request
        releaseid (basestring): The id of the Release object you would like the counts performed on
    Returns:
        dict: A dictionary expressing the counts, as described above.
    """

    release = models.Release.get(releaseid, request.db)
    basequery = request.db.query(models.Update).filter(models.Update.release == release)
    counts = {}
    counts.update(_get_status_counts(basequery, models.UpdateStatus.pending))
    counts.update(_get_status_counts(basequery, models.UpdateStatus.testing))
    counts.update(_get_status_counts(basequery, models.UpdateStatus.stable))

    return counts


@view_config(route_name='home', renderer='home.html')
def home(request):
    """
    Provide the data required to present the Bodhi frontpage. This function returns a dictionary
    with the following 4 keys:

        release_updates_counts: a dict of counts of various states and types of updates as
                                generated by get_update_counts()
        top_testers:            a list of 5 tuples, the 5 top testers in the last 7 days.
                                The first item of each tuple contains a dict of the items
                                in the User model for that user. The second item of the tuple
                                contains the number of comments the user has left in Bodhi.
        critpath_updates:       a list of 5 dicts, the 5 most recent critical path updates.
                                Each dict contains key-value pairs for all the items in the
                                Update model.
        security_updates:       a list of 5 dicts, the 5 most recent security updates.
                                Each dict contains key-value pairs for all the items in the
                                Update model.

    Args:
        request (pyramid.request): The current web request.

    Returns:
        dict: A Dictionary expressing the values described above

    """
    r = request

    @request.cache.cache_on_arguments()
    def work():
        top_testers = get_top_testers(request)
        critpath_updates = get_latest_updates(request, True, False)
        security_updates = get_latest_updates(request, False, True)
        release_updates_counts = {}
        for release in request.releases['current']:
            release_updates_counts[release["name"]] = get_update_counts(request, release["name"])

        return {
            "release_updates_counts": release_updates_counts,
            "top_testers": [(obj.__json__(r), n) for obj, n in top_testers],
            "critpath_updates": [obj.__json__(r) for obj in critpath_updates],
            "security_updates": [obj.__json__(r) for obj in security_updates],
        }

    return work()


@view_config(route_name='new_update', renderer='new_update.html')
def new_update(request):
    """ Returns the new update form """
    user = request.authenticated_userid
    if not user:
        raise HTTPForbidden("You must be logged in.")
    return dict(
        update=None,
        types=reversed(models.UpdateType.values()),
        severities=sorted(models.UpdateSeverity.values(), key=bodhi.server.util.sort_severity),
        suggestions=reversed(models.UpdateSuggestion.values()),
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
    def work(pkg, testing):
        result = []
        koji.multicall = True

        releases = db.query(models.Release) \
                     .filter(
                         models.Release.state.in_(
                             (models.ReleaseState.pending,
                              models.ReleaseState.current)))

        kwargs = dict(package=pkg, latest=True)
        for release in releases:
            koji.listTagged(release.candidate_tag, **kwargs)
            if testing:
                koji.listTagged(release.testing_tag, **kwargs)
                koji.listTagged(release.pending_testing_tag, **kwargs)
                koji.listTagged(release.pending_signing_tag, **kwargs)

        response = koji.multiCall() or []  # Protect against None

        for taglist in response:
            if isinstance(taglist, dict):
                continue
            for build in taglist[0]:
                item = {
                    'nvr': build['nvr'],
                    'id': build['id'],
                }
                # Prune duplicates
                # https://github.com/fedora-infra/bodhi/issues/450
                if item not in result:
                    result.append(item)
        return result

    pkg = request.params.get('package')
    testing = asbool(request.params.get('testing'))
    log.debug('latest_candidate(%r, %r)' % (pkg, testing))

    if not pkg:
        return []

    result = work(pkg, testing)

    log.debug(result)
    return result


@view_config(route_name='latest_builds', renderer='json')
def latest_builds(request):
    """ Get a list of the latest builds for a given package.

    Returns a dictionary of the release dist tag to the latest build.
    """
    builds = {}
    koji = request.koji
    package = request.params.get('package')
    for tag_type, tags in models.Release.get_tags(request.db)[0].iteritems():
        for tag in tags:
            try:
                for build in koji.getLatestBuilds(tag, package=package):
                    builds[tag] = build['nvr']
            except:  # Things like EPEL don't have pending tags
                pass
    return builds


@view_config(route_name='masher_status', renderer='masher.html')
def masher_status(request):
    return dict()


@view_config(route_name='new_override', renderer='override.html')
def new_override(request):
    """ Returns the new buildroot override form """
    nvr = request.params.get('nvr')
    user = request.authenticated_userid
    if not user:
        raise HTTPForbidden("You must be logged in.")
    return dict(nvr=nvr)


@view_config(route_name='popup_toggle', request_method='POST')
def popup_toggle(request):
    # Get the user
    userid = request.authenticated_userid
    if userid is None:
        raise HTTPForbidden("You must be logged in.")
    user = request.db.query(models.User).filter_by(name=unicode(userid)).first()
    if user is None:
        raise HTTPBadRequest("For some reason, user does not exist.")

    # Toggle the value.
    user.show_popups = not user.show_popups

    # And send the user back
    return_to = request.params.get('next', request.route_url('home'))
    return HTTPFound(location=return_to)


@view_config(route_name='api_version', renderer='json')
def api_version(request):
    """ Returns the Bodhi API version """
    return dict(version=bodhi.server.util.version())


@notfound_view_config(append_slash=True)
def notfound_view(context, request):
    """ Automatically redirects to slash-appended routes.

    Note: The URL below spans two lines.
    http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/urldispatch.html
    """
    return exception_view(context, request)


@view_config(context=HTTPForbidden)
@view_config(context=Exception)
def exception_view(exc, request):
    """ A generic error page handler (404s, 403s, 500s, etc..)

    This is here to catch everything that isn't caught by our cornice error
    handlers.  When we do catch something, we transform it intpu a cornice
    Errors object and pass it to our nice cornice error handler.  That way, all
    the exception presentation and rendering we can keep in one place.
    """

    errors = getattr(request, 'errors', [])
    status = getattr(exc, 'status_code', 500)

    if status not in (404, 403):
        log.exception("Error caught.  Handling HTML response.")
    else:
        log.warn(str(exc))

    if not len(errors):
        description = getattr(exc, 'explanation', None) or str(exc)

        errors = cornice.errors.Errors(request, status=status)
        errors.add('unknown', description=description)

    return bodhi.server.services.errors.html_handler(errors)
