"""Some extensions for conu.

This should be sent upstream.
"""

import json

from conu.backend.docker.client import get_client
from conu.utils import run_cmd


class Network:
    """A generic Network representation. This is an abstract class."""

    def __init__(self, identifier):
        self._id = identifier

    def get_id(self):
        """Get the network identifier."""
        raise NotImplementedError("get_id method is not implemented")

    def connect_container(self, container, aliases=None):
        """Connect a container to this network.

        Args:
            container (conu.apidefs.container.Container): The container to connect.
            aliases ([str], optional): The list of DNS aliases for this container.
        """
        raise NotImplementedError("connect_container method is not implemented")

    def disconnect_container(self, container, force=False):
        """Disconnect a container from this network

        Args:
            container (conu.apidefs.container.Container): The container to disconnect.
            force (bool, optional): Forcibly disconnect. Defaults to False.
        """
        raise NotImplementedError("disconnect_container method is not implemented")

    def remove(self):
        """Remove this network."""
        raise NotImplementedError("remove method is not implemented")

    @classmethod
    def create(cls, name, driver):
        """Create the network.

        Args:
            name (str): The name of the network
            driver (str): The driver to use.

        Returns:
            Network: The created Network instance.
        """
        raise NotImplementedError("create method is not implemented")


class DockerNetwork(Network):
    """The docker implementation of a network."""
    def __init__(self, identifier):
        super().__init__(identifier)
        self.d = get_client()

    def get_id(self):
        return self._id

    def connect_container(self, container, aliases=None):
        return self.d.connect_container_to_network(
            container.get_id(), self.get_id(), aliases=aliases,
        )

    def disconnect_container(self, container, force=False):
        return self.d.disconnect_container_from_network(
            container.get_id(), self.get_id(), force=force,
        )

    def remove(self):
        self.d.remove_network(self.get_id())

    @classmethod
    def create(cls, name, driver):
        client = get_client()
        response = client.create_network(name, driver=driver)
        return cls(response["Id"])


class PodmanNetwork(Network):
    """The podman implementation of a network."""
    def __init__(self, identifier):
        super().__init__(identifier)

    def get_id(self):
        return self._id

    def connect_container(self, container, aliases=None):
        cmdline = ['podman', 'network', 'connect']
        for alias in aliases or []:
            cmdline.extend(["--alias", alias])
        cmdline.extend([self.get_id(), container.get_id()])
        output = run_cmd(cmdline, return_output=True, log_output=True)
        print("connect:", output)  # XXX
        return json.loads(output)[0]

    def disconnect_container(self, container, force=False):
        cmdline = ['podman', 'network', 'disconnect']
        if force:
            cmdline.append("--force")
        cmdline.extend([self.get_id(), container.get_id()])
        output = run_cmd(cmdline, return_output=True, log_output=True)
        print("diconnect:", output)  # XXX
        return json.loads(output)[0]

    def remove(self):
        cmdline = ['podman', 'network', 'rm', self.get_id()]
        run_cmd(cmdline, return_output=True, log_output=True)

    @classmethod
    def create(cls, name, driver):
        cmdline = ['podman', 'network', 'create', "--driver", driver, name]
        run_cmd(cmdline, return_output=True, log_output=True)
        return cls(name)
