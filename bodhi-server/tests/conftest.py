# Copyright © 2007-2019 Red Hat, Inc.
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
"""Pytest configuration."""

from unittest import mock
import json
import os
import tempfile

import pytest


# Set BODHI_CONFIG to our testing ini file.
@pytest.fixture(autouse=True)
def mock_settings_env_vars():
    with mock.patch.dict(os.environ, {"BODHI_CONFIG": os.path.join(os.path.dirname(__file__),
                                                                   "testing.ini")}):
        yield


@pytest.fixture(scope="session")
def critpath_json_config(request):
    """
    Critpath JSON configuration fixture.

    Set up one valid (f36) and one invalid (f35) configuration file
    for critpath.type=json and yield the path, file names, and sample
    data.
    """
    tempdir = tempfile.TemporaryDirectory(suffix='bodhi')
    f35file = os.path.join(tempdir.name, 'f35.json')
    with open(f35file, 'w', encoding='utf-8') as f35filefh:
        f35filefh.write("This is not JSON")
    f36file = os.path.join(tempdir.name, 'f36.json')
    testdata = {
        'rpm': {
            'core': [
                'ModemManager-glib',
                'NetworkManager',
                'TurboGears',
            ],
            'critical-path-apps': [
                'abattis-cantarell-fonts',
                'adobe-source-code-pro-fonts',
            ]
        }
    }
    with open(f36file, 'w', encoding='utf-8') as f36filefh:
        json.dump(testdata, f36filefh)
    yield (tempdir.name, testdata)
    tempdir.cleanup()
