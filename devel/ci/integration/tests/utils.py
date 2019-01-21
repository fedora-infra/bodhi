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
import shutil
import subprocess
import tempfile
from contextlib import contextmanager

import requests


def get_db_dump(url):
    """Get an app's database dump in the Fedora infrastructure.

    The database dump will be uncompressed and store locally. If the local file
    exists, it will used and not re-downloaded.

    Args:
        url (str): The URL to download the dump from.

    Returns:
        str: The local file path of the dump.
    """
    filename = os.path.basename(url)
    if filename.endswith(".xz"):
        filename = filename[:-3]
    filepath = os.path.join("devel", "ci", "integration", "dumps", filename)
    if os.path.exists(filepath):
        return filepath
    response = requests.get(url)
    assert response.ok
    if url.endswith(".xz"):
        compressed_filepath = "{}.xz".format(filepath)
        with open(compressed_filepath, "wb") as fd:
            for chunk in response.iter_content(chunk_size=128):
                fd.write(chunk)
        subprocess.check_call(["xz", "-d", compressed_filepath])
    return filepath


def make_db_and_user(db_container, name, dump_url=None):
    """Create a database and a user in PostgreSQL.

    Args:
        db_container (conu.DockerContainer): The PostgreSQL container.
        name (str): the database and use names to create.
        dump_url (str): the URL of the database dump to preload the new
            database with.
    """
    # Prepare the database
    db_container.execute(
        ["/usr/bin/psql", "-q", "-U", "postgres", "-c", "CREATE USER {} CREATEDB;".format(name)]
    )
    db_container.execute(
        [
            "/usr/bin/psql", "-q", "-U", "postgres", "-c",
            (
                "CREATE DATABASE {} WITH TEMPLATE = template0 ENCODING = 'UTF8' "
                "LC_COLLATE = 'en_US.UTF-8' LC_CTYPE = 'en_US.UTF-8';"
            ).format(name),
        ]
    )
    if dump_url:
        db_dump = get_db_dump(dump_url)
        db_container.copy_to(db_dump, "/tmp/database.dump")
        db_container.execute(["/usr/bin/psql", "-q", "-U", name, "-f", "/tmp/database.dump"])
        db_container.execute(["rm", "/tmp/database.dump"])


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
