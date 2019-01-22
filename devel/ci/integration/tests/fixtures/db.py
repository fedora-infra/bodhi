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
import pytest


@pytest.fixture(scope="session")
def db_container(docker_backend, docker_network):
    """Fixture preparing and yielding a PostgreSQL container.

    This container can be used by other apps to store data.

    Args:
        docker_backend (conu.DockerBackend): The Docker backend (fixture).
        docker_network (str): The Docker network ID (fixture).

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
        container.get_id(), docker_network["Id"], aliases=["db"],
    )
    container.wait_for_port(5432, timeout=-1)
    yield container
    container.kill()
    container.delete()
