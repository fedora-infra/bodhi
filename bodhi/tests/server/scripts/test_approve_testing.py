# Copyright © 2016-2019 Red Hat, Inc. and others.
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
This module contains tests for the bodhi.server.scripts.approve_testing module.
"""
from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import call, patch

from fedora_messaging import api, testing as fml_testing

from bodhi.server.config import config
from bodhi.server import models
from bodhi.server.scripts import approve_testing
from bodhi.tests.server.base import BaseTestCase


class TestMain(BaseTestCase):
    """
    This class contains tests for the main() function.
    """
    def test_autokarma_update_meeting_time_requirements_gets_one_comment(self):
        """
        Ensure that an update that meets the required time in testing gets only one comment from
        Bodhi to that effect, even on subsequent runs of main().
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = True
        update.request = None
        update.stable_karma = 10
        update.status = models.UpdateStatus.testing
        update.date_testing = datetime.utcnow() - timedelta(days=7)
        with fml_testing.mock_sends():
            self.db.commit()

        with patch('bodhi.server.scripts.approve_testing.initialize_db'):
            with patch('bodhi.server.scripts.approve_testing.get_appsettings', return_value=''):
                with fml_testing.mock_sends(api.Message):
                    approve_testing.main(['nosetests', 'some_config.ini'])

                # Now we will run main() again, but this time we expect Bodhi not to add any
                # further comments.
                with fml_testing.mock_sends():
                    approve_testing.main(['nosetests', 'some_config.ini'])

        bodhi = self.db.query(models.User).filter_by(name=u'bodhi').one()
        comment_q = self.db.query(models.Comment).filter_by(update_id=update.id, user_id=bodhi.id)
        self.assertEqual(comment_q.count(), 1)
        self.assertEqual(
            comment_q[0].text,
            config.get('testing_approval_msg') % update.release.mandatory_days_in_testing)

    # Set the release's mandatory days in testing to 0 to set up the condition for this test.
    @patch.dict(config, [('fedora.mandatory_days_in_testing', 0)])
    def test_autokarma_update_without_mandatory_days_in_testing(self):
        """
        If the Update's release doesn't have a mandatory days in testing, main() should ignore it
        (and should not comment on the update at all, even if it does reach karma levels.)
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = True
        update.request = None
        update.status = models.UpdateStatus.testing
        update.date_testing = datetime.utcnow() - timedelta(days=7)
        # Let's delete all the comments to make our assertion at the end of this simpler.
        for c in update.comments:
            self.db.delete(c)
        with fml_testing.mock_sends():
            self.db.commit()

        with patch('bodhi.server.scripts.approve_testing.initialize_db'):
            with patch('bodhi.server.scripts.approve_testing.get_appsettings', return_value=''):
                with fml_testing.mock_sends():
                    approve_testing.main(['nosetests', 'some_config.ini'])

        # The bodhi user shouldn't exist, since it shouldn't have made any comments
        self.assertEqual(self.db.query(models.User).filter_by(name=u'bodhi').count(), 0)
        self.assertEqual(self.db.query(models.Comment).count(), 0)

    def test_autokarma_update_not_meeting_testing_requirments(self):
        """
        If an autokarma update has not met the testing requirements, bodhi should not comment on the
        update.
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = True
        update.request = None
        update.status = models.UpdateStatus.testing
        # 6 days isn't enough time to meet the testing requirements.
        update.date_testing = datetime.utcnow() - timedelta(days=6)
        # Let's delete all the comments to make our assertion at the end of this simpler.
        for c in update.comments:
            self.db.delete(c)
        with fml_testing.mock_sends():
            self.db.commit()

        with patch('bodhi.server.scripts.approve_testing.initialize_db'):
            with patch('bodhi.server.scripts.approve_testing.get_appsettings', return_value=''):
                with fml_testing.mock_sends():
                    approve_testing.main(['nosetests', 'some_config.ini'])

        # The bodhi user shouldn't exist, since it shouldn't have made any comments
        self.assertEqual(self.db.query(models.User).filter_by(name=u'bodhi').count(), 0)
        self.assertEqual(self.db.query(models.Comment).count(), 0)

    @patch('bodhi.server.models.Update.comment', side_effect=IOError('The DB died lol'))
    @patch('bodhi.server.scripts.approve_testing.Session.remove')
    @patch('bodhi.server.scripts.approve_testing.sys.exit')
    @patch('sys.stdout', new_callable=StringIO)
    def test_exception_handler(self, stdout, exit, remove, comment):
        """The Exception handler prints the Exception, rolls back and closes the db, and exits."""
        update = self.db.query(models.Update).all()[0]
        update.date_testing = datetime.utcnow() - timedelta(days=15)
        update.request = None
        update.status = models.UpdateStatus.testing
        self.db.flush()

        with patch('bodhi.server.scripts.approve_testing.initialize_db'):
            with patch('bodhi.server.scripts.approve_testing.get_appsettings', return_value=''):
                with patch.object(self.db, 'commit'):
                    with patch.object(self.db, 'rollback'):
                        approve_testing.main(['nosetests', 'some_config.ini'])

                        self.assertEqual(self.db.commit.call_count, 0)
                        self.db.rollback.assert_called_once_with()

        exit.assert_called_once_with(1)
        comment.assert_called_once_with(
            self.db,
            ('This update has reached 7 days in testing and can be pushed to stable now if the '
             'maintainer wishes'),
            author=u'bodhi')
        self.assertEqual(stdout.getvalue(),
                         f'{update.alias} now meets testing requirements\nThe DB died lol\n')
        remove.assert_called_once_with()

    @patch('bodhi.server.models.Update.comment', side_effect=[None, IOError('The DB died lol')])
    @patch('bodhi.server.scripts.approve_testing.Session.remove')
    @patch('bodhi.server.scripts.approve_testing.sys.exit')
    @patch('sys.stdout', new_callable=StringIO)
    def test_exception_handler_on_the_second_update(self, stdout, exit, remove, comment):
        """
        Ensure, that when the Exception is raised, all previous transactions are commited,
        the Exception handler prints the Exception, rolls back and closes the db, and exits.
        """
        update = self.db.query(models.Update).all()[0]
        update.date_testing = datetime.utcnow() - timedelta(days=15)
        update.request = None
        update.status = models.UpdateStatus.testing

        update2 = self.create_update([u'bodhi2-2.0-1.fc17'])
        update2.date_testing = datetime.utcnow() - timedelta(days=15)
        update2.request = None
        update2.status = models.UpdateStatus.testing
        self.db.flush()

        with patch('bodhi.server.scripts.approve_testing.initialize_db'):
            with patch('bodhi.server.scripts.approve_testing.get_appsettings', return_value=''):
                with patch.object(self.db, 'commit'):
                    with patch.object(self.db, 'rollback'):
                        approve_testing.main(['nosetests', 'some_config.ini'])

                        self.assertEqual(self.db.commit.call_count, 1)
                        self.db.rollback.assert_called_once_with()

        exit.assert_called_once_with(1)
        comment_expected_call = call(
            self.db,
            ('This update has reached 7 days in testing and can be pushed to stable now if the '
             'maintainer wishes'),
            author=u'bodhi',
        )
        self.assertEqual(comment.call_args_list, [comment_expected_call, comment_expected_call])
        self.assertEqual(stdout.getvalue(),
                         (f'{update2.alias} now meets testing requirements\n'
                          f'{update.alias} now meets testing requirements\nThe DB died lol\n'))
        remove.assert_called_once_with()

    def test_non_autokarma_critpath_update_meeting_karma_requirements_gets_one_comment(self):
        """
        Ensure that a non-autokarma critical path update that meets the required karma threshold
        and required time in testing gets only one comment from Bodhi to that effect, even on
        subsequent runs of main(). There was an issue[0] where Bodhi wasn't correctly detecting when
        it should add these comments, and with detecting that it has already commented on
        critical path updates, and would repeatedly comment that these updates could be pushed.
        This test ensures that issue stays fixed.

        [0] https://github.com/fedora-infra/bodhi/issues/1009
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = False
        # Make this update a critpath update to force meets_testing_requirements into a different
        # code path.
        update.critpath = True
        # It's been in testing long enough to get the comment from bodhi that it can be pushed.
        update.date_testing = datetime.utcnow() - timedelta(days=15)
        update.request = None
        update.stable_karma = 1
        update.status = models.UpdateStatus.testing
        update.comment(self.db, u'testing', author=u'hunter2', karma=1)
        with fml_testing.mock_sends(api.Message):
            self.db.commit()

        with patch('bodhi.server.scripts.approve_testing.initialize_db'):
            with patch('bodhi.server.scripts.approve_testing.get_appsettings', return_value=''):
                approve_testing.main(['nosetests', 'some_config.ini'])

                # Now we will run main() again, but this time we expect Bodhi not to add any
                # further comments.
                approve_testing.main(['nosetests', 'some_config.ini'])

        bodhi = self.db.query(models.User).filter_by(name=u'bodhi').one()
        comment_q = self.db.query(models.Comment).filter_by(update_id=update.id, user_id=bodhi.id)
        self.assertEqual(comment_q.count(), 1)
        self.assertEqual(comment_q[0].text, config.get('testing_approval_msg_based_on_karma'))

    def test_non_autokarma_critpath_update_not_meeting_time_requirements_gets_no_comment(self):
        """
        Ensure that a non-autokarma critical path update that does not meet the required time in
        testing does not get any comment from bodhi saying it can be pushed to stable.
        There was an issue[0] where Bodhi was incorrectly detecting that the update could be pushed
        and was commenting to that effect. This test ensures that issue stays fixed.

        [0] https://github.com/fedora-infra/bodhi/issues/1009
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = False
        # Make this update a critpath update to force meets_testing_requirements into a different
        # code path.
        update.critpath = True
        update.request = None
        update.stable_karma = 1
        update.status = models.UpdateStatus.testing
        update.comment(self.db, u'testing', author=u'hunter2', karma=1)
        with fml_testing.mock_sends(api.Message):
            self.db.commit()

        with patch('bodhi.server.scripts.approve_testing.initialize_db'):
            with patch('bodhi.server.scripts.approve_testing.get_appsettings', return_value=''):
                approve_testing.main(['nosetests', 'some_config.ini'])

                # Now we will run main() again, but this time we expect Bodhi not to add any
                # further comments.
                approve_testing.main(['nosetests', 'some_config.ini'])

        # The bodhi user shouldn't exist, since it shouldn't have made any comments
        self.assertEqual(self.db.query(models.User).filter_by(name=u'bodhi').count(), 0)
        # There are three comments, but none from the non-existing bodhi user.
        self.assertEqual(self.db.query(models.Comment).count(), 3)
        usernames = [
            c.user.name
            for c in self.db.query(models.Comment).order_by(models.Comment.timestamp).all()]
        self.assertEqual(usernames, [u'guest', u'anonymous', u'hunter2'])

    def test_non_autokarma_update_meeting_karma_requirements_gets_one_comment(self):
        """
        Ensure that a non-autokarma update that meets the required karma threshold gets only one
        comment from Bodhi to that effect, even on subsequent runs of main(). There was an issue[0]
        where Bodhi wasn't correctly detecting that it has already commented on updates, and would
        repeatedly comment that non-autokarma updates could be pushed. This test ensures that issue
        stays fixed.

        [0] https://github.com/fedora-infra/bodhi/issues/1009
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = False
        update.request = None
        update.stable_karma = 1
        update.status = models.UpdateStatus.testing
        update.comment(self.db, u'testing', author=u'hunter2', karma=1)
        with fml_testing.mock_sends(api.Message):
            self.db.commit()

        with patch('bodhi.server.scripts.approve_testing.initialize_db'):
            with patch('bodhi.server.scripts.approve_testing.get_appsettings', return_value=''):
                approve_testing.main(['nosetests', 'some_config.ini'])

                # Now we will run main() again, but this time we expect Bodhi not to add any
                # further comments.
                approve_testing.main(['nosetests', 'some_config.ini'])

        bodhi = self.db.query(models.User).filter_by(name=u'bodhi').one()
        comment_q = self.db.query(models.Comment).filter_by(update_id=update.id, user_id=bodhi.id)
        self.assertEqual(comment_q.count(), 1)
        self.assertEqual(comment_q[0].text, config.get('testing_approval_msg_based_on_karma'))

    def test_non_autokarma_critpath_update_meeting_time_requirements_gets_one_comment(self):
        """
        Ensure that a critpath update that meets the required time in testing (14 days) gets a
        comment from Bodhi indicating that the update has met the required time in testing.
        There was an issue[0] where Bodhi was indicating that the update had been in testing for
        only 7 days, when the update had been in testing for 14 days.

        [0] https://github.com/fedora-infra/bodhi/issues/1361
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = False
        update.request = None
        update.stable_karma = 10
        update.critpath = True
        update.status = models.UpdateStatus.testing
        update.date_testing = datetime.utcnow() - timedelta(days=14)
        with fml_testing.mock_sends():
            self.db.commit()

        with patch('bodhi.server.scripts.approve_testing.initialize_db'):
            with patch('bodhi.server.scripts.approve_testing.get_appsettings', return_value=''):
                with fml_testing.mock_sends(api.Message):
                    approve_testing.main(['nosetests', 'some_config.ini'])

                # Now we will run main() again, but this time we expect Bodhi not to add any
                # further comments.
                with fml_testing.mock_sends():
                    approve_testing.main(['nosetests', 'some_config.ini'])

        update = self.db.query(models.Update).all()[0]
        self.assertEqual(update.critpath, True)
        self.assertEqual(update.mandatory_days_in_testing, 14)

        bodhi = self.db.query(models.User).filter_by(name=u'bodhi').one()
        comment_q = self.db.query(models.Comment).filter_by(update_id=update.id, user_id=bodhi.id)
        self.assertEqual(comment_q.count(), 1)
        self.assertEqual(
            comment_q[0].text,
            config.get('testing_approval_msg') % update.mandatory_days_in_testing)
        self.assertEqual(update.release.mandatory_days_in_testing, 7)
        self.assertEqual(update.mandatory_days_in_testing, 14)

    def test_non_autokarma_update_with_unmet_karma_requirement(self):
        """
        A non-autokarma update without enough karma should not get comments from Bodhi.
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = False
        update.request = None
        update.stable_karma = 10
        update.status = models.UpdateStatus.testing
        update.comment(self.db, u'testing', author=u'hunter2', karma=1)
        with fml_testing.mock_sends(api.Message):
            self.db.commit()

        with patch('bodhi.server.scripts.approve_testing.initialize_db'):
            with patch('bodhi.server.scripts.approve_testing.get_appsettings', return_value=''):
                with fml_testing.mock_sends():
                    approve_testing.main(['nosetests', 'some_config.ini'])

        # The bodhi user shouldn't exist, since it shouldn't have made any comments
        self.assertEqual(self.db.query(models.User).filter_by(name=u'bodhi').count(), 0)
        # There are three comments, but none from the non-existing bodhi user.
        self.assertEqual(self.db.query(models.Comment).count(), 3)
        usernames = [
            c.user.name
            for c in self.db.query(models.Comment).order_by(models.Comment.timestamp).all()]
        self.assertEqual(usernames, [u'guest', u'anonymous', u'hunter2'])

    def test_non_autokarma_update_with_unmet_karma_requirement_after_time_met(self):
        """
        A non-autokarma update without enough karma that reaches mandatory days in testing should
        get a comment from Bodhi that the update can be pushed to stable.

        See https://github.com/fedora-infra/bodhi/issues/1094
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = False
        update.request = None
        update.stable_karma = 10
        update.status = models.UpdateStatus.testing
        update.date_testing = datetime.utcnow() - timedelta(days=7)
        update.comment(self.db, u'testing', author=u'hunter2', karma=1)
        with fml_testing.mock_sends(api.Message):
            self.db.commit()

        with patch('bodhi.server.scripts.approve_testing.initialize_db'):
            with patch('bodhi.server.scripts.approve_testing.get_appsettings', return_value=''):
                with fml_testing.mock_sends(api.Message):
                    approve_testing.main(['nosetests', 'some_config.ini'])

        bodhi = self.db.query(models.User).filter_by(name=u'bodhi').one()
        comment_q = self.db.query(models.Comment).filter_by(update_id=update.id, user_id=bodhi.id)
        self.assertEqual(comment_q.count(), 1)
        self.assertEqual(
            comment_q[0].text,
            config.get('testing_approval_msg') % update.release.mandatory_days_in_testing)

    # Set the release's mandatory days in testing to 0 to set up the condition for this test.
    @patch.dict(config, [('fedora.mandatory_days_in_testing', 0)])
    def test_non_autokarma_update_without_mandatory_days_in_testing(self):
        """
        If the Update's release doesn't have a mandatory days in testing, main() should ignore it
        (and should not comment on the update at all, even if it does reach karma levels.)
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = False
        update.request = None
        update.stable_karma = 1
        update.status = models.UpdateStatus.testing
        update.comment(self.db, u'testing', author=u'hunter2', karma=1)
        with fml_testing.mock_sends(api.Message):
            self.db.commit()

        with patch('bodhi.server.scripts.approve_testing.initialize_db'):
            with patch('bodhi.server.scripts.approve_testing.get_appsettings', return_value=''):
                approve_testing.main(['nosetests', 'some_config.ini'])

        # The bodhi user shouldn't exist, since it shouldn't have made any comments
        self.assertEqual(self.db.query(models.User).filter_by(name=u'bodhi').count(), 0)
        # There are three comments, but none from the non-existing bodhi user.
        self.assertEqual(self.db.query(models.Comment).count(), 3)
        usernames = [
            c.user.name
            for c in self.db.query(models.Comment).order_by(models.Comment.timestamp).all()]
        self.assertEqual(usernames, [u'guest', u'anonymous', u'hunter2'])

    @patch.dict(config, [('fedora.mandatory_days_in_testing', 14)])
    def test_subsequent_comments_after_initial_push_comment(self):
        """
        If a user edits an update after Bodhi comments a testing_approval_msg,
        Bodhi should send an additional testing_approval_msg when the revised
        update is eligible to be pushed to stable.

        See https://github.com/fedora-infra/bodhi/issues/1310
        """
        update = self.db.query(models.Update).all()[0]
        update.request = None
        update.status = models.UpdateStatus.testing
        update.date_testing = datetime.utcnow() - timedelta(days=14)
        self.db.flush()

        with patch('bodhi.server.scripts.approve_testing.initialize_db'):
            with patch('bodhi.server.scripts.approve_testing.get_appsettings', return_value=''):
                with fml_testing.mock_sends(api.Message):
                    approve_testing.main(['nosetests', 'some_config.ini'])
                update.comment(self.db, u"Removed build", 0, u'bodhi')
                with fml_testing.mock_sends(api.Message):
                    approve_testing.main(['nosetests', 'some_config.ini'])

        bodhi = self.db.query(models.User).filter_by(name=u'bodhi').one()
        cmnts = self.db.query(models.Comment).filter_by(update_id=update.id, user_id=bodhi.id)
        # There are 3 comments: testing_approval_msg, build change, testing_approval_msg
        self.assertEqual(cmnts.count(), 3)
        self.assertEqual(
            cmnts[0].text,
            config.get('testing_approval_msg') %
            update.release.mandatory_days_in_testing)
        self.assertEqual(cmnts[1].text, 'Removed build')
        self.assertEqual(
            cmnts[2].text,
            config.get('testing_approval_msg') %
            update.release.mandatory_days_in_testing)

    @patch('sys.exit')
    @patch('sys.stdout', new_callable=StringIO)
    def test_usage(self, stdout, exit):
        """
        Assert that the usage message is returned to the user if not exactly 2 arguments are given
        """
        with patch('bodhi.server.scripts.approve_testing.initialize_db'):
            with patch('bodhi.server.scripts.approve_testing.get_appsettings', return_value=''):
                approve_testing.main(['nosetests', 'some_config.ini', 'testnoses'])

        self.assertEqual(
            stdout.getvalue(),
            'usage: nosetests <config_uri>\n(example: "nosetests development.ini")\n')
        exit.assert_called_once_with(1)
