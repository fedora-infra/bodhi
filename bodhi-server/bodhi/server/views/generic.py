# Copyright © 2014-2019 Red Hat, Inc. and others
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
"""A collection of views that don't fit in any other common category."""

import datetime

from prometheus_client import CONTENT_TYPE_LATEST, generate_latest, REGISTRY
from pyramid.exceptions import HTTPBadRequest, HTTPForbidden
from pyramid.httpexceptions import HTTPMovedPermanently, HTTPUnauthorized
from pyramid.response import Response
from pyramid.settings import asbool
from pyramid.view import notfound_view_config, view_config
import cornice.errors
import sqlalchemy as sa

from bodhi.server import log, METADATA, models
from bodhi.server.config import config
import bodhi.server.util


def get_top_testers():
    """
    Return a query of the 5 users that have submitted the most comments in the last 7 days.

    Returns:
        sqlalchemy.orm.query.Query: A SQLAlchemy query that contains the
                                  5 users that have submitted the most comments
                                  in the last 7 days, and their total number of
                                  comments in bodhi.
    """
    blacklist = config.get('stats_blacklist')
    days = config.get('top_testers_timeframe')
    start_time = datetime.datetime.utcnow() - datetime.timedelta(days=days)

    query = models.Session().query(
        models.User,
        sa.func.count(models.User.comments).label('count_1')
    ).join(models.Comment)
    query = query\
        .order_by(sa.text('count_1 desc'))\
        .filter(models.Comment.timestamp > start_time)

    for user in blacklist:
        query = query.filter(models.User.name != str(user))

    return query\
        .group_by(models.User)\
        .limit(5)\
        .all()


def get_top_packagers():
    """
    Return a query of the 5 users that have submitted the most updates in the last 7 days.

    Returns:
        sqlalchemy.orm.query.Query: A SQLAlchemy query that contains the
                                  5 users that have submitted the most updates
                                  in the last 7 days, and their total number of
                                  updates in bodhi.
    """
    blacklist = config.get('stats_blacklist')
    days = config.get('top_testers_timeframe')
    start_time = datetime.datetime.utcnow() - datetime.timedelta(days=days)

    query = models.Session().query(
        models.User,
        sa.func.count(models.User.updates).label('count_1')
    ).join(models.Update)
    query = query\
        .order_by(sa.text('count_1 desc'))\
        .filter(models.Update.date_submitted > start_time)

    for user in blacklist:
        query = query.filter(models.User.name != str(user))

    return query\
        .group_by(models.User)\
        .limit(5)\
        .all()


def get_testing_counts(critpath, security):
    """
    Return a count of updates in Testing status.

    critpath and security are optional filters for security or critical path updates.

    Args:
        critpath (boolean): If True, filter results to only return updates in the Critical Path
        security (boolean): If True, filter results to only return Security updates
    Returns:
        int: the number of updates in the testing status
    """
    query = models.Update.query

    if critpath:
        query = query.filter(
            models.Update.critpath == True)
    if security:
        query = query.filter(
            models.Update.type == models.UpdateType.security)

    query = query.filter(
        models.Update.status == models.UpdateStatus.testing)

    query = query.order_by(models.Update.date_submitted.desc())
    return query.count()


def _generate_home_page_stats():
    """
    Generate and return a dictionary of stats for the home() function to use.

    This function returns a dictionary with the following 5 keys:

        top_testers:            a list of 5 tuples, the 5 top testers in the last 7 days.
                                The first item of each tuple contains a dict of the items
                                in the User model for that user. The second item of the tuple
                                contains the number of comments the user has left in Bodhi.
        top_packagers:           a list of 5 tuples, the 5 top packagers in the last 7 days.
                                The first item of each tuple contains a dict of the items
                                in the User model for that user. The second item of the tuple
                                contains the number of updates the user has filed in Bodhi.
        critpath_testing_count: the number of critical path updates in testin.
        security_testing_count: the number of security updates in testing
        all_testing_count:      the number of all updates in testing

    Returns:
        dict: A Dictionary expressing the values described above
    """
    top_testers = get_top_testers()
    top_packagers = get_top_packagers()

    return {
        "top_testers": [(obj.__json__(), n) for obj, n in top_testers],
        "top_packagers": [(obj.__json__(), n) for obj, n in top_packagers],
        "critpath_testing_count": get_testing_counts(True, False),
        "security_testing_count": get_testing_counts(False, True),
        "all_testing_count": get_testing_counts(False, False),
    }


def _get_sidetags(koji, user=None, contains_builds=False):
    """
    Return a list of koji sidetags.

    Args:
        koji: the koji client instance from request.koji
        user: a string of the user's FAS name
        contains_builds: a boolean. if true, only return sidetags with builds
    Returns:
        dict: A list of the sidetags information.
    """
    sidetags = koji.listSideTags(user=user)

    koji.multicall = True
    for tag in sidetags:
        koji.getTag(tag['name'])
    sidetags_info = koji.multiCall()

    koji.multicall = True
    for tag in sidetags_info:
        koji.listTagged(tag[0]['name'], latest=True)
    builds = koji.multiCall()

    result = []
    for i, tag in enumerate(sidetags_info):
        if (contains_builds and builds[i][0]) or not contains_builds:
            result.append({
                'id': tag[0]['id'],
                'name': tag[0]['name'],
                'sidetag_user': tag[0]['extra']['sidetag_user'],
                'builds': builds[i][0]
            })

    return result


def _get_active_updates(request):
    query = models.Update.query

    update_status = [models.UpdateStatus.pending, models.UpdateStatus.testing]
    query = query.filter(sa.sql.or_(*[models.Update.status == s for s in update_status]))

    user = models.User.get(request.user.name)

    query = query.filter(models.Update.user == user)

    query = query.order_by(models.Update.date_submitted.desc())

    return query.all()


def _get_active_overrides(request):
    query = models.BuildrootOverride.query

    query = query.filter(models.BuildrootOverride.expired_date.is_(None))
    user = models.User.get(request.user.name)

    query = query.filter(models.BuildrootOverride.submitter == user)

    query = query.order_by(models.BuildrootOverride.submission_date.desc())

    return query.all()


@view_config(route_name='prometheus_metric')
def get_metrics(request):
    """
    Provide the metrics to be consumed by prometheus.

    See the metrics_tween.py for hook to collect metrics for page requests

    Args:
        request (pyramid.request): The current web request.
    Returns:
        str: text in the prometheus metrics format.
    """
    registry = REGISTRY

    request.response.content_type = CONTENT_TYPE_LATEST
    resp = Response(
        content_type=CONTENT_TYPE_LATEST,
    )
    resp.body = generate_latest(registry)
    return resp


@view_config(route_name='home', renderer='home.html')
def home(request):
    """
    Provide the data required to present the Bodhi frontpage.

    See the docblock on _generate_home_page_stats() for details on the return value.

    Args:
        request (pyramid.request): The current web request.
    Returns:
        dict: A Dictionary expressing the values described in the docblock for
            _generate_home_page_stats().
    """
    data = _generate_home_page_stats()
    if request.user:
        data['active_updates'] = _get_active_updates(request)
        data['active_overrides'] = _get_active_overrides(request)
    return data


@view_config(route_name='new_update', renderer='new_update.html')
def new_update(request):
    """
    Return the new update form.

    Args:
        request (pyramid.request.Request): The current request.
    Returns:
        dict: A dictionary with four keys. "update" indexes None. "types" indexes a list of the
            possible UpdateTypes. "severities" indexes a list of the possible severity values.
            "suggestions" indexes a list of the possible values for update suggestions.
    Raises:
        pyramid.exceptions.HTTPForbidden: If the user is not logged in.
    """
    user = request.authenticated_userid
    if not user:
        raise HTTPForbidden("You must be logged in.")
    suggestions = list(models.UpdateSuggestion.values())
    return dict(
        update=None,
        types=reversed(list(models.UpdateType.values())),
        severities=sorted(list(models.UpdateSeverity.values()),
                          key=bodhi.server.util.sort_severity),
        suggestions=suggestions,
        sidetags=_get_sidetags(request.koji, user=user, contains_builds=True)
    )


@view_config(route_name='latest_candidates', renderer='json')
def latest_candidates(request):
    """
    Return the most recent candidate builds for a given package name.

    For a given `package`, this method returns the most recent builds tagged
    into the Release.candidate_tag for all Releases. The package name is specified in the request
    "package" parameter.

    Args:
        request (pyramid.request.Request): The current request. The package name is specified in the
            request's "package" parameter.
    Returns:
        list: A list of dictionaries of the found builds. Each dictionary has 5 keys: "nvr" maps
            to the build's nvr field, "id" maps to the build's id, "tag_name" is the tag of the
            build, owner_name is the person who built the package in koji, and 'release_name' is
            the bodhi release name of the package.
    """
    koji = request.koji
    db = request.db

    def work(testing, hide_existing, pkg=None, prefix=None):
        result = []
        koji.multicall = True

        releases = db.query(models.Release) \
                     .filter(
                         models.Release.state.in_(
                             (models.ReleaseState.pending,
                              models.ReleaseState.frozen,
                              models.ReleaseState.current)))

        if hide_existing:
            # We want to filter out builds associated with an update.
            # Since the candidate_tag is removed when an update is pushed to
            # stable, we only need a list of builds that are associated to
            # updates still in pending state.

            # Don't filter by releases here, because the associated update
            # might be archived but the build might be inherited into an active
            # release. If this gives performance troubles later on, caching
            # this set should be easy enough.
            associated_build_nvrs = set(
                row[0] for row in
                db.query(models.Build.nvr).
                join(models.Update).
                filter(models.Update.status == models.UpdateStatus.pending)
            )

        kwargs = dict(package=pkg, prefix=prefix, latest=True)
        tag_release = dict()
        for release in releases:
            tag_release[release.candidate_tag] = release.long_name
            tag_release[release.testing_tag] = release.long_name
            tag_release[release.pending_testing_tag] = release.long_name
            tag_release[release.pending_signing_tag] = release.long_name
            koji.listTagged(release.candidate_tag, **kwargs)
            if testing:
                koji.listTagged(release.testing_tag, **kwargs)
                koji.listTagged(release.pending_testing_tag, **kwargs)
                if release.pending_signing_tag:
                    koji.listTagged(release.pending_signing_tag, **kwargs)

        response = koji.multiCall() or []  # Protect against None
        for taglist in response:
            # if the call to koji results in errors, it returns them
            # in the reponse as dicts. Here we detect these, and log
            # the errors
            if isinstance(taglist, dict):
                log.error('latest_candidates endpoint asked Koji about a non-existent tag:')
                log.error(taglist)
            else:
                for build in taglist[0]:
                    if hide_existing and build['nvr'] in associated_build_nvrs:
                        continue

                    item = {
                        'nvr': build['nvr'],
                        'id': build['id'],
                        'package_name': build['package_name'],
                        'owner_name': build['owner_name'],
                    }

                    # The build's tag might not be present in tag_release
                    # because its associated release is archived and therefore
                    # filtered out in the query above.
                    if build['tag_name'] in tag_release:
                        item['release_name'] = tag_release[build['tag_name']]

                    # Prune duplicates
                    # https://github.com/fedora-infra/bodhi/issues/450
                    if item not in result:
                        result.append(item)
        return result

    pkg = request.params.get('package')
    prefix = request.params.get('prefix')
    testing = asbool(request.params.get('testing'))
    hide_existing = asbool(request.params.get('hide_existing'))
    log.debug('latest_candidate(%r, %r, %r)' % (pkg, testing, hide_existing))

    if pkg:
        result = work(testing, hide_existing, pkg=pkg)
    else:
        result = work(testing, hide_existing, prefix=prefix)
    return result


@view_config(route_name='latest_builds', renderer='json')
def latest_builds(request):
    """
    Return a list of the latest builds for a given package.

    Args:
        request (pyramid.request.Request): The current request. The request's "package" parameter is
            used to pass the package name being queried.
    Returns:
        dict: A dictionary of the release dist tag to the latest build.
    """
    builds = {}
    koji = request.koji
    package = request.params.get('package')
    for tag_type, tags in models.Release.get_tags(request.db)[0].items():
        for tag in tags:
            try:
                for build in koji.getLatestBuilds(tag, package=package):
                    builds[tag] = build['nvr']
            except Exception:  # Things like EPEL don't have pending tags
                pass
    return builds


@view_config(route_name='get_sidetags', renderer='json')
def get_sidetags(request):
    """
    Return a list of koji sidetags based on query arguments.

    Args:
        request (pyramid.request.Request): The current request. The request's "user" parameter is
            used to pass the username being queried.
    Returns:
        dict: A list of the sidetags information.
    """
    koji = request.koji
    # 'user': a FAS username, used to only return sidetags from that user
    user = request.params.get('user')
    # 'contains_builds': a boolean to only return sidetags with that contain builds
    contains_builds = asbool(request.params.get('contains_builds'))

    return _get_sidetags(koji, user=user, contains_builds=contains_builds)


@view_config(route_name='latest_builds_in_tag', renderer='json')
def latest_builds_in_tag(request):
    """
    Return a list of the latest builds for a given tag.

    Args:
        request (pyramid.request.Request): The current request. The request's "tag" parameter is
            used to pass the koji tagname being queried.
    Returns:
        dict: A dictionary of the release dist tag to the latest build.
    """
    koji = request.koji
    tag = request.params.get('tag')
    if not tag:
        raise HTTPBadRequest("tag parameter is required")
    else:
        return koji.listTagged(tag, latest=True)


@view_config(route_name='new_override', renderer='override.html')
def new_override(request):
    """
    Return the new buildroot override form.

    Args:
        request (pyramid.request.Request): The current request.
    Returns:
        dict: A dictionary of the form {nvr: nvr}, where the request nvr field indexes itself.
    Raises:
        pyramid.exceptions.HTTPForbidden: If the user is not logged in.
    """
    nvr = request.params.get('nvr')
    user = request.authenticated_userid
    if not user:
        raise HTTPForbidden("You must be logged in.")
    return dict(nvr=nvr)


@view_config(route_name='api_version', renderer='json')
def api_version(request):
    """
    Return the Bodhi API version.

    Args:
        request (pyramid.request.Request): The current request.
    Returns:
        dict: A dictionary with a "version" key indexing a string of the Bodhi version.
    """
    return dict(version=bodhi.server.util.version())


@view_config(route_name='liveness', renderer='json')
def liveness(request):
    """
    Return 'ok' as a sign of being alive.

    Args:
        request (pyramid.request.Request): The current request.
    Returns:
        str: 'ok'
    """
    return 'ok'


@view_config(route_name='readyness', renderer='json')
def readyness(request):
    """
    Return 200 if the app can query the db, to signify being ready.

    Args:
        request (pyramid.request.Request): The current request.
    Returns:
        dict: A dictionary with list of services checked.
    """
    try:
        request.db.execute("SELECT 1")
        return dict(db_session=True)
    except Exception:
        raise Exception("App not ready, is unable to execute a trivial select.")


@notfound_view_config(append_slash=True)
def notfound_view(context, request):
    """
    Automatically redirects to slash-appended routes.

    Note: The URL below spans two lines.
    http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/urldispatch.html

    Args:
        context (pyramid.httpexceptions.HTTPNotFound): The 404 not found error.
        request (pyramid.request.Request): The current request.
    Returns:
        bodhi.server.services.errors.html_handler: A pyramid.httpexceptions.HTTPError to be rendered
            to the user for the 404.
    """
    return exception_html_view(context, request)


@view_config(context=HTTPForbidden, accept='text/html')
@view_config(context=HTTPUnauthorized, accept='text/html')
@view_config(context=Exception, accept='text/html')
def exception_html_view(exc, request):
    """
    Return a html error response upon generic errors (404s, 403s, 500s, etc..).

    This is here to catch everything that isn't caught by our cornice error
    handlers.  When we do catch something, we transform it into a cornice
    Errors object and pass it to our nice cornice error handler.  That way, all
    the exception presentation and rendering we can keep in one place.

    Args:
        exc (Exception): The unhandled exception.
        request (pyramid.request.Request): The current request.
    Returns:
        bodhi.server.services.errors.html_handler: A pyramid.httpexceptions.HTTPError to be rendered
            to the user for the given exception.
    """
    errors = getattr(request, 'errors', [])
    status = getattr(exc, 'status_code', 500)

    if status not in (404, 403, 401):
        log.exception("Error caught.  Handling HTML response.")
    else:
        log.warning(str(exc))

    if not len(errors):
        errors = cornice.errors.Errors(status=status)
        errors.add('body', description=str(exc))
        request.errors = errors

    return bodhi.server.services.errors.html_handler(request)


@view_config(context=HTTPForbidden, accept='application/json')
@view_config(context=Exception, accept='application/json')
def exception_json_view(exc, request):
    """
    Return a json error response upon generic errors (404s, 403s, 500s, etc..).

    This is here to catch everything that isn't caught by our cornice error
    handlers.  When we do catch something, we transform it into a cornice
    Errors object and pass it to our nice cornice error handler.  That way, all
    the exception presentation and rendering we can keep in one place.

    Args:
        exc (Exception): The unhandled exception.
        request (pyramid.request.Request): The current request.
    Returns:
        bodhi.server.services.errors.json_handler: A pyramid.httpexceptions.HTTPError to be rendered
            to the user for the given exception.
    """
    errors = getattr(request, 'errors', [])
    status = getattr(exc, 'status_code', 500)

    if status not in (404, 403):
        log.exception("Error caught.  Handling JSON response.")
    else:
        log.warning(str(exc))

    if not len(errors):
        errors = cornice.errors.Errors(status=status)
        errors.add('body', description=str(exc), name=exc.__class__.__name__)
        request.errors = errors

    return bodhi.server.services.errors.json_handler(request)


@view_config(route_name='docs')
def docs(request):
    """Legacy: Redirect the previously self-hosted documentation."""
    major_minor_version = ".".join(METADATA["version"].split(".")[:2])
    subpath = "/".join(request.subpath)
    url = f"https://fedora-infra.github.io/bodhi/{major_minor_version}/{subpath}"
    raise HTTPMovedPermanently(url)
