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

import os

import docker
import requests


def make_db_and_user(db_container, name, use_dump=False):
    """Create a database and a user in PostgreSQL.

    Args:
        db_container (conu.DockerContainer): The PostgreSQL container.
        name (str): the database and use names to create.
        dump_url (str): the URL of the database dump to preload the new
            database with.
    """
    # Prepare the database
    db_container.execute(
        ["/usr/bin/psql", "-q", "-U", "postgres", "-c", "CREATE USER {} CREATEDB;".format(name)]
    )
    db_container.execute(
        [
            "/usr/bin/psql", "-q", "-U", "postgres", "-c",
            (
                "CREATE DATABASE {} WITH TEMPLATE = template0 ENCODING = 'UTF8' "
                "LC_COLLATE = 'en_US.UTF-8' LC_CTYPE = 'en_US.UTF-8';"
            ).format(name),
        ]
    )
    if use_dump:
        db_dump = os.path.join("devel", "ci", "integration", "dumps", f"{name}.dump.xz")
        if not os.path.exists(db_dump):
            # Download it
            url = f"https://infrastructure.fedoraproject.org/infra/db-dumps/{name}.dump.xz"
            response = requests.get(url, stream=True)
            response.raise_for_status()
            with open(db_dump, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        db_container.copy_to(db_dump, "/tmp/database.dump.xz")
        db_container.execute(
            ["sh", "-c", f"xzcat /tmp/database.dump.xz | /usr/bin/psql -q -U {name}"]
        )
        db_container.execute(["rm", "/tmp/database.dump.xz"])


def stop_and_delete(container):
    try:
        container.kill()
    except docker.errors.APIError as e:
        if e.response.status_code == 404:
            return
        raise
    try:
        container.delete()
    except docker.errors.APIError as e:
        expected = f"removal of container {container.get_id()} is already in progress"
        if e.response.status_code == 404:
            return
        elif e.response.status_code == 409 and e.explanation == expected:
            return
        raise
