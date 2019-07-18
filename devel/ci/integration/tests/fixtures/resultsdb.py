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

import pytest

from ..utils import make_db_and_user


@pytest.fixture(scope="session")
def resultsdb_container(docker_backend, docker_network, db_container, rabbitmq_container):
    """Fixture preparing and yielding a ResultsDB container.

    Args:
        docker_backend (conu.DockerBackend): The Docker backend (fixture).
        docker_network (dict): The Docker network ID (fixture).
        db_container(conu.DockerContainer): The PostgreSQL container (fixture).
        rabbitmq_container (conu.DockerContainer): The RabbitMQ container
            (fixture).

    Yields:
        conu.DockerContainer: The ResultsDB container.
    """
    # Prepare the database
    make_db_and_user(db_container, "resultsdb")
    # Define the container and start it
    image_name = "bodhi-ci-integration-resultsdb"
    image = docker_backend.ImageClass(image_name)
    container = image.run_via_api()
    container.start()
    docker_backend.d.connect_container_to_network(
        container.get_id(), docker_network["Id"], aliases=["resultsdb", "resultsdb.ci"],
    )
    # Add sample data in the database
    container.execute(["resultsdb", "init_db"])
    # we need to wait for the webserver to start serving
    container.wait_for_port(80, timeout=30)
    yield container
    container.kill()
    container.delete()
