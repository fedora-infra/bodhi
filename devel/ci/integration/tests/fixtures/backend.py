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

from __future__ import absolute_import, unicode_literals

import logging

import pytest
from conu import DockerBackend


@pytest.fixture(scope="session")
def docker_backend():
    """Fixture yielding a Conu Docker backend.

    Yields:
        conu.DockerBackend: The Docker backend.
    """
    # Redefined to set the scope
    with DockerBackend(logging_level=logging.DEBUG) as backend:
        yield backend


@pytest.fixture(scope="session")
def docker_network(docker_backend):
    """Fixture yielding a Docker network to attach all containers to.

    Args:
        conu.DockerBackend: The Docker backend fixture.

    Yields:
        str: The Docker network ID.
    """
    network = docker_backend.d.create_network("bodhi_test", driver="bridge")
    yield network
    docker_backend.d.remove_network(network["Id"])
