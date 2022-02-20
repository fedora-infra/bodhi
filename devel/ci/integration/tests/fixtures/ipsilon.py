# Copyright © 2019 Red Hat, Inc.
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

import conu
import pytest

from .utils import stop_and_delete


@pytest.fixture(scope="session")
def ipsilon_container(
    docker_backend: conu.DockerBackend, docker_network: dict
) -> conu.DockerContainer:
    """
    Fixture preparing and yielding an Ipsilon container.

    Args:
        docker_backend: The Docker backend (fixture).
        docker_network: The Docker network ID (fixture).

    Yields:
        The Ipsilon container.
    """
    # Define the container and start it
    image_name = "bodhi-ci-integration-ipsilon"
    image = docker_backend.ImageClass(image_name)
    run_opts = [
        "--rm",
        "--name", "ipsilon",
        "--network", docker_network.get_id(),
        "--network-alias", "ipsilon",
        "--network-alias", "ipsilon.ci",
        "--network-alias", "id.dev.fedoraproject.org",
    ]
    container = image.run_via_binary(additional_opts=run_opts)
    container.start()
    # we need to wait for the broker to start listening
    container.wait_for_port(80, timeout=30)
    yield container
    stop_and_delete(container)
