# -*- coding: utf-8 -*-
# Copyright ® 2017 Red Hat, Inc.
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
"""This module contains tests for the bodhi.server.scripts.babysit_ci module."""

from click import testing

from bodhi.server import models
from bodhi.server.scripts import babysit_ci
from bodhi.tests.server.base import BaseTestCase


class TestBabysit(BaseTestCase):
    """This class contains tests for the babysit() function."""
    def test_build_with_scm_url(self):
        """Assert correct behavior when a Build already has an scm_url."""
        runner = testing.CliRunner()
        b = models.Build.query.filter(models.Build.nvr == u'bodhi-2.0-1.fc17').one()
        # We need to make it so b is in a non-final CI status
        b.ci_status = models.CiStatus.running
        b.scm_url = u'some_url_that_isnt_from_devbuildsys'
        self.db.commit()

        result = runner.invoke(babysit_ci.babysit, [])

        self.assertEqual(result.exit_code, 0)
        # The Build from the test case setup should not have the scm_url from the
        # DevBuildsys.getTaskRequest() call, since we gave it one.
        b = models.Build.query.filter(models.Build.nvr == u'bodhi-2.0-1.fc17').one()
        self.assertEqual(b.scm_url, 'some_url_that_isnt_from_devbuildsys')

    def test_build_without_scm_url(self):
        """Assert correct behavior when a Build lacks an scm_url."""
        runner = testing.CliRunner()
        b = models.Build.query.filter(models.Build.nvr == u'bodhi-2.0-1.fc17').one()
        # We need to make it so b is in a non-final CI status
        b.ci_status = models.CiStatus.running
        self.db.commit()

        result = runner.invoke(babysit_ci.babysit, [])

        self.assertEqual(result.exit_code, 0)
        # The Build from the test case setup should have the scm_url from the
        # DevBuildsys.getTaskRequest() call.
        b = models.Build.query.filter(models.Build.nvr == u'bodhi-2.0-1.fc17').one()
        self.assertEqual(
            b.scm_url,
            'git://pkgs.fedoraproject.org/rpms/bodhi?#2e994ca8b3296e62e8b0aadee1c5c0649559625a')
