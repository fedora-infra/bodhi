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

import conu.utils.probes
import pytest

from .utils import stop_and_delete


@pytest.fixture(scope="session")
def valkey_container(docker_backend, docker_network):
    """Fixture preparing and yielding a Valkey container.

    Args:
        docker_backend (conu.DockerBackend): The Docker backend (fixture).
        docker_network (str): The Docker network ID (fixture).

    Yields:
        conu.DockerContainer: The Valkey container.
    """
    # Define the container and start it
    image_name = "bodhi-ci-integration-valkey"
    image = docker_backend.ImageClass(image_name)
    run_opts = [
        "--rm",
        "--name", "valkey",
        "--network", docker_network.get_id(),
        "--network-alias", "valkey",
        "--network-alias", "valkey.ci",
    ]
    container = image.run_via_binary(additional_opts=run_opts)
    container.start()
    try:
        # we need to wait for the server to start serving
        container.wait_for_port(6379, timeout=30)
    except conu.utils.probes.ProbeTimeout:
        for log in container.logs():
            # Let's print out the logs from the container in the hopes that they will help us debug
            # why it isn't starting.
            print(log)
        raise
    yield container
    stop_and_delete(container)
