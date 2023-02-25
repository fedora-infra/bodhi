# Copyright © 2018-2019 Red Hat, Inc.
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

import itertools
import json
import re
import textwrap

from munch import Munch
import psycopg2
import pytest
import requests

from .utils import read_file, replace_file, run_cli


def _db_record_to_munch(cursor, record):
    """Convert a database record to a Munch object.

    Args:
        cursor (psycopg2.extensions.cursor): The database cursor.
        record (tuple): The record to convert.
    Returns:
        Munch: An object with column names as attributes and record values as
            values.
    """
    return Munch(dict([
        (cursor.description[i].name, record[i])
        for i in range(len(record))
    ]))


def test_composes_info(bodhi_container, db_container):
    """Test ``bodhi composes info``"""
    compose = {}
    updates = []
    # Fetch the latest compse from the DB
    query_composes = """SELECT
      r.name as release,
      c.state as state,
      c.request as request,
      c.date_created as date_created,
      c.state_date as state_date,
      c.error_message as error_message
    FROM composes c
    JOIN releases r ON r.id = c.release_id
    WHERE r.state = 'current' OR r.state = 'pending'
    ORDER BY date_created DESC LIMIT 1
    """
    # Fetch updates for compse from the DB
    query_updates = """SELECT
    u.alias, u.id, u.type, u.display_name
    FROM updates u
    JOIN releases r ON r.id = u.release_id
    WHERE r.name = %s AND u.locked = TRUE AND u.request = %s
    ORDER BY u.date_submitted
    """
    # Fetch builds for each update from the DB
    query_builds = """SELECT
    nvr, type
    FROM builds
    WHERE update_id = %s
    ORDER BY nvr
    """

    db_ip = db_container.get_IPv4s()[0]
    conn = psycopg2.connect("dbname=bodhi2 user=postgres host={}".format(db_ip))
    with conn:
        with conn.cursor() as curs:
            curs.execute(query_composes)
            row = curs.fetchone()
            if row is None:
                pytest.skip("No compose in the database")
            for column, value in zip(curs.description, row):
                compose[column.name] = value
            curs.execute(query_updates, (compose['release'], compose['request'], ))
            for row in curs.fetchall():
                updates.append({
                    'alias': row[0], 'id': row[1], 'type': row[2], 'display_name': row[3],
                    'builds': []
                })
            for update in updates:
                curs.execute(query_builds, (update['id'], ))
                for row in curs.fetchall():
                    update['builds'].append({'nvr': row[0], 'content_type': row[1]})
    conn.close()

    result = run_cli(bodhi_container, ["composes", "info", compose['release'], compose['request']])
    assert result.exit_code == 0

    security = ' '
    for update in updates:
        if update['type'] == 'security':
            security = '*'
            break
    if len(updates) and len(updates[0]['builds']):
        content_type = updates[0]['builds'][0]['content_type']
    else:
        content_type = None
    title = f"{security}{compose['release']}-{compose['request']}"
    details = f"{len(updates):3d} updates ({compose['state']}) "
    separator = "================================================================================\n"
    header = f"     {title:<16}: {details}\n"

    expected_output = separator + header + separator
    expected_output += f"""\
Content Type: {content_type}
     Started: {compose['date_created'].strftime("%Y-%m-%d %H:%M:%S")}
     Updated: {compose['state_date'].strftime("%Y-%m-%d %H:%M:%S")}
"""
    # If the compose doesn't have a error_message, the CLI does not render the Error: line.
    if compose['error_message']:
        expected_output += f"       Error: {compose['error_message']}\n"

    expected_output += "\nUpdates:\n\n"
    for update in updates:
        if update["display_name"]:
            update_builds = update["display_name"]
        elif len(update['builds']) > 2:
            builds_left = len(update['builds']) - 2
            suffix = f", and {builds_left} more"
            update_builds = ", ".join([u['nvr'] for u in update['builds'][:2]])
            update_builds += suffix
        else:
            update_builds = " and ".join([u['nvr'] for u in update['builds']])
        expected_output += f"\t{update['alias']}: {update_builds}\n"
    expected_output += "\n"

    assert expected_output == result.output


def test_composes_list(bodhi_container, db_container):
    """Test ``bodhi composes list``"""
    result = run_cli(bodhi_container, ["composes", "list"])
    assert result.exit_code == 0
    # Parse command output
    updates_by_compose = {}
    output_parser = re.compile(r"[\*\s]?([\w-]+)\s*:\s+(\d+) updates \((\w+)\)")
    for line in result.output.splitlines():
        match = output_parser.match(line)
        assert match is not None
        updates_by_compose[match.group(1)] = (int(match.group(2)), match.group(3))
    # Look in the DB for what is expected
    expected = {}
    query = """SELECT
    r.name, c.request, SUM(CASE WHEN u.locked = TRUE THEN 1 ELSE 0 END), c.state
    FROM composes c
    JOIN releases r ON r.id = c.release_id
    JOIN updates u ON u.release_id = r.id AND u.request = c.request
    WHERE (r.state = 'current' OR r.state = 'pending' OR
    (r.state = 'frozen' AND u.request = 'testing'))
    GROUP BY r.name, c.request, c.state
    """
    db_ip = db_container.get_IPv4s()[0]
    conn = psycopg2.connect("dbname=bodhi2 user=postgres host={}".format(db_ip))
    with conn:
        with conn.cursor() as curs:
            curs.execute(query)
            for record in curs:
                compose = "{}-{}".format(record[0], record[1])
                expected[compose] = (record[2], record[3])
    conn.close()
    assert updates_by_compose == expected


def test_releases_info(bodhi_container, db_container):
    """Test ``bodhi releases info``"""
    # Fetch the available releases from the DB
    db_ip = db_container.get_IPv4s()[0]
    query = "SELECT * FROM releases"
    releases = []
    conn = psycopg2.connect("dbname=bodhi2 user=postgres host={}".format(db_ip))
    with conn:
        with conn.cursor() as curs:
            curs.execute(query)
            for record in curs:
                releases.append(_db_record_to_munch(curs, record))
    conn.close()
    for release in releases:
        # Run the command for each release
        result = run_cli(bodhi_container, ["releases", "info", release["name"]])
        assert result.exit_code == 0
        expected = """Release:
  Name:                     {name}
  Long Name:                {long_name}
  Version:                  {version}
  Branch:                   {branch}
  ID Prefix:                {id_prefix}
  Dist Tag:                 {dist_tag}
  Stable Tag:               {stable_tag}
  Testing Tag:              {testing_tag}
  Candidate Tag:            {candidate_tag}
  Pending Signing Tag:      {pending_signing_tag}
  Pending Testing Tag:      {pending_testing_tag}
  Pending Stable Tag:       {pending_stable_tag}
  Override Tag:             {override_tag}
  State:                    {state}
  Email Template:           {mail_template}
  Composed by Bodhi:        {composed_by_bodhi}
  Create Automatic Updates: {create_automatic_updates}
  Package Manager:          {package_manager}
  Testing Repository:       {testing_repository}
  End of Life:              {eol}
""".format(**release)
        assert result.output == expected


def test_releases_list(bodhi_container, db_container):
    """Test ``bodhi releases list``"""
    # Fetch the available releases from the DB
    db_ip = db_container.get_IPv4s()[0]
    query_pending_releases = "SELECT name FROM releases WHERE state = 'pending'"
    query_archived_releases = "SELECT name FROM releases WHERE state = 'archived'"
    query_current_releases = "SELECT name FROM releases WHERE state = 'current'"
    query_frozen_releases = "SELECT name FROM releases WHERE state = 'frozen'"
    pending_releases = []
    archived_releases = []
    current_releases = []
    frozen_releases = []
    conn = psycopg2.connect("dbname=bodhi2 user=postgres host={}".format(db_ip))
    with conn:
        with conn.cursor() as curs:
            curs.execute(query_pending_releases)
            for record in curs:
                pending_releases.append(record[0])
            curs.execute(query_archived_releases)
            for record in curs:
                archived_releases.append(record[0])
            curs.execute(query_current_releases)
            for record in curs:
                current_releases.append(record[0])
            curs.execute(query_frozen_releases)
            for record in curs:
                frozen_releases.append(record[0])
    conn.close()

    # Run the command
    # To fetch all existing releases in one call, we have to add --rows option
    result = run_cli(bodhi_container, ["releases", "list", "--display-archived", "--rows", "100"])
    assert result.exit_code == 0
    if len(pending_releases):
        expected_pending_output = "pending:"
        for name in pending_releases:
            expected_pending_output += f"\n  Name:                {name}"
        assert expected_pending_output in result.output
    if len(archived_releases):
        expected_archived_output = "archived:"
        for name in archived_releases:
            expected_archived_output += f"\n  Name:                {name}"
        assert expected_archived_output in result.output
    if len(current_releases):
        expected_current_output = "current:"
        for name in current_releases:
            expected_current_output += f"\n  Name:                {name}"
        assert expected_current_output in result.output
    if len(frozen_releases):
        expected_frozen_output = "frozen:"
        for name in frozen_releases:
            expected_frozen_output += f"\n  Name:                {name}"
        assert expected_frozen_output in result.output


def test_overrides_query(bodhi_container, db_container):
    """Test ``bodhi overrides query``"""
    # Fetch the number of overrides from the DB
    db_ip = db_container.get_IPv4s()[0]
    query = "SELECT COUNT(*) FROM buildroot_overrides"
    conn = psycopg2.connect("dbname=bodhi2 user=postgres host={}".format(db_ip))
    with conn:
        with conn.cursor() as curs:
            curs.execute(query)
            total = curs.fetchone()[0]
    conn.close()
    # Run the command
    result = run_cli(bodhi_container, ["overrides", "query"])
    assert result.exit_code == 0
    last_line = result.output.split("\n")[-2]
    assert last_line == "{} overrides found ({} shown)".format(total, min(total, 20))


def test_updates_query_total(bodhi_container, db_container):
    """Test listing the updates with ``bodhi updates query``"""
    # Fetch the number of updates from the DB
    db_ip = db_container.get_IPv4s()[0]
    query = "SELECT COUNT(*) FROM updates"
    conn = psycopg2.connect("dbname=bodhi2 user=postgres host={}".format(db_ip))
    with conn:
        with conn.cursor() as curs:
            curs.execute(query)
            total = curs.fetchone()[0]
    conn.close()
    # Run the command
    result = run_cli(bodhi_container, ["updates", "query"])
    assert result.exit_code == 0
    last_line = result.output.split("\n")[-2]
    assert last_line == "{} updates found ({} shown)".format(total, min(total, 20))


def test_updates_query_details(bodhi_container, db_container, greenwave_container):
    """Test getting an update's details with ``bodhi updates query``"""
    # Fetch the last update from the DB
    db_ip = db_container.get_IPv4s()[0]
    query_update = (
        "SELECT "
        "  users.name as username, "
        "  releases.long_name as release, "
        "  updates.* "
        "FROM updates "
        "JOIN users ON updates.user_id = users.id "
        "JOIN releases ON updates.release_id = releases.id "
        "WHERE releases.state = 'current' "
        "AND updates.critpath = FALSE "  # Greenwave results are more complex for critpath
        "ORDER BY date_submitted DESC LIMIT 1"
    )
    query_comments = (
        "SELECT u.name as username, c.timestamp, c.karma, c.text FROM comments c "
        "JOIN users u ON c.user_id = u.id "
        "WHERE update_id = %s ORDER BY c.timestamp"
    )
    query_karma = (
        "SELECT SUM(comments.karma) as karma FROM comments "
        "JOIN updates ON comments.update_id = updates.id "
        "WHERE update_id = %s"
    )
    query_ct = (
        "SELECT builds.type FROM builds "
        "JOIN updates ON builds.update_id = updates.id "
        "WHERE update_id = %s LIMIT 1"
    )
    query_builds = "SELECT nvr FROM builds WHERE update_id = %s ORDER BY nvr"
    conn = psycopg2.connect("dbname=bodhi2 user=postgres host={}".format(db_ip))
    with conn:
        with conn.cursor() as curs:
            curs.execute(query_update)
            result = curs.fetchone()
            if result is None:
                pytest.skip("No update in the database")
            update = _db_record_to_munch(curs, result)
            update.comments = []
            curs.execute(query_comments, (update.id, ))
            for record in curs:
                update.comments.append(_db_record_to_munch(curs, record))
            curs.execute(query_karma, (update.id, ))
            update.karma = _db_record_to_munch(curs, curs.fetchone()).karma or 0
            curs.execute(query_ct, (update.id, ))
            update.content_type = _db_record_to_munch(curs, curs.fetchone()).type
            curs.execute(query_builds, (update.id, ))
            update.builds = [r[0] for r in curs]
    conn.close()
    # Run the command
    result = run_cli(bodhi_container, ["updates", "query", "--updateid", update.alias])
    assert result.exit_code == 0
    assert "Update ID: {}".format(update.alias) in result.output
    assert "Content Type: {}".format(update.content_type) in result.output
    assert "Release: {}".format(update.release) in result.output
    assert "Status: {}".format(update.status) in result.output
    assert "Type: {}".format(update.type) in result.output
    assert "Severity: {}".format(update.severity) in result.output
    assert "Karma: {}".format(update.karma) in result.output
    expected_autokarma = (
        "Autokarma: {u.autokarma}  [{u.unstable_karma}, {u.stable_karma}]"
    ).format(u=update)
    assert expected_autokarma in result.output
    # If the update doesn't have a request, the CLI does not render the Request: line.
    if update.request:
        assert "Request: {}".format(update.request) in result.output
    # Notes are formatted
    formatted_notes = list(itertools.chain(*[
        textwrap.wrap(line, width=66)
        for line in update.notes.splitlines()
    ]))
    for index, notes_line in enumerate(formatted_notes):
        if index == 0:
            assert "Notes: {}".format(notes_line) in result.output
        else:
            assert "     : {}".format(notes_line) in result.output
    assert "Submitter: {}".format(update.username) in result.output
    expected_submitted = "Submitted: {}".format(
        update.date_submitted.strftime("%Y-%m-%d %H:%M:%S")
    )
    assert expected_submitted in result.output
    for comment in update.comments:
        assert "{user} - {date} (karma {karma})".format(
            user=comment.username,
            date=comment.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            karma=comment.karma,
        ) in result.output
        # Comments are formatted too
        for index, comment_line in enumerate(textwrap.wrap(comment.text, width=66)):
            assert comment_line in result.output
    assert "1 updates found (1 shown)" in result.output
    # CI Status
    gw_ip = greenwave_container.get_IPv4s()[0]
    greenwave_result = requests.post(
        "http://{}:8080/api/v1.0/decision".format(gw_ip),
        headers={"content-type": "application/json"},
        data=json.dumps({
            "product_version": update.release.lower().replace(' ', '-'),
            "decision_context": (
                "bodhi_update_push_stable" if update.status == "stable"
                else "bodhi_update_push_testing"
            ),
            "subject": [
                {"item": b, "type": "koji_build"}
                for b in update.builds
            ] + [
                {"item": update.alias, "type": "bodhi_update"}
            ],
            "verbose": True,
        }),
    ).json()
    print("greenwave result:", greenwave_result)
    assert "summary" in greenwave_result
    assert "CI Status: {}".format(greenwave_result["summary"]) in result.output


def test_updates_download(bodhi_container, db_container):
    """Test ``bodhi updates download``"""
    # Fetch the last updates from the DB
    builds = []
    db_ip = db_container.get_IPv4s()[0]
    query_updates = "SELECT id, alias FROM updates ORDER BY date_submitted DESC LIMIT 3"
    query_builds = "SELECT nvr FROM builds WHERE update_id = %s ORDER BY nvr"
    conn = psycopg2.connect("dbname=bodhi2 user=postgres host={}".format(db_ip))
    with conn:
        with conn.cursor() as curs:
            curs.execute(query_updates)
            updates = [_db_record_to_munch(curs, record) for record in curs]
            for update in updates:
                curs.execute(query_builds, (update.id, ))
                builds.extend([r[0] for r in curs])
    conn.close()
    # Prepare the command to run
    cmd = [
        "updates", "download", "--arch", "all",
        "--updateid", ",".join([u.alias for u in updates]),
    ]
    # The bodhi CLI will execute the koji CLI. Replace that executable with
    # something we can track.
    koji_mock = "#!/bin/sh\necho TESTING CALL $0 $@\n"
    with replace_file(bodhi_container, "/usr/bin/koji", koji_mock):
        result = run_cli(bodhi_container, cmd)
    assert result.exit_code == 0
    for update in updates:
        assert "Downloading packages from {}".format(update['alias']) in result.output
    for build_id in builds:
        assert re.search(
            f"TESTING CALL .*koji download-build.*{re.escape(build_id)}",
            result.output
        )


def test_updates_request(bodhi_container, ipsilon_container, db_container):
    def find_update():
        base_query = [
            "SELECT alias",
            "FROM updates u",
            "JOIN releases r ON u.release_id = r.id",
            "WHERE r.state != 'archived' AND r.composed_by_bodhi = TRUE",
            "AND u.locked = FALSE",
            "ORDER BY u.date_submitted DESC LIMIT 1"
        ]
        db_ip = db_container.get_IPv4s()[0]
        conn = psycopg2.connect("dbname=bodhi2 user=postgres host={}".format(db_ip))
        with conn:
            with conn.cursor() as curs:
                # First try to find an update that we can use.
                query = base_query[:]
                query.insert(
                    4,
                    "AND u.status = 'testing' AND u.request IS NULL and u.critpath = FALSE"
                )
                query.insert(
                    5,
                    "AND u.test_gating_status IN ('ignored', 'passed', 'greenwave_failed')"
                )
                curs.execute(" ".join(query))
                result = curs.fetchone()
                assert result is not None
                update_alias = result[0]
                # Now let's make sure the update is pushable to stable
                curs.execute(
                    "UPDATE updates SET stable_karma = 0, stable_days = 0 "
                    "WHERE alias = %s",
                    (update_alias,)
                )
        conn.close()
        return update_alias

    update_alias = find_update()
    result = run_cli(
        bodhi_container, ["updates", "request", update_alias, "stable"]
    )
    if result.exit_code != 0:
        with read_file(bodhi_container, "/httpdir/errorlog") as log:
            print(log.read())
        assert False, result.output
    assert "This update has been submitted for stable by guest." in result.output
