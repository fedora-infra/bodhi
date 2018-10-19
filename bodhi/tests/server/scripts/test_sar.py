# -*- coding: utf-8 -*-
# Copyright © 2018 Sebastian Wojciechowski
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
"""
This module contains tests for the bodhi.server.scripts.sar module.
"""
import os
from datetime import datetime

from click import testing
import mock

from bodhi.server import models
from bodhi.server.scripts import sar
from bodhi.tests.server.base import BaseTestCase


EXPECTED_USER_DATA_OUTPUT = """\
==========> User account data for: guest <==========

email: None
groups: ['packager']
popups: True

----> Comments: <----

Comment no 1:
anonymous: False
karma: 1
karma_critpath: 0
text: wow. amaze.
timestamp: 1984-11-02 00:00:00
update_alias: FEDORA-2018-a3bbe1a8f2
username: guest

----> Updates: <----

Update no 1:
alias: FEDORA-2018-a3bbe1a8f2
autokarma: True
bugs: [12345]
builds: ['bodhi-2.0-1.fc17']
close_bugs: True
date_submitted: 1984-11-02 00:00:00
notes: Useful details!
release_name: F17
require_bugs: False
require_testcases: False
requirements: rpmlint
severity: medium
stable_karma: 3
suggest: unspecified
type: bugfix
unstable_karma: -3
user: guest
"""

EXPECTED_JSON_OUTPUT = (
    '{"guest": {"comments": [{"anonymous": false, "karma": 1, "karma_critpath": 0, "text":'
    ' "wow. amaze.", "timestamp": "1984-11-02 00:00:00", "update_alias": '
    '"FEDORA-2018-a3bbe1a8f2", "username": "guest"}], "email": null, "groups": '
    '["packager"], "name": "guest", "show_popups": true, "updates": [{"alias": '
    '"FEDORA-2018-a3bbe1a8f2", "autokarma": true, "bugs": [12345], "builds": '
    '["bodhi-2.0-1.fc17"], "close_bugs": true, "date_submitted": "1984-11-02 00:00:00", '
    '"notes": "Useful details!", "release_name": "F17", "require_bugs": false, '
    '"require_testcases": false, "requirements": "rpmlint", "severity": "medium", '
    '"stable_karma": 3, "suggest": "unspecified", "type": "bugfix", '
    '"unstable_karma": -3, "user": "guest"}]}}\n'
)


class TestSar(BaseTestCase):
    """This class contains tests for the get_user_data() function."""

    def test_invalid_user(self):
        """Ensure nothing is printed when user is not found and human readable is off."""
        runner = testing.CliRunner()
        r = runner.invoke(sar.get_user_data, ["--username=" + "invalid_user"])

        self.assertEqual(r.exit_code, 0)
        self.assertEqual(r.output, "")

    def test_invalid_user_human_readable(self):
        """Ensure proper info is printed when user is not found and human readable is on."""
        runner = testing.CliRunner()
        r = runner.invoke(sar.get_user_data, ["--username=" + "invalid_user", "--human-readable"])

        self.assertEqual(r.exit_code, 0)
        self.assertEqual(r.output, u"User not found.\n")

    def test_valid_user(self):
        """Ensure json with user data is printed when human readable is off."""
        now = datetime.utcnow()
        now_str = str(now.strftime("%Y-%m-%d %H:%M:%S"))
        comment = self.db.query(models.Comment).all()[0]
        comment.timestamp = now
        self.db.commit()
        expected_output = EXPECTED_JSON_OUTPUT.replace("1984-11-02 00:00:00", now_str, 1)

        runner = testing.CliRunner()
        r = runner.invoke(sar.get_user_data, ["--username=" + "guest"])

        self.assertEqual(r.exit_code, 0)
        self.assertEqual(r.output, expected_output)

    @mock.patch.dict(os.environ, {"SAR_USERNAME": "guest"})
    def test_valid_user_envvar(self):
        """Ensure json with user data is printed when human readable is off."""
        now = datetime.utcnow()
        now_str = str(now.strftime("%Y-%m-%d %H:%M:%S"))
        comment = self.db.query(models.Comment).all()[0]
        comment.timestamp = now
        self.db.commit()
        expected_output = EXPECTED_JSON_OUTPUT.replace("1984-11-02 00:00:00", now_str, 1)

        runner = testing.CliRunner()
        r = runner.invoke(sar.get_user_data)

        self.assertEqual(r.exit_code, 0)
        self.assertEqual(r.output, expected_output)

    def test_valid_user_human_readable(self):
        """Ensure user data are printed when human readable is on."""
        now = datetime.utcnow()
        now_str = str(now.strftime("%Y-%m-%d %H:%M:%S"))
        comment = self.db.query(models.Comment).all()[0]
        comment.timestamp = now
        self.db.commit()
        expected_output = EXPECTED_USER_DATA_OUTPUT.replace("1984-11-02 00:00:00", now_str, 1)

        runner = testing.CliRunner()
        r = runner.invoke(sar.get_user_data, ["--username=" + "guest", "--human-readable"])

        self.assertEqual(r.exit_code, 0)
        # Since py2 and py3 display list with strings in different way,
        # we have to change adjust script output a little bit
        self.assertEqual(r.output.replace("u'", "'"), expected_output)
