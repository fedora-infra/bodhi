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

import math

from cornice import Service
from pyramid.httpexceptions import HTTPBadRequest
from sqlalchemy.sql import or_

from bodhi import log
from bodhi.models import Comment, Build, Bug, CVE, Package, Update
import bodhi.captcha
import bodhi.schemas
import bodhi.security
from bodhi.validators import (
    validate_packages,
    validate_update,
    validate_updates,
    validate_update_owner,
    validate_comment_id,
    validate_username,
    validate_bug_feedback,
    validate_testcase_feedback,
    validate_captcha,
)


comment = Service(name='comment', path='/comments/{id}',
                 validators=(validate_comment_id,),
                 description='Comment submission service',
                 cors_origins=bodhi.security.cors_origins_ro)

comments = Service(name='comments', path='/comments/',
                   description='Comment submission service',
                   # Note, this 'rw' is not a typo.  the @comments service has
                   # a ``post`` section at the bottom.
                   cors_origins=bodhi.security.cors_origins_rw)


@comment.get(accept=('application/json', 'text/json'), renderer='json')
@comment.get(accept=('application/javascript'), renderer='jsonp')
@comment.get(accept=('application/atom+xml'), renderer='rss')
@comment.get(accept="text/html", renderer="comment.html")
def get_comment(request):
    """ Return a single comment from an id """
    return dict(comment=request.validated['comment'])


@comments.get(schema=bodhi.schemas.ListCommentSchema,
             accept=('application/json', 'text/json'), renderer='json',
             validators=(
                 validate_username,
                 validate_update_owner,
                 validate_updates,
                 validate_packages,
             ))
@comments.get(schema=bodhi.schemas.ListCommentSchema,
             accept=('application/javascript'), renderer='jsonp',
             validators=(
                 validate_username,
                 validate_update_owner,
                 validate_updates,
                 validate_packages,
             ))
@comments.get(schema=bodhi.schemas.ListCommentSchema,
             accept=('application/atom+xml'), renderer='rss',
             validators=(
                 validate_username,
                 validate_update_owner,
                 validate_updates,
                 validate_packages,
             ))
@comments.get(schema=bodhi.schemas.ListCommentSchema,
             accept=('text/html'), renderer='comments.html',
             validators=(
                 validate_username,
                 validate_update_owner,
                 validate_updates,
                 validate_packages,
             ))
def query_comments(request):
    db = request.db
    data = request.validated
    query = db.query(Comment)

    anonymous = data.get('anonymous')
    if anonymous is not None:
        query = query.filter_by(anonymous=anonymous)

    like = data.get('like')
    if like is not None:
        query = query.filter(or_(*[
            Comment.text.like('%%%s%%' % like)
        ]))

    packages = data.get('packages')
    if packages is not None:
        query = query\
            .join(Comment.update)\
            .join(Update.builds)\
            .join(Build.package)
        query = query.filter(or_(*[Build.package==pkg for pkg in packages]))

    since = data.get('since')
    if since is not None:
        query = query.filter(Comment.timestamp >= since)

    updates = data.get('updates')
    if updates is not None:
        query = query.filter(or_(*[Comment.update==u for u in updates]))

    update_owner = data.get('update_owner')
    if update_owner is not None:
        query = query.join(Comment.update)
        query = query.filter(Update.user==update_owner)

    user = data.get('user')
    if user is not None:
        query = query.filter(Comment.user==user)

    query = query.order_by(Comment.timestamp.desc())

    total = query.count()

    page = data.get('page')
    rows_per_page = data.get('rows_per_page')
    pages = int(math.ceil(total / float(rows_per_page)))
    query = query.offset(rows_per_page * (page - 1)).limit(rows_per_page)

    return dict(
        comments=query.all(),
        page=page,
        pages=pages,
        rows_per_page=rows_per_page,
        total=total,
        chrome=data.get('chrome'),
    )


@comments.post(schema=bodhi.schemas.SaveCommentSchema,
               #permission='create',  # We need an ACL for this to work...
               renderer='json',
               validators=(
                   validate_update,
                   validate_bug_feedback,
                   validate_testcase_feedback,
                   validate_captcha,
               ))
def new_comment(request):
    """ Add a new comment to an update. """
    settings = request.registry.settings
    data = request.validated

    # This has already been validated at this point, but we need to ditch
    # it since the models don't care about a csrf argument.
    data.pop('csrf_token')

    update = data.pop('update')
    email = data.pop('email', None)
    author = email or (request.user and request.user.name)
    anonymous = bool(email) or not author

    if not author:
        request.errors.add('body', 'email', 'You must provide an author')
        request.errors.status = HTTPBadRequest.code
        return

    try:
        com = update.comment(author=author, anonymous=anonymous, **data)
    except Exception as e:
        log.exception(e)
        request.errors.add('body', 'comment', 'Unable to create comment')
        return

    return dict(comment=com)
