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

import time

import conu
import pytest


@pytest.fixture(scope="session")
def rabbitmq_container(
    docker_backend: conu.DockerBackend, docker_network: str
) -> conu.DockerContainer:
    """
    Fixture preparing and yielding a RabbitMQ container.

    Args:
        docker_backend: The Docker backend (fixture).
        docker_network: The Docker network ID (fixture).

    Yields:
        The RabbitMQ container.
    """
    # Define the container and start it
    image_name = "bodhi-ci-integration-rabbitmq"
    image = docker_backend.ImageClass(image_name)
    container = image.run_via_api()
    container.start()
    docker_backend.d.connect_container_to_network(
        container.get_id(), docker_network["Id"], aliases=["rabbitmq"]
    )
    # we need to wait for the broker to start listening
    container.wait_for_port(5672, timeout=30)
    # wait until the embedded consumer is connected
    for i in range(15):
        if _consumer_is_connected(container, "dumper"):
            break
        print("Consumer not connected yet, retrying")
        time.sleep(1)
    else:
        raise RuntimeError("The Fedora Messaging consumer did not connect in time")
    yield container
    container.kill()
    container.delete()


def _consumer_is_connected(container: conu.DockerContainer, queue_name: str) -> bool:
    """Returns whether a consumer is connected to the provided queue name."""
    container.wait_for_port(15672, timeout=30)
    with container.http_client(port="15672") as client:
        client.auth = ('guest', 'guest')
        response = client.get("/api/consumers/")
        consumers = response.json()
    consumed_queues = [c["queue"]["name"] for c in consumers]
    return queue_name in consumed_queues
