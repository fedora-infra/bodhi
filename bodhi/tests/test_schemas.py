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

import unittest
import bodhi.schemas


class TestSchemas(unittest.TestCase):

    def test_schema_unflattening_for_comments(self):
        expected = {
            'email': 'w@t.com',
            'text': 'this is an update comment',
            'karma': -1,
            'karma_critpath': 1,
            'bug_feedback': [{'bug_id': 1, 'karma': 1}],
            'testcase_feedback': [{'testcase_name': "wat", 'karma': -1}],
        }
        flat_structure = {
            'email': 'w@t.com',
            'text': 'this is an update comment',
            'karma': -1,
            'karma_critpath': 1,
            'bug_feedback.0.bug_id': 1,
            'bug_feedback.0.karma': 1,
            'testcase_feedback.0.testcase_name': 'wat',
            'testcase_feedback.0.karma': -1,
        }
        schema = bodhi.schemas.SaveCommentSchema()
        nested_structure = schema.unflatten(flat_structure)
        self.assertEquals(nested_structure, expected)
