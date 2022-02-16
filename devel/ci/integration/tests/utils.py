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

import json
import os
import shutil
import tempfile
from contextlib import contextmanager

from conu import ConuException
from fedora_messaging import message
from munch import Munch


@contextmanager
def read_file(container, path, binary=False):
    """Read a file in a container.

    Args:
        container (conu.DockerContainer): The container where the file is.
        path (str): The file path in the container.
        binary (bool): Whether the file should be opened in binary mode.

    Yields:
        file: The opened file object.
    """
    with tempfile.TemporaryDirectory() as tempdir:
        destfile = os.path.join(tempdir, "file")
        container.copy_from(path, destfile)
        mode = "rb" if binary else "r"
        with open(destfile, mode) as fh:
            yield fh


@contextmanager
def edit_file(container, path):
    """Edit a file in a container.

    Args:
        container (conu.DockerContainer): The container where the file is.
        path (str): The file path in the container.

    Yields:
        str: A path to a local file that will be synced back to the container.
    """
    with tempfile.TemporaryDirectory() as tempdir:
        destfile = os.path.join(tempdir, "file")
        container.copy_from(path, destfile)
        yield destfile
        container.copy_to(destfile, path)


@contextmanager
def replace_file(container, path, contents):
    """Temporarily replace a file with the provided content in a container.

    Args:
        container (conu.DockerContainer): The container where the file is.
        path (str): The file path in the container.
        contents (str): The temporary content for the file.

    Yields:
        str: A path to a local file that will be synced back to the container.
    """
    with tempfile.TemporaryDirectory() as tempdir:
        backupfile = os.path.join(tempdir, "original")
        container.copy_from(path, backupfile)
        newfile = os.path.join(tempdir, "replacement")
        with open(newfile, "w") as f:
            f.write(contents)
        shutil.copymode(backupfile, newfile)
        container.copy_to(newfile, path)
        try:
            yield
        finally:
            container.copy_to(backupfile, path)


def get_sent_messages(rabbitmq_container):
    """Read a file in a container.

    Args:
        rabbitmq_container (conu.DockerContainer): The RabbitMQ container.

    Returns:
        list(Message): A list of Message instance that were sent over the broker.
    """
    with tempfile.TemporaryDirectory() as tempdir:
        destfile = os.path.join(tempdir, "file")
        rabbitmq_container.copy_from("/var/log/fedora-messaging/messages.log", destfile)
        with open(destfile, "r") as fh:
            serialized_messages = fh.read().replace("\n", ",")
    serialized_messages = "[%s]" % serialized_messages[:-1]
    return message.loads(serialized_messages)


def get_task_results(container):
    """Read a file in a container.

    Args:
        container (conu.DockerContainer): The container where the file is.
        binary (bool): Whether the file should be opened in binary mode.

    Returns:
        file: The opened file object.
    """
    result_path = "/srv/celery-results"
    results = []
    with tempfile.TemporaryDirectory() as tempdir:
        container.copy_from(result_path, tempdir)
        for root, dirs, files in os.walk(tempdir):
            for filename in files:
                with open(os.path.join(root, filename)) as fh:
                    result = json.load(fh)
                results.append(result)
    return results


def run_cli(bodhi_container, args, **kwargs):
    """Run the Bodhi CLI in the Bodhi container

    Args:
        bodhi_container (conu.DockerContainer): The Bodhi container to use.
        args (list): The CLI arguments
        kwargs (dict): The kwargs to use for the ``DockerContainer.execute()``
            method.
    Returns:
        Munch: Execution result as an object with an ``exit_code`` property
            (``int``) and an ``output`` property (``str``).
    """
    if "exec_create_kwargs" not in kwargs:
        kwargs["exec_create_kwargs"] = {}
    if "environment" not in kwargs["exec_create_kwargs"]:
        kwargs["exec_create_kwargs"]["environment"] = {}
    kwargs["exec_create_kwargs"]["environment"]["PYTHONWARNINGS"] = "ignore"
    cmd = ["bodhi"] + args + [
        "--url", "http://localhost:8080",
        "--id-provider", "https://id.dev.fedoraproject.org/openidc",
    ]
    try:
        output = bodhi_container.execute(cmd, **kwargs)
    except ConuException as e:
        return Munch(exit_code=1, output=str(e))
    return Munch(exit_code=0, output="".join(line.decode("utf-8") for line in output))
