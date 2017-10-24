# -*- coding: utf-8 -*-
# Copyright © 2017 Red Hat, Inc.
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

import yaml

from bodhi.tests.server import base


class YAMLLoadTest(unittest.TestCase):
    """Ensure that the JJB template is parseable YAML."""
    def test_failure_comment(self):
        """Ensure that the failure-comment is properly parsed."""
        with open(os.path.join(base.PROJECT_PATH, 'devel/ci/githubprb-project.yml')) as jjb_f:
            jjb = jjb_f.read()

        jjb = yaml.safe_load(jjb)

        self.assertEqual(
            jjb[0]['trigger']['triggers'][0]['github-pull-request']['failure-comment'],
            ('This pull request fails CI testing. Please review the Jenkins job. Hint: You can '
             'search for "JENKIES FAIL" in the console output to quickly find errors.'))
