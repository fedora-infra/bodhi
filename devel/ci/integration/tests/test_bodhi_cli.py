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

import itertools
import json
import re
import textwrap

import psycopg2
import requests

from conu import ConuException
from munch import Munch

from .utils import replace_file


def _run_cli(bodhi_container, args, **kwargs):
    """Run the Bodhi CLI in the Bodhi container

    Args:
        bodhi_container (conu.DockerContainer): The Bodhi container to use.
        args (list): The CLI arguments
        kwargs (dict): The kwargs to use for the ``DockerContainer.execute()``
            method.
    Returns:
        Munch: Execution result as an object with an ``exit_code`` property
            (``int``) and an ``output`` property (``str``).
    """
    try:
        output = bodhi_container.execute(
            ["bodhi"] + args + ["--url", "http://localhost:8080"],
            **kwargs
        )
    except ConuException as e:
        return Munch(exit_code=1, output=str(e))
    return Munch(exit_code=0, output="".join(line.decode("utf-8") for line in output))


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


def test_composes_list(bodhi_container, db_container):
    """Test ``bodhi composes list``"""
    result = _run_cli(bodhi_container, ["composes", "list"])
    assert result.exit_code == 0
    # Parse command output
    updates_by_compose = {}
    output_parser = re.compile(r"[\*\s]?([\w-]+)\s+:\s+(\d+) updates \((\w+)\)")
    for line in result.output.splitlines():
        match = output_parser.match(line)
        assert match is not None
        updates_by_compose[match.group(1)] = (int(match.group(2)), match.group(3))
    # Look in the DB for what is expected
    expected = {}
    query = """SELECT
    r.name, c.request, COUNT(u.id), c.state
    FROM composes c
    JOIN releases r ON r.id = c.release_id
    JOIN updates u ON u.release_id = r.id AND u.request = c.request
    WHERE r.state = 'current' AND u.locked = TRUE
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
        result = _run_cli(bodhi_container, ["releases", "info", release["name"]])
        assert result.exit_code == 0
        expected = """Release:
  Name:                {name}
  Long Name:           {long_name}
  Version:             {version}
  Branch:              {branch}
  ID Prefix:           {id_prefix}
  Dist Tag:            {dist_tag}
  Stable Tag:          {stable_tag}
  Testing Tag:         {testing_tag}
  Candidate Tag:       {candidate_tag}
  Pending Signing Tag: {pending_signing_tag}
  Pending Testing Tag: {pending_testing_tag}
  Pending Stable Tag:  {pending_stable_tag}
  Override Tag:        {override_tag}
  State:               {state}
  Email Template:      {mail_template}
""".format(**release)
        assert result.output == expected


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
    result = _run_cli(bodhi_container, ["overrides", "query"])
    assert result.exit_code == 0
    last_line = result.output.split("\n")[-2]
    assert last_line == "{} overrides found (20 shown)".format(total)


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
    result = _run_cli(bodhi_container, ["updates", "query"])
    assert result.exit_code == 0
    last_line = result.output.split("\n")[-2]
    assert last_line == "{} updates found (20 shown)".format(total)


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
            update = _db_record_to_munch(curs, curs.fetchone())
            update.comments = []
            curs.execute(query_comments, (update.id, ))
            for record in curs:
                update.comments.append(_db_record_to_munch(curs, record))
            curs.execute(query_karma, (update.id, ))
            update.karma = _db_record_to_munch(curs, curs.fetchone()).karma
            curs.execute(query_ct, (update.id, ))
            update.content_type = _db_record_to_munch(curs, curs.fetchone()).type
            curs.execute(query_builds, (update.id, ))
            update.builds = [r[0] for r in curs]
    conn.close()
    # Run the command
    result = _run_cli(bodhi_container, ["updates", "query", "--updateid", update.alias])
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
                {"original_spec_nvr": b}
                for b in update.builds
            ] + [
                {"item": update.alias, "type": "bodhi_update"}
            ]
        }),
    ).json()
    assert "summary" in greenwave_result
    assert "CI Status: {}".format(greenwave_result["summary"]) in result.output


def test_updates_download(bodhi_container, db_container):
    """Test ``bodhi updates download``"""
    # Fetch the last updates from the DB
    builds = []
    db_ip = db_container.get_IPv4s()[0]
    query_updates = "SELECT id, alias, title FROM updates ORDER BY date_submitted DESC LIMIT 3"
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
        result = _run_cli(bodhi_container, cmd)
    assert result.exit_code == 0
    for update in updates:
        assert "Downloading packages from {}".format(update['title']) in result.output
    for build_id in builds:
        assert "TESTING CALL /usr/bin/koji download-build {}".format(build_id) in result.output
