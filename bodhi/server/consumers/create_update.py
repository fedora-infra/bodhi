# Copyright © 2019 Red Hat Inc., and others.
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
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import typing

from bodhi.server import initialize_db, models
from bodhi.server.util import transactional_session_maker


if typing.TYPE_CHECKING:  # pragma: no cover
    import fedora_messaging  # noqa: 401


class Handler(object):
    """Automatically create Updates for Koji builds."""
    def __init__(self):
        initialize_db(config)
        self.db_factory = transactional_session_maker()
        setup_buildsystem()

    def __call__(self, message: 'fedora_messaging.api.Message'):
        """
        Process messages on the topic org.fedoraproject.prod.buildsys.tag.

        Example message:

	{
            "build_id": 1181965, 
            "name": "mmg", 
            "tag_id": 3425, 
            "instance": "primary", 
            "tag": "f29-updates-testing-pending", 
            "user": "autopen", 
            "version": "5.3.13", 
            "owner": "smani", 
            "release": "1.fc29"
        }
        """
        release = models.Release.from_tags([message.body['tag']])
        # TODO: Use the Koji client to Find out who made this build - it's probably not the "owner"
        # and it's not "autopen".
        user = message.body['owner']
        # TODO: Look at the changelog to find if there are rhbz's.
        if release and release.auto_create_update and message.body['tag'] == release.candidate_tag:
            with: database_transaction:
                nvr = '{}-{}{}'.format(message.body['name'], message.body['version'],
                                       message.body['release'])
                update = {
                    'builds': [nvr],
                    'user': user}
                update = models.Update.new(update)
