# -*- coding: utf-8 -*-
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
"""This module contains tests for the CI yaml file."""
import os
import unittest

from bodhi.server import util
from bodhi.tests.server import base


JJB_TEMPLATE_PATH = os.path.join(base.PROJECT_PATH, 'devel/ci/githubprb-project.yml')


class YAMLLoadTest(unittest.TestCase):
    """Ensure that the JJB template is valid."""

    def test_jenkins_jobs(self):
        """Make sure jenkins-jobs test likes our JJB template."""
        cmd = ['jenkins-jobs', 'test', JJB_TEMPLATE_PATH]

        out, err, code = util.cmd(cmd)

        message = 'Hint: Try running {}'.format(' '.join(cmd))
        self.assertEqual(code, 0, message)
