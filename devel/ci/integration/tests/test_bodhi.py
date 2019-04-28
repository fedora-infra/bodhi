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

import math

import psycopg2

from tests.utils import read_file


def test_get_root(bodhi_container, db_container):
    """Test ``/`` path"""
    # Fetch releases from DB
    query = (
        "SELECT long_name "
        "FROM releases "
        "WHERE state = 'pending' OR state = 'current'"
    )
    db_ip = db_container.get_IPv4s()[0]
    conn = psycopg2.connect("dbname=bodhi2 user=postgres host={}".format(db_ip))
    with conn:
        with conn.cursor() as curs:
            curs.execute(query)
            expected_releases = [r[0] for r in curs]
    conn.close()

    # GET on /
    with bodhi_container.http_client(port="8080") as c:
        headers = {'Accept': 'text/html'}
        http_response = c.get("/", headers=headers)

    try:
        assert http_response.ok
        assert "Fedora Update System" in http_response.text
        for release_long_name in expected_releases:
            assert release_long_name in http_response.text
    except AssertionError:
        print(http_response)
        print(http_response.text)
        with read_file(bodhi_container, "/httpdir/errorlog") as log:
            print(log.read())
        raise


def test_get_metrics(bodhi_container):
    """Test ``/metrics`` path"""
    # GET on /metrics
    with bodhi_container.http_client(port="8080") as c:
        headers = {'Accept': 'text/html'}
        http_response = c.get("/metrics", headers=headers)

    try:
        assert http_response.ok
        assert "Bodhi Metrics" in http_response.text
    except AssertionError:
        print(http_response)
        print(http_response.text)
        with read_file(bodhi_container, "/httpdir/errorlog") as log:
            print(log.read())
        raise


def test_get_api_version(bodhi_container):
    """Test ``/api_version`` path"""
    # GET on /api_version
    # this is standard `requests.Response`
    http_response = bodhi_container.http_request(path="/api_version", port=8080)

    # Get bodhi version from source
    ret = bodhi_container.execute(
        "python3 -c \"import pkg_resources; print(pkg_resources."
        "get_distribution('bodhi').version, end='', flush=True)\""
    )
    bodhi_version = ret[0].decode("utf-8")
    try:
        assert http_response.ok
        assert http_response.json() == {"version": bodhi_version}
    except AssertionError:
        print(http_response)
        print(http_response.text)
        with read_file(bodhi_container, "/httpdir/errorlog") as log:
            print(log.read())
        raise


def test_get_notfound_view(bodhi_container):
    """Test not_found_view path"""
    # GET on /inexisting_path
    with bodhi_container.http_client(port="8080") as c:
        headers = {'Accept': 'text/html'}
        http_response = c.get("/inexisting_path", headers=headers)

    try:
        assert not http_response.ok
        assert http_response.status_code == 404
        assert "Not Found" in http_response.text
        assert "The resource could not be found" in http_response.text
    except AssertionError:
        print(http_response)
        print(http_response.text)
        with read_file(bodhi_container, "/httpdir/errorlog") as log:
            print(log.read())
        raise


def test_get_releases_view(bodhi_container, db_container):
    """Test ``/releases`` path"""
    # Fetch releases from DB
    query = """SELECT long_name FROM releases"""
    db_ip = db_container.get_IPv4s()[0]
    conn = psycopg2.connect("dbname=bodhi2 user=postgres host={}".format(db_ip))
    with conn:
        with conn.cursor() as curs:
            curs.execute(query)
            for record in curs:
                expected_releases = [r[0] for r in curs]
    conn.close()

    # GET on /releases
    with bodhi_container.http_client(port="8080") as c:
        headers = {'Accept': 'text/html'}
        http_response = c.get(f"/releases", headers=headers)

    try:
        assert http_response.ok
        for release_long_name in expected_releases:
            assert release_long_name in http_response.text
    except AssertionError:
        print(http_response)
        print(http_response.text)
        with read_file(bodhi_container, "/httpdir/errorlog") as log:
            print(log.read())
        raise


def test_get_release_view(bodhi_container, db_container):
    """Test ``/releases/{name}`` path"""
    # Fetch releases with state 'current' from DB
    query = (
        "SELECT "
        "long_name, "
        "state, "
        "dist_tag, "
        "stable_tag, "
        "testing_tag, "
        "candidate_tag, "
        "pending_signing_tag, "
        "pending_testing_tag, "
        "pending_stable_tag, "
        "override_tag "
        "FROM releases "
        "WHERE state = 'current' LIMIT 1"
    )
    db_ip = db_container.get_IPv4s()[0]
    conn = psycopg2.connect("dbname=bodhi2 user=postgres host={}".format(db_ip))
    with conn:
        with conn.cursor() as curs:
            curs.execute(query)
            release_info = curs.fetchone()
    conn.close()

    release_long_name = release_info[0]

    # GET on /release/{name}
    with bodhi_container.http_client(port="8080") as c:
        headers = {'Accept': 'text/html'}
        http_response = c.get(f"/releases/{release_long_name}", headers=headers)

    try:
        assert http_response.ok
        assert f"Latest {release_long_name} updates" in http_response.text
        for column_content in release_info:
            assert column_content in http_response.text
    except AssertionError:
        print(http_response)
        print(http_response.text)
        with read_file(bodhi_container, "/httpdir/errorlog") as log:
            print(log.read())
        raise


def test_get_updates_view(bodhi_container, db_container):
    """Test ``/updates`` path"""
    # Fetch updates from DB
    expected_updates_titles = []
    query_updates = (
        "SELECT id "
        "FROM updates "
        "ORDER BY date_submitted DESC LIMIT 20"
    )
    query_builds = (
        "SELECT builds.nvr as nvr "
        "FROM builds "
        "JOIN updates ON builds.update_id = updates.id "
        "WHERE update_id = %s"
    )
    db_ip = db_container.get_IPv4s()[0]
    conn = psycopg2.connect("dbname=bodhi2 user=postgres host={}".format(db_ip))
    with conn:
        with conn.cursor() as curs:
            curs.execute(query_updates)
            expected_updates = [row[0] for row in curs]
            for update_id in expected_updates:
                curs.execute(query_builds, (update_id, ))
                builds_nvrs = [row[0] for row in curs]
                builds_nvrs.sort()
                expected_updates_titles.append(" ".join(builds_nvrs))
    conn.close()

    # GET on /updates
    with bodhi_container.http_client(port="8080") as c:
        headers = {'Accept': 'text/html'}
        http_response = c.get("/updates", headers=headers)

    try:
        assert http_response.ok
        for update_titile in expected_updates_titles:
            max_length = 70
            if len(update_titile) > max_length:
                update_titile = update_titile[:max_length] + "..."
            assert update_titile in http_response.text
    except AssertionError:
        print(http_response)
        print(http_response.text)
        with read_file(bodhi_container, "/httpdir/errorlog") as log:
            print(log.read())
        raise


def test_get_update_view(bodhi_container, db_container):
    """Test ``/updates/{alias}`` path"""
    # Fetch latest update with 'testing' status from DB
    query_updates = (
        "SELECT "
        "  updates.id as id, "
        "  updates.alias as alias, "
        "  updates.status as status, "
        "  updates.type as type, "
        "  updates.severity as severity, "
        "  updates.stable_karma as stable_karma, "
        "  updates.unstable_karma as unstable_karma, "
        "  updates.autokarma as autokarma, "
        "  updates.request as request, "
        "  updates.locked as locked, "
        "  updates.suggest as suggest, "
        "  users.name as username "
        "FROM updates "
        "JOIN users ON updates.user_id = users.id "
        "WHERE status = 'testing' "
        "ORDER BY date_submitted DESC LIMIT 1"
    )
    query_builds = (
        "SELECT "
        "  builds.nvr as nvr, "
        "  builds.type as content_type "
        "FROM builds "
        "JOIN updates ON builds.update_id = updates.id "
        "WHERE update_id = %s"
    )
    db_ip = db_container.get_IPv4s()[0]
    conn = psycopg2.connect("dbname=bodhi2 user=postgres host={}".format(db_ip))
    with conn:
        with conn.cursor() as curs:
            curs.execute(query_updates)
            update_info = {}
            for value, description in zip(curs.fetchone(), curs.description):
                update_info[description.name] = value
            curs.execute(query_builds, (update_info["id"], ))
            rows = curs.fetchall()
            builds_nvrs = [row[0] for row in rows]
            update_info["content_type"] = rows[0][1]

    conn.close()

    # GET on latest testing update
    with bodhi_container.http_client(port="8080") as c:
        headers = {'Accept': 'text/html'}
        http_response = c.get(f"/updates/{update_info['alias']}", headers=headers)

    content_type_mapping = {
        'base': 'Base',
        'rpm': 'RPM',
        'module': 'Module',
        'container': 'Container',
        'flatpak': 'Flatpak',
    }

    try:
        assert http_response.ok
        assert update_info['alias'] in http_response.text
        assert update_info['status'] in http_response.text
        assert update_info['type'] in http_response.text
        assert update_info['severity'] in http_response.text
        assert update_info['username'] in http_response.text
        assert content_type_mapping[update_info['content_type']] in http_response.text
        assert f"stable threshold: {update_info['stable_karma']}" in http_response.text
        assert f"unstable threshold: {update_info['unstable_karma']}" in http_response.text
        if update_info['request']:
            assert update_info['request'] in http_response.text
        if update_info['autokarma']:
            assert "Enabled" in http_response.text
        else:
            assert "Disabled" in http_response.text
        if update_info['locked']:
            assert "Locked" in http_response.text
        if update_info['suggest'] == "reboot":
            assert "Reboot Required" in http_response.text
        elif update_info['suggest'] == "logout":
            assert "Logout Required" in http_response.text
        for nvr in builds_nvrs:
            assert nvr in http_response.text
    except AssertionError:
        print(http_response)
        print(http_response.text)
        with read_file(bodhi_container, "/httpdir/errorlog") as log:
            print(log.read())
        raise


def test_get_user_view(bodhi_container, db_container):
    """Test ``/users/{name}`` path"""
    # Fetch user(of latest update) from DB
    query_users = (
        "SELECT "
        "  users.name as username "
        "FROM updates "
        "JOIN users ON updates.user_id = users.id "
        "ORDER BY date_submitted DESC LIMIT 1"
    )
    db_ip = db_container.get_IPv4s()[0]
    conn = psycopg2.connect("dbname=bodhi2 user=postgres host={}".format(db_ip))
    with conn:
        with conn.cursor() as curs:
            curs.execute(query_users)
            username = curs.fetchone()[0]
    conn.close()

    # GET on user with latest update
    with bodhi_container.http_client(port="8080") as c:
        headers = {'Accept': 'text/html'}
        http_response = c.get(f"/users/{username}", headers=headers)

    try:
        assert http_response.ok
        assert f"{username}'s latest updates" in http_response.text
        assert f"{username}'s latest buildroot overrides" in http_response.text
        assert "Feedback received on updates" in http_response.text
        assert "Feedback sent on updates" in http_response.text
    except AssertionError:
        print(http_response)
        print(http_response.text)
        with read_file(bodhi_container, "/httpdir/errorlog") as log:
            print(log.read())
        raise


def test_get_packages_json(bodhi_container, db_container):
    """Test ``/packages`` path"""
    # Fetch package(with latest update) from DB
    query_updates = (
        "SELECT "
        "  id "
        "FROM updates "
        "ORDER BY date_submitted DESC LIMIT 1"
    )
    query_packages = (
        "SELECT "
        "  packages.name, "
        "  packages.type "
        "FROM builds "
        "JOIN packages ON builds.package_id = packages.id "
        "WHERE update_id = %s LIMIT 1"
    )
    db_ip = db_container.get_IPv4s()[0]
    conn = psycopg2.connect("dbname=bodhi2 user=postgres host={}".format(db_ip))
    with conn:
        with conn.cursor() as curs:
            curs.execute(query_updates)
            update_id = curs.fetchone()[0]
            curs.execute(query_packages, (update_id, ))
            row = curs.fetchone()
            package_name = row[0]
            package_type = row[1]
    conn.close()

    # GET on user with latest update
    with bodhi_container.http_client(port="8080") as c:
        http_response = c.get(f"/packages/?name={package_name}")

    expected_json = {
        "packages": [
            {"name": package_name, "requirements": None, "type": package_type}
        ],
        "page": 1,
        "pages": 1,
        "rows_per_page": 20,
        "total": 1,
    }

    try:
        assert http_response.ok
        assert expected_json == http_response.json()
    except AssertionError:
        print(http_response)
        print(http_response.text)
        with read_file(bodhi_container, "/httpdir/errorlog") as log:
            print(log.read())
        raise


def test_get_override_view(bodhi_container, db_container):
    """Test ``/overrides/{nvr}`` path"""
    # Fetch latest overrides from DB
    query_overrides = (
        "SELECT "
        "  builds.nvr as nvr, "
        "  buildroot_overrides.expired_date as expired_date, "
        "  users.name as username "
        "FROM buildroot_overrides "
        "JOIN users ON buildroot_overrides.submitter_id = users.id "
        "JOIN builds ON buildroot_overrides.build_id = builds.id "
        "ORDER BY submission_date DESC LIMIT 1"
    )
    db_ip = db_container.get_IPv4s()[0]
    conn = psycopg2.connect("dbname=bodhi2 user=postgres host={}".format(db_ip))
    with conn:
        with conn.cursor() as curs:
            curs.execute(query_overrides)
            row = curs.fetchone()
            nvr = row[0]
            expired_date = row[1]
            username = row[2]
    conn.close()

    # GET on latest override
    with bodhi_container.http_client(port="8080") as c:
        headers = {'Accept': 'text/html'}
        http_response = c.get(f"/overrides/{nvr}", headers=headers)

    try:
        assert http_response.ok
        assert "Buildroot Override for " in http_response.text
        assert nvr in http_response.text
        assert "Submitted by" in http_response.text
        assert username in http_response.text
        assert "Notes" in http_response.text
        if expired_date is not None:
            assert "Expired" in http_response.text
    except AssertionError:
        print(http_response)
        print(http_response.text)
        with read_file(bodhi_container, "/httpdir/errorlog") as log:
            print(log.read())
        raise


def test_get_overrides_view(bodhi_container, db_container):
    """Test ``/overrides`` path"""
    # Fetch latest overrides from DB
    query_overrides = (
        "SELECT "
        "  builds.nvr as nvr, "
        "  users.name as username "
        "FROM buildroot_overrides "
        "JOIN users ON buildroot_overrides.submitter_id = users.id "
        "JOIN builds ON buildroot_overrides.build_id = builds.id "
        "ORDER BY submission_date DESC LIMIT 20"
    )
    expected_overrides = []
    db_ip = db_container.get_IPv4s()[0]
    conn = psycopg2.connect("dbname=bodhi2 user=postgres host={}".format(db_ip))
    with conn:
        with conn.cursor() as curs:
            curs.execute(query_overrides)
            rows = curs.fetchall()
            for row in rows:
                expected_overrides.append({"nvr": row[0], "username": row[1]})
    conn.close()

    # GET on user with latest update
    with bodhi_container.http_client(port="8080") as c:
        headers = {'Accept': 'text/html'}
        http_response = c.get(f"/overrides", headers=headers)

    try:
        assert http_response.ok
        assert "Overrides" in http_response.text
        for override in expected_overrides:
            assert override["nvr"] in http_response.text
            assert override["username"] in http_response.text
    except AssertionError:
        print(http_response)
        print(http_response.text)
        with read_file(bodhi_container, "/httpdir/errorlog") as log:
            print(log.read())
        raise


def test_get_build_json(bodhi_container, db_container):
    """Test ``/builds/{nvr}`` path"""
    # Fetch builds (of latest update) from DB
    query_updates = (
        "SELECT "
        "  id "
        "FROM updates "
        "ORDER BY date_submitted DESC LIMIT 1"
    )
    query_builds = (
        "SELECT "
        "  nvr, "
        "  release_id, "
        "  signed, "
        "  type, "
        "  epoch "
        "FROM builds "
        "WHERE update_id = %s LIMIT 1"
    )
    db_ip = db_container.get_IPv4s()[0]
    conn = psycopg2.connect("dbname=bodhi2 user=postgres host={}".format(db_ip))
    with conn:
        with conn.cursor() as curs:
            curs.execute(query_updates)
            update_id = curs.fetchone()[0]
            curs.execute(query_builds, (update_id, ))
            nvr, release_id, signed, build_type, epoch = curs.fetchone()
    conn.close()

    # GET on build
    with bodhi_container.http_client(port="8080") as c:
        http_response = c.get(f"/builds/{nvr}")

    build = {
        "nvr": nvr, "release_id": release_id, "signed": signed, "type": build_type, "epoch": epoch,
    }
    try:
        assert http_response.ok
        assert build == http_response.json()
    except AssertionError:
        print(http_response)
        print(http_response.text)
        with read_file(bodhi_container, "/httpdir/errorlog") as log:
            print(log.read())
        raise


def test_get_builds_json(bodhi_container, db_container):
    """Test ``/builds`` path"""
    # Fetch builds (of latest update) from DB
    query_updates = (
        "SELECT "
        "  id, "
        "  alias "
        "FROM updates "
        "ORDER BY date_submitted DESC LIMIT 1"
    )
    query_builds = (
        "SELECT "
        "  nvr, "
        "  release_id, "
        "  signed, "
        "  type, "
        "  epoch "
        "FROM builds "
        "WHERE update_id = %s"
    )
    db_ip = db_container.get_IPv4s()[0]
    conn = psycopg2.connect("dbname=bodhi2 user=postgres host={}".format(db_ip))
    with conn:
        with conn.cursor() as curs:
            curs.execute(query_updates)
            row = curs.fetchone()
            update_id = row[0]
            update_alias = row[1]
            curs.execute(query_builds, (update_id, ))
            builds = []
            for row in curs.fetchall():
                build = {}
                for value, description in zip(row, curs.description):
                    build[description.name] = value
                builds.append(build)
    conn.close()

    # GET on builds of lates update
    with bodhi_container.http_client(port="8080") as c:
        http_response = c.get(f"/builds/?updates={update_alias}")

    default_rows_per_page = 20
    expected_json = {
        "builds": builds,
        "page": 1,
        "pages": int(math.ceil(len(builds) / float(default_rows_per_page))),
        "rows_per_page": default_rows_per_page,
        "total": len(builds),
    }
    try:
        assert http_response.ok
        assert expected_json == http_response.json()
    except AssertionError:
        print(http_response)
        print(http_response.text)
        with read_file(bodhi_container, "/httpdir/errorlog") as log:
            print(log.read())
        raise
