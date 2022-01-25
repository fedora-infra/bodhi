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

import logging
import os
import uuid

import pytest
from conu import DockerBackend, PodmanBackend
from docker import errors

from .conu_ext import DockerNetwork, PodmanNetwork


@pytest.fixture(scope="session")
def docker_backend():
    """Fixture yielding a Conu Docker backend.

    Yields:
        conu.DockerBackend or conu.PodmanBackend: The container backend.
    """
    # Redefined to set the scope
    runtime = os.environ.get("CONTAINER_RUNTIME", "docker")
    if runtime == "podman":
        backend_class = PodmanBackend
        network_class = PodmanNetwork
        # Podman support is still unstable: https://github.com/user-cont/conu/issues/388
        raise ValueError("Running the integration tests with podman is not supported yet.")
    elif runtime == "docker":
        backend_class = DockerBackend
        network_class = DockerNetwork
    else:
        raise ValueError(f"Unsupported container runtime: {runtime}")
    with backend_class(logging_level=logging.DEBUG) as backend:
        backend.NetworkClass = network_class
        yield backend


@pytest.fixture(scope="session")
def docker_network(docker_backend):
    """Fixture yielding a Docker network to attach all containers to.

    Args:
        conu.DockerBackend: The Docker backend fixture.

    Yields:
        dict: The Docker network.
    """
    network = docker_backend.NetworkClass.create(f"bodhi_test-{uuid.uuid4()}", driver="bridge")
    yield network
    try:
        network.remove()
    except errors.APIError as e:
        raise e
