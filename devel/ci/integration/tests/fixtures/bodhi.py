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

from ..utils import make_db_and_user


@pytest.fixture(scope="session")
def bodhi_container(
    docker_backend, docker_network, db_container, resultsdb_container,
    waiverdb_container, greenwave_container, rabbitmq_container,
):
    """Fixture preparing and yielding a Bodhi container to test against.

    Args:
        docker_backend (conu.DockerBackend): The Docker backend (fixture).
        docker_network (dict): The Docker network ID (fixture).
        db_container (conu.DockerContainer): The PostgreSQL container (fixture).
        resultsdb_container (conu.DockerContainer): The ResultsDB container
            (fixture).
        waiverdb_container (conu.DockerContainer): The WaiverDB container
            (fixture).
        greenwave_container (conu.DockerContainer): The Greenwave container
            (fixture).
        rabbitmq_container (conu.DockerContainer): The RabbitMQ container
            (fixture).

    Yields:
        conu.DockerContainer: The Bodhi container.
    """
    # Prepare the database
    make_db_and_user(db_container, "bodhi2", True)
    image = docker_backend.ImageClass(
        os.environ.get("BODHI_INTEGRATION_IMAGE", "bodhi-ci-integration-bodhi")
    )
    container = image.run_via_api()
    container.start()
    docker_backend.d.connect_container_to_network(
        container.get_id(), docker_network["Id"], aliases=["bodhi", "bodhi.ci"],
    )
    # Update the database schema
    container.execute(["alembic-3", "-c", "/bodhi/alembic.ini", "upgrade", "head"])
    # we need to wait for the webserver to start serving
    container.wait_for_port(8080, timeout=30)
    yield container
    container.kill()
    container.delete()
