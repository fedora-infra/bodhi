import math

from cornice import Service
from sqlalchemy.sql import or_

from bodhi import log
from bodhi.models import Comment, Build, Bug, CVE, Package, Update
import bodhi.schemas
import bodhi.security
from bodhi.validators import (
    validate_packages,
    validate_updates,
    validate_update_owner,
    validate_username,
)


comments = Service(name='comments', path='/comments/',
                  description='Comment submission service')


@comments.get(schema=bodhi.schemas.ListCommentSchema,
             accept=('application/json', 'text/json'), renderer='json',
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
    )


#@comments.post(schema=bodhi.schemas.SaveCommentSchema,
#              permission='create', renderer='json',
#              validators=(
#                  validate_nvrs, validate_version, validate_builds,
#                  validate_uniqueness, validate_tags, validate_acls,
#                  validate_enums))
#def new_comment(request):
#    """ Save a comment.
#
#    This entails either creating a new comment, or editing an existing one. To
#    edit an existing comment, the comment's original title must be specified in
#    the ``edited`` parameter.
#    """
#    data = request.validated
#    log.debug('validated = %s' % data)
#    req = data.get('request')
#    del(data['request'])
#
#    try:
#        if data.get('edited'):
#            log.info('Editing comment: %s' % data['edited'])
#            up = Comment.edit(request, data)
#        else:
#            log.info('Creating new comment: %s' % ' '.join(data['builds']))
#            up = Comment.new(request, data)
#            log.debug('comment = %r' % up)
#    except:
#        log.exception('An unexpected exception has occured')
#        request.errors.add('body', 'builds', 'Unable to create comment')
#        return
#
#    up.obsolete_older_comments(request)
#
#    # Set request
#    if req:
#        up.set_request(req, request)
#
#    # Send out email notifications
#
#    return up
