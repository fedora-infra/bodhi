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

from datetime import datetime, timedelta
from cornice import Service
from pyramid.exceptions import HTTPNotFound
from sqlalchemy.sql import or_

from bodhi import log
from bodhi.models import Update, Build, Package, Release, Stack
import bodhi.schemas
import bodhi.security
from bodhi.validators import (
    validate_nvrs,
    validate_version,
    validate_uniqueness,
    validate_tags,
    validate_acls,
    validate_builds,
    validate_enums,
    validate_updates,
    validate_packages,
    validate_stack,
    validate_release,
    validate_username,
    validate_groups,
)


stack = Service(name='stack', path='/stacks/{name}',
                validators=(validate_stack,),
                description='Bodhi Stacks')
stacks = Service(name='stacks', path='/stacks/',
                 description='Bodhi Stacks')


@stack.get(accept="text/html", renderer="stacks.html")
@stack.get(accept=('application/json', 'text/json'), renderer='json')
@stack.get(accept=('application/javascript'), renderer='jsonp')
def get_stack(request):
    id = request.matchdict.get('name')
    stack = Stack.get(id, request.db)
    if not stack:
        request.errors.add('body', 'name', 'No such stack')
        request.errors.status = HTTPNotFound.code
    return stack


@stacks.get(accept="text/html", schema=bodhi.schemas.ListStacksSchema,
            renderer='stacks.html')
def query_stacks_html(request):
    db = request.db
    data = request.validated
    query = db.query(Stack).order_by(Stack.name.desc())
    total = query.count()

    page = data.get('page')
    rows_per_page = data.get('rows_per_page')
    pages = int(math.ceil(total / float(rows_per_page)))
    query = query.offset(rows_per_page * (page - 1)).limit(rows_per_page)

    return dict(
        stacks=query.all(),
        page=page,
        pages=pages,
        rows_per_page=rows_per_page,
        total=total,
    )


#@stacks.get(accept=('application/json', 'text/json'),
#              schema=bodhi.schemas.Liststackschema, renderer='json',
#              validators=(validate_release, validate_updates,
#                          validate_packages))
#def query_stacks_json(request):
#    db = request.db
#    data = request.validated
#    query = db.query(Release)
#
#    name = data.get('name')
#    if name is not None:
#        query = query.filter(Release.name.like(name))
#
#    updates = data.get('updates')
#    if updates is not None:
#        query = query.join(Release.builds).join(Build.update)
#        args = \
#            [Update.title == update.title for update in updates] +\
#            [Update.alias == update.alias for update in updates]
#        query = query.filter(or_(*args))
#
#    packages = data.get('packages')
#    if packages is not None:
#        query = query.join(Release.builds).join(Build.package)
#        query = query.filter(or_(*[Package.id == p.id for p in packages]))
#
#    total = query.count()
#
#    page = data.get('page')
#    rows_per_page = data.get('rows_per_page')
#    pages = int(math.ceil(total / float(rows_per_page)))
#    query = query.offset(rows_per_page * (page - 1)).limit(rows_per_page)
#
#    return dict(
#        stacks=query.all(),
#        page=page,
#        pages=pages,
#        rows_per_page=rows_per_page,
#        total=total,
#    )
#
#@stacks.post(schema=bodhi.schemas.SaveStackSchema,
#               acl=bodhi.security.packagers_allowed_acl, renderer='json',
#               #validators=(validate_tags, validate_enums)
#               )
#def save_release(request):
#    """Save a stack"""
#    data = request.validated
#
#    edited = data.pop("edited", None)
#
#    try:
#        if edited is None:
#            log.info("Creating a new release: %s" % data['name'])
#            r = Release(**data)
#
#        else:
#            log.info("Editing release: %s" % edited)
#            r = request.db.query(Release).filter(Release.name==edited).one()
#            for k, v in data.items():
#                setattr(r, k, v)
#
#    except Exception as e:
#        log.exception(e)
#        request.errors.add('body', 'release',
#                           'Unable to create update: %s' % e)
#        return
#
#
#    request.db.add(r)
#    request.db.flush()
#
#    return r
