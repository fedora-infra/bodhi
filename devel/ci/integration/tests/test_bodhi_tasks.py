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
import json
import time

from conu import ConuException
import psycopg2
import pytest

from .utils import get_task_results, read_file, run_cli


def test_push_composer_start(bodhi_container, db_container, rabbitmq_container):
    try:
        output = bodhi_container.execute(
            ["bodhi-push", "--username", "ci", "-y"],
            exec_create_kwargs={"environment": {"PYTHONWARNINGS": "ignore"}},
        )
    except ConuException as e:
        assert False, str(e)
    output = "".join(line.decode("utf-8") for line in output)
    assert output.endswith("Requesting a compose\n")
    # Check how many composes should be done
    # because we later check for pungi.log, we need to see if there are composes that apply
    # we can get these from the type field of the builds table,
    # after joining with the composes table through updates table.
    query = """
      SELECT DISTINCT
        c.release_id, c.request, c.checkpoints, state, b.type
      FROM
        composes AS c
      INNER JOIN updates AS u ON (c.release_id = u.release_id AND c.request = u.request )
      INNER JOIN builds AS b ON (b.update_id = u.id)
      WHERE b.type = 'rpm' AND state <> 'failed';
    """
    db_ip = db_container.get_IPv4s()[0]
    conn = psycopg2.connect("dbname=bodhi2 user=postgres host={}".format(db_ip))
    with conn:
        with conn.cursor() as curs:
            curs.execute(query)
            composes = curs.fetchall()
    valid_composes = []
    for compose in composes:
        checkpoints = json.loads(compose[2])
        if not checkpoints.get("compose_done"):
            valid_composes.append(compose)
    if not valid_composes:
        pytest.skip("We can't test whether composes were run, there are none pending")
    # Give some time for the message to go around and the command to be run.
    try:
        bodhi_container.execute(["wait-for-file", "/tmp/pungi-calls.log"])
    except ConuException as e:
        print(f"Waiting for pungi-calls.log failed, relevant composes: {composes}")
        with read_file(bodhi_container, "/tmp/celery.log") as log:
            print(log.read())
        raise e
    with read_file(bodhi_container, "/tmp/pungi-calls.log") as fh:
        calls = fh.read().splitlines()
    # Just check that pungi was run at least once, we're not testing the
    # Compose runner here.
    assert len(calls) > 0


def test_update_edit(
    bodhi_container, ipsilon_container, db_container, rabbitmq_container
):
    def find_update():
        query = (
            "SELECT alias "
            "FROM updates u "
            "JOIN releases r ON u.release_id = r.id "
            "JOIN users us ON u.user_id = us.id "
            "WHERE r.state != 'archived' AND r.composed_by_bodhi = TRUE "
            # Recent EPEL releases are more complex and lead to flakiness. Example:
            # Cannot find release associated with build: netatalk-3.1.12-27.el9,
            # tags: ['el9-updates-candidate', 'el9', 'el9-updates-testing']
            "AND r.id_prefix = 'FEDORA' "
            "AND u.locked = FALSE AND u.status IN ('pending', 'testing') "
            "AND u.type != 'security' "
            "AND u.from_tag IS NULL "
            "AND us.name NOT LIKE '%packagerbot%' "
            "ORDER BY u.date_submitted DESC LIMIT 1"
        )
        db_ip = db_container.get_IPv4s()[0]
        conn = psycopg2.connect("dbname=bodhi2 user=postgres host={}".format(db_ip))
        with conn:
            with conn.cursor() as curs:
                curs.execute(query)
                result = curs.fetchone()
                assert result is not None
                update_alias = result[0]
        conn.close()
        return update_alias

    def find_bug():
        base_query = [
            "SELECT bug_id",
            "FROM bugs b",
            "WHERE TRUE",
            "LIMIT 1"
        ]
        db_ip = db_container.get_IPv4s()[0]
        conn = psycopg2.connect("dbname=bodhi2 user=postgres host={}".format(db_ip))
        with conn:
            with conn.cursor() as curs:
                curs.execute(" ".join(base_query))
                result = curs.fetchone()
                assert result is not None
                bug_id = result[0]
        conn.close()
        return str(bug_id)

    update_alias = find_update()
    bug_id = find_bug()
    # Remove previous task results
    # bodhi_container.execute(["find", "/srv/celery-results", "-type", "f", "-delete"])
    result = run_cli(
        bodhi_container,
        [
            "updates",
            "edit",
            "--debug",
            "--bugs",
            bug_id,
            "--stable-karma",
            "1",
            update_alias,
        ]
    )
    if result.exit_code != 0:
        with read_file(bodhi_container, "/httpdir/errorlog") as log:
            print(log.read())
        assert False, result.output
    try:
        bodhi_container.execute(["wait-for-file", "-d", "/srv/celery-results"])
    except ConuException as e:
        print(f"Waiting for celery results failed, relevant update: {update_alias}")
        print("Apache logs:")
        with read_file(bodhi_container, "/httpdir/errorlog") as log:
            print(log.read())
        print("Celery logs:")
        with read_file(bodhi_container, "/tmp/celery.log") as log:
            print(log.read())
        raise e
    result = {"status": "RETRY"}
    while result["status"] == "RETRY":
        results = get_task_results(bodhi_container)
        assert len(results) > 0
        result = results[-1]
        time.sleep(1)
    assert result["status"] == "SUCCESS", result
    assert result["traceback"] is None
