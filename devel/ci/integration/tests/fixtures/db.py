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

import docker.errors
import pytest


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
        os.environ.get("BODHI_INTEGRATION_POSTGRESQL_IMAGE", "postgres"),
        tag="latest"
    )
    container = image.run_via_api()
    container.start()
    docker_backend.d.connect_container_to_network(
        container.get_id(), docker_network["Id"], aliases=["db", "db.ci"],
    )
    container.wait_for_port(5432, timeout=64)
    container.execute(
        ["/usr/bin/pg_isready", "-q", "-t", "64"]
    )
    yield container
    try:
        container.kill()
    except docker.errors.APIError:
        # If the container isn't running, this will get raised. It's fine, we wanted the container
        # stopped and it is, so pass.
        pass
    container.delete()
