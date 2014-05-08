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
