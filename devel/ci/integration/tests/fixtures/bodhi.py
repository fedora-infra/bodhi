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
from uuid import uuid4

import pytest
from six.moves.configparser import ConfigParser

from ..utils import make_db_and_user, edit_file


@pytest.fixture(scope="session")
def bodhi_container(
    docker_backend, docker_network, db_container, resultsdb_container,
    waiverdb_container, greenwave_container
):
    """Fixture preparing and yielding a Bodhi container to test against.

    Args:
        docker_backend (conu.DockerBackend): The Docker backend (fixture).
        docker_network (str): The Docker network ID (fixture).
        db_container (conu.DockerContainer): The PostgreSQL container (fixture).
        resultsdb_container (conu.DockerContainer): The ResultsDB container
            (fixture).
        waiverdb_container (conu.DockerContainer): The WaiverDB container
            (fixture).
        greenwave_container (conu.DockerContainer): The Greenwave container
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
    config_override = {
        "base_address": "https://bodhi.fedoraproject.org/",
        "sqlalchemy.url": "postgresql://bodhi2@db/bodhi2",
        "pungi.cmd": "/bin/true",
        "dogpile.cache.backend": "dogpile.cache.memory_pickle",
        "legal_link": "https://fedoraproject.org/wiki/Legal:Main",
        "privacy_link": "https://fedoraproject.org/wiki/Legal:PrivacyPolicy",
        "authtkt.secret": uuid4().hex,
        "session.secret": uuid4().hex,
        "query_wiki_test_cases": "True",
        "wiki_url": "https://fedoraproject.org/w/api.php",
        "test_case_base_url": "https://fedoraproject.org/wiki/",
        "resultsdb_url": "http://resultsdb/resultsdb/",
        "test_gating.required": "True",
        "greenwave_api_url": "http://greenwave:8080/api/v1.0",
        "waiverdb_api_url": "http://waiverdb:8080/api/v1.0",
        "default_email_domain": "fedoraproject.org",
        # Only on bodhi-backend
        # "compose_dir": "/mnt/koji/compose/updates/",
        # "compose_stage_dir": "/mnt/koji/compose/updates/",
        "max_concurrent_composes": "3",
        "clean_old_composes": "false",
        "pungi.conf.rpm": "pungi.rpm.conf.j2",
        "pungi.conf.module": "pungi.module.conf.j2",
        "pungi.extracmdline":
            "--notification-script=/usr/bin/pungi-fedmsg-notification "
            "--notification-script=pungi-wait-for-signed-ostree-handler",
        "max_update_length_for_ui": "70",
        "top_testers_timeframe": "900",
        "buildsystem": "koji",
        "fedmenu.url": "https://apps.fedoraproject.org/fedmenu",
        "fedmenu.data_url": "https://apps.fedoraproject.org/js/data.js",
        "acl_system": "pagure",
        "bugtracker": "bugzilla",
        "bz_products": "Fedora,Fedora EPEL",
        "reboot_pkgs": "kernel kernel-smp kernel-PAE glibc hal dbus",
        "critpath.type": "pdc",
        "critpath.num_admin_approvals": "0",
        "fedora_modular.mandatory_days_in_testing": "7",
        "buildroot_overrides.expire_after": "1",
        "pyramid.reload_templates": "false",
        "pyramid.debug_authorization": "false",
        "pyramid.debug_notfound": "false",
        "pyramid.debug_routematch": "false",
        "authtkt.secure": "true",
        "authtkt.timeout": "1209600",
        # Building a cache for every test takes a lot of time, so let's configure the Bodhi server
        # not to warm the cache.
        "warm_cache_on_start": "false",
    }
    with edit_file(container, "/etc/bodhi/production.ini") as config_path:
        config = ConfigParser()
        config.read(config_path)
        for key, value in config_override.items():
            config.set("app:main", key, value)

        with open(config_path, "w") as config_file:
            config.write(config_file)

    container.start()
    docker_backend.d.connect_container_to_network(
        container.get_id(), docker_network["Id"], aliases=["bodhi"],
    )
    # Update the database schema
    container.execute(["alembic-3", "-c", "/bodhi/alembic.ini", "upgrade", "head"])
    # we need to wait for the webserver to start serving
    container.wait_for_port(8080, timeout=30)
    yield container
    container.kill()
    container.delete()
