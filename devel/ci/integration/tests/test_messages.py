# Copyright © 2019 Red Hat, Inc.
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

import time

from conu import ConuException

from .utils import get_sent_messages


def test_push_composer_start(bodhi_container, db_container, rabbitmq_container):
    try:
        output = bodhi_container.execute(["bodhi-push", "--username", "ci", "-y"])
    except ConuException as e:
        assert False, str(e)
    output = "".join(line.decode("utf-8") for line in output)
    assert output.endswith("Sending composer.start message\n")
    # Give some time for the message to go around
    time.sleep(2)
    messages = get_sent_messages(rabbitmq_container)
    assert len(messages) == 1
    message = messages[0]
    assert message.topic == "org.fedoraproject.prod.bodhi.composer.start"
    assert "composes" in message.body
    assert len(message.body["composes"]) > 0
    assert message.body["agent"] == "ci"
