# -*- coding: utf-8 -*-
# Copyright © 2018 Red Hat, Inc.
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
"""
Define Bodhi's WSGI application.

As of the writing of this docblock, this module is a bit misnamed since the webapp is actually
defined in bodhi.server.__init__. However, that is an anti-pattern with lots of nasty in-line
imports due to circular dependencies, and this module is intended to solve that problem.
Unfortunately, it is a backwards-incompatible change to move main() here, so it will remain in
__init__ until we make a major Bodhi release. See https://github.com/fedora-infra/bodhi/issues/2294
"""

from pyramid.events import NewRequest, subscriber

from bodhi import server


def _complete_database_session(request):
    """
    Commit the database changes if no exceptions occurred.

    This is a post-request hook. It handles rolling back or committing the session based on whether
    an exception occurred or not. To get a database session that's not tied to the request/response
    cycle, just use the :data:`Session` scoped session.

    Args:
        request (pyramid.request.Request): The current web request.
    """
    _rollback_or_commit(request)
    server.Session().close()
    server.Session.remove()


@subscriber(NewRequest)
def _prepare_request(event):
    """
    Add callbacks onto every new request.

    This function adds a callback to clean up the database session when the request is finished.

    Args:
        event (pyramid.events.NewRequest): The new request event.
    """
    event.request.add_finished_callback(_complete_database_session)


def _rollback_or_commit(request):
    """
    Commit the transaction if there are no exceptions, otherwise rollback.

    Args:
        request (pyramid.request.Request): The current web request.
    """
    if request.exception is not None:
        server.Session().rollback()
    else:
        server.Session().commit()
