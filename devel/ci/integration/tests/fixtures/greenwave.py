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

import docker.errors
import pytest

from ..utils import make_db_and_user


@pytest.fixture(scope="session")
def greenwave_container(docker_backend, docker_network, db_container):
    """Fixture preparing and yielding a Greenwave container.

    Args:
        docker_backend (conu.DockerBackend): The Docker backend (fixture).
        docker_network (str): The Docker network ID (fixture).
        db_container(conu.DockerContainer): The PostgreSQL container (fixture).

    Yields:
        conu.DockerContainer: The Greenwave container.
    """
    # Prepare the database
    make_db_and_user(db_container, "greenwave")
    # Define the container and start it
    image_name = "bodhi-ci-integration-greenwave"
    image = docker_backend.ImageClass(image_name)
    container = image.run_via_api()
    container.start()
    docker_backend.d.connect_container_to_network(
        container.get_id(), docker_network["Id"], aliases=["greenwave"],
    )
    # we need to wait for the webserver to start serving
    container.wait_for_port(8080, timeout=-1)
    yield container
    try:
        container.kill()
    except docker.errors.APIError:
        # Sometimes the container is not running, so this will raise an Exception. Since our goal
        # is that the container is not running, this is OK.
        pass
    container.delete()
