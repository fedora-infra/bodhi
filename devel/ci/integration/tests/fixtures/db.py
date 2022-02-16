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

import os

import pytest

from .utils import stop_and_delete


@pytest.fixture(scope="session")
def db_container(docker_backend, docker_network):
    """Fixture preparing and yielding a PostgreSQL container.

    This container can be used by other apps to store data.

    Args:
        docker_backend (conu.DockerBackend): The Docker backend (fixture).
        docker_network (dict): The Docker network ID (fixture).

    Yields:
        conu.DockerContainer: The PostgreSQL container.
    """
    image = docker_backend.ImageClass(
        os.environ.get("BODHI_INTEGRATION_POSTGRESQL_IMAGE", "quay.io/bodhi-ci/postgresql"),
        tag="latest"
    )
    run_opts = [
        "--rm",
        "-e", "POSTGRES_HOST_AUTH_METHOD=trust",
        "--name", "database",
        "--network", docker_network.get_id(),
        "--network-alias", "db",
        "--network-alias", "db.ci",
    ]
    container = image.run_via_binary(additional_opts=run_opts)
    container.start()
    print(container.get_metadata())
    container.wait_for_port(5432, timeout=64)
    container.execute(
        ["/usr/bin/pg_isready", "-q", "-t", "64"]
    )
    yield container
    stop_and_delete(container)
