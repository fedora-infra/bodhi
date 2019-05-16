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
"""Test the bodhi async tasks."""

import psycopg2
import pytest
from conu import ConuException

from .utils import read_file, wait_for_file


def test_push_composer_start(bodhi_container, db_container, rabbitmq_container):
    try:
        output = bodhi_container.execute(["bodhi-push", "--username", "ci", "-y"])
    except ConuException as e:
        assert False, str(e)
    output = "".join(line.decode("utf-8") for line in output)
    assert output.endswith("Requesting a compose\n")
    # Check how many composes should be done
    query = "SELECT COUNT(*) FROM composes"
    db_ip = db_container.get_IPv4s()[0]
    conn = psycopg2.connect("dbname=bodhi2 user=postgres host={}".format(db_ip))
    with conn:
        with conn.cursor() as curs:
            curs.execute(query)
            composes_count = curs.fetchone()[0]
    if composes_count == 0:
        pytest.skip("We can't test whether composes were run, there are none pending")
    # Give some time for the message to go around and the command to be run.
    wait_for_file(bodhi_container, "/tmp/pungi-calls.log")
    with read_file(bodhi_container, "/tmp/pungi-calls.log") as fh:
        calls = fh.read().splitlines()
    # Just check that pungi was run at least once, we're not testing the
    # Compose runner here.
    assert len(calls) > 0
