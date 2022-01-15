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
This module contains tests for the bodhi.server.tasks.approve_testing module.
"""
from datetime import datetime, timedelta
from unittest.mock import call, patch

from fedora_messaging import api, testing as fml_testing
import pytest

from bodhi.messages.schemas import update as update_schemas
from bodhi.server.config import config
from bodhi.server import models
from bodhi.server.tasks import approve_testing_task
from bodhi.server.tasks.approve_testing import main as approve_testing_main
from ..base import BasePyTestCase
from .base import BaseTaskTestCase


class TestTask(BasePyTestCase):
    """Test the task in bodhi.server.tasks."""

    @patch("bodhi.server.tasks.bugs")
    @patch("bodhi.server.tasks.buildsys")
    @patch("bodhi.server.tasks.initialize_db")
    @patch("bodhi.server.tasks.config")
    @patch("bodhi.server.tasks.approve_testing.main")
    def test_task(self, main_function, config_mock, init_db_mock, buildsys, bugs):
        approve_testing_task()
        config_mock.load_config.assert_called_with()
        init_db_mock.assert_called_with(config_mock)
        buildsys.setup_buildsystem.assert_called_with(config_mock)
        bugs.set_bugtracker.assert_called_with()
        main_function.assert_called_with()


class TestMain(BaseTaskTestCase):
    """
    This class contains tests for the main() function.
    """

    @patch('bodhi.server.models.mail')
    def test_autokarma_update_meeting_time_requirements_gets_one_comment(self, mail):
        """
        Ensure that an update that meets the required time in testing gets only one comment from
        Bodhi to that effect, even on subsequent runs of main().
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = True
        update.autotime = False
        update.request = None
        update.stable_karma = 10
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []

        update.date_testing = datetime.utcnow() - timedelta(days=7)
        with fml_testing.mock_sends():
            self.db.commit()
        expected_message = update_schemas.UpdateRequirementsMetStableV1.from_dict(
            {'update': update})

        with fml_testing.mock_sends(expected_message):
            approve_testing_main()
            # The approve testing script changes the update, so let's put the changed
            # update into our expected message body.
            expected_message.body['update'] = models.Update.query.first().__json__()
        # Now we will run main() again, but this time we expect Bodhi not to add any
        # further comments.
        with fml_testing.mock_sends():
            approve_testing_main()

        bodhi = self.db.query(models.User).filter_by(name='bodhi').one()
        comment_q = self.db.query(models.Comment).filter_by(update_id=update.id, user_id=bodhi.id)
        assert comment_q.count() == 1
        assert comment_q[0].text == config.get('testing_approval_msg')
        assert mail.send.call_count == 1

    # Set the release's mandatory days in testing to 0 to set up the condition for this test.
    @patch.dict(config, [('fedora.mandatory_days_in_testing', 0)])
    def test_autokarma_update_without_mandatory_days_in_testing(self):
        """
        If the Update's release doesn't have a mandatory days in testing, main() should ignore it
        (and should not comment on the update at all, even if it does reach karma levels.)
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = True
        update.autotime = False
        update.request = None
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []

        update.date_testing = datetime.utcnow() - timedelta(days=7)
        # Let's delete all the comments to make our assertion at the end of this simpler.
        for c in update.comments:
            self.db.delete(c)
        with fml_testing.mock_sends():
            self.db.commit()

        with fml_testing.mock_sends():
            approve_testing_main()

        # The bodhi user shouldn't exist, since it shouldn't have made any comments
        assert self.db.query(models.User).filter_by(name='bodhi').count() == 0
        assert self.db.query(models.Comment).count() == 0

    def test_autokarma_update_not_meeting_testing_requirements(self):
        """
        If an autokarma update has not met the testing requirements, bodhi should not comment on the
        update.
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = True
        update.request = None
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        # 6 days isn't enough time to meet the testing requirements.
        update.date_testing = datetime.utcnow() - timedelta(days=6)
        # Let's delete all the comments to make our assertion at the end of this simpler.
        for c in update.comments:
            self.db.delete(c)
        with fml_testing.mock_sends():
            self.db.commit()

        with fml_testing.mock_sends():
            approve_testing_main()

        # The bodhi user shouldn't exist, since it shouldn't have made any comments
        assert self.db.query(models.User).filter_by(name='bodhi').count() == 0
        assert self.db.query(models.Comment).count() == 0

    @patch('bodhi.server.models.Update.comment', side_effect=IOError('The DB died lol'))
    @patch('bodhi.server.tasks.approve_testing.log')
    @pytest.mark.parametrize('composed_by_bodhi', (True, False))
    def test_exception_handler(self, log, comment, composed_by_bodhi):
        """The Exception handler prints the Exception, rolls back and closes the db, and exits."""
        update = self.db.query(models.Update).all()[0]
        update.autotime = False
        update.date_testing = datetime.utcnow() - timedelta(days=15)
        update.request = None
        update.status = models.UpdateStatus.testing
        update.release.composed_by_bodhi = composed_by_bodhi
        self.db.flush()

        with patch.object(self.db, 'commit'):
            with patch.object(self.db, 'rollback'):
                approve_testing_main()
                assert self.db.commit.call_count == 0
                self.db.rollback.assert_called_once_with()

        comment.assert_called_once_with(
            self.db,
            ('This update can be pushed to stable now if the maintainer wishes'),
            author='bodhi',
            email_notification=composed_by_bodhi,
        )
        log.info.assert_called_with(f'{update.alias} now meets testing requirements')
        log.exception.assert_called_with("There was an error approving testing updates.")

    @patch('bodhi.server.models.Update.comment', side_effect=[None, IOError('The DB died lol')])
    @patch('bodhi.server.tasks.approve_testing.log')
    @pytest.mark.parametrize('composed_by_bodhi', (True, False))
    def test_exception_handler_on_the_second_update(
            self, log, comment, composed_by_bodhi):
        """
        Ensure, that when the Exception is raised, all previous transactions are commited,
        the Exception handler prints the Exception, rolls back and closes the db, and exits.
        """
        update = self.db.query(models.Update).all()[0]
        update.autotime = False
        update.date_testing = datetime.utcnow() - timedelta(days=15)
        update.request = None
        update.release.composed_by_bodhi = composed_by_bodhi
        update.status = models.UpdateStatus.testing

        update2 = self.create_update(['bodhi2-2.0-1.fc17'])
        update2.autotime = False
        update2.date_testing = datetime.utcnow() - timedelta(days=15)
        update2.request = None
        update2.status = models.UpdateStatus.testing
        self.db.flush()

        with patch.object(self.db, 'commit'):
            with patch.object(self.db, 'rollback'):
                approve_testing_main()
                assert self.db.commit.call_count == 1
                self.db.rollback.assert_called_once_with()

        comment_expected_call = call(
            self.db,
            ('This update can be pushed to stable now if the maintainer wishes'),
            author='bodhi',
            email_notification=composed_by_bodhi,
        )
        assert comment.call_args_list == [comment_expected_call, comment_expected_call]
        log.info.assert_any_call(f'{update.alias} now meets testing requirements')
        log.info.assert_any_call(f'{update2.alias} now meets testing requirements')
        log.exception.assert_called_with("There was an error approving testing updates.")

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
        update.autotime = False
        # Make this update a critpath update to force meets_testing_requirements into a different
        # code path.
        update.critpath = True
        # It's been in testing long enough to get the comment from bodhi that it can be pushed.
        update.date_testing = datetime.utcnow() - timedelta(days=15)
        update.request = None
        update.stable_karma = 1
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []

        update.comment(self.db, 'testing', author='hunter2', karma=1)
        with fml_testing.mock_sends(api.Message):
            self.db.commit()

        with fml_testing.mock_sends(api.Message):
            approve_testing_main()
        # Now we will run main() again, but this time we expect Bodhi not to add any
        # further comments.
        with fml_testing.mock_sends():
            approve_testing_main()

        bodhi = self.db.query(models.User).filter_by(name='bodhi').one()
        comment_q = self.db.query(models.Comment).filter_by(update_id=update.id, user_id=bodhi.id)
        assert comment_q.count() == 1
        assert comment_q[0].text == config.get('testing_approval_msg')

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
        self.db.flush()
        # Clear pending messages
        self.db.info['messages'] = []

        approve_testing_main()
        # Now we will run main() again, but this time we expect Bodhi not to add any
        # further comments.
        with fml_testing.mock_sends():
            approve_testing_main()

        # The update should have one +1, which is as much as the stable karma but not as much as the
        # required +2 to go stable.
        assert update._composite_karma == (1, 0)
        # The bodhi user shouldn't exist, since it shouldn't have made any comments
        assert self.db.query(models.User).filter_by(name='bodhi').count() == 0
        # There are two comments, but none from the non-existing bodhi user.
        assert self.db.query(models.Comment).count() == 2
        usernames = [
            c.user.name
            for c in self.db.query(models.Comment).order_by(models.Comment.timestamp).all()]
        assert usernames == ['guest', 'anonymous']

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
        update.autotime = False
        update.request = None
        update.stable_karma = 1
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []

        update.comment(self.db, 'testing', author='hunter2', karma=1)
        with fml_testing.mock_sends(api.Message):
            self.db.commit()

        with fml_testing.mock_sends(api.Message):
            approve_testing_main()
        # Now we will run main() again, but this time we expect Bodhi not to add any
        # further comments.
        with fml_testing.mock_sends():
            approve_testing_main()

        bodhi = self.db.query(models.User).filter_by(name='bodhi').one()
        comment_q = self.db.query(models.Comment).filter_by(update_id=update.id, user_id=bodhi.id)
        assert comment_q.count() == 1
        assert comment_q[0].text == config.get('testing_approval_msg')

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
        update.autotime = False
        update.request = None
        update.stable_karma = 10
        update.critpath = True
        update.status = models.UpdateStatus.testing
        update.date_testing = datetime.utcnow() - timedelta(days=14)
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        with fml_testing.mock_sends(api.Message):
            approve_testing_main()
        # Now we will run main() again, but this time we expect Bodhi not to add any
        # further comments.
        with fml_testing.mock_sends():
            approve_testing_main()

        update = self.db.query(models.Update).all()[0]
        assert update.critpath == True
        assert update.mandatory_days_in_testing == 14

        bodhi = self.db.query(models.User).filter_by(name='bodhi').one()
        comment_q = self.db.query(models.Comment).filter_by(update_id=update.id, user_id=bodhi.id)
        assert comment_q.count() == 1
        assert comment_q[0].text == config.get('testing_approval_msg')
        assert update.release.mandatory_days_in_testing == 7
        assert update.mandatory_days_in_testing == 14

    def test_non_autokarma_update_with_unmet_karma_requirement(self):
        """
        A non-autokarma update without enough karma should not get comments from Bodhi.
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = False
        update.request = None
        update.stable_karma = 10
        update.status = models.UpdateStatus.testing
        self.db.flush()
        # Clear pending messages
        self.db.info['messages'] = []

        with fml_testing.mock_sends():
            approve_testing_main()

        # The update should have one positive karma and no negative karmas
        assert update._composite_karma == (1, 0)
        # The bodhi user shouldn't exist, since it shouldn't have made any comments
        assert self.db.query(models.User).filter_by(name='bodhi').count() == 0
        # There are two comments, but none from the non-existing bodhi user.
        assert self.db.query(models.Comment).count() == 2
        usernames = [
            c.user.name
            for c in self.db.query(models.Comment).order_by(models.Comment.timestamp).all()]
        assert usernames == ['guest', 'anonymous']

    def test_non_autokarma_update_with_unmet_karma_requirement_after_time_met(self):
        """
        A non-autokarma update without enough karma that reaches mandatory days in testing should
        get a comment from Bodhi that the update can be pushed to stable.

        See https://github.com/fedora-infra/bodhi/issues/1094
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = False
        update.autotime = False
        update.request = None
        update.stable_karma = 10
        update.status = models.UpdateStatus.testing
        update.date_testing = datetime.utcnow() - timedelta(days=7)
        self.db.flush()
        # Clear pending messages
        self.db.info['messages'] = []

        with fml_testing.mock_sends(api.Message):
            approve_testing_main()

        # The update should have one positive karma and no negative karmas
        assert update._composite_karma == (1, 0)
        bodhi = self.db.query(models.User).filter_by(name='bodhi').one()
        comment_q = self.db.query(models.Comment).filter_by(update_id=update.id, user_id=bodhi.id)
        assert comment_q.count() == 1
        assert comment_q[0].text == config.get('testing_approval_msg')

    # Set the release's mandatory days in testing to 0 to set up the condition for this test.
    @patch.dict(config, [('fedora.mandatory_days_in_testing', 0)])
    def test_non_autokarma_update_without_mandatory_days_in_testing(self):
        """
        If the Update's release doesn't have a mandatory days in testing, main() should ignore it
        (and should not comment on the update at all, even if it does reach karma levels.)
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = False
        update.autotime = False
        update.request = None
        update.stable_karma = 1
        update.status = models.UpdateStatus.testing
        self.db.flush()
        # Clear pending messages
        self.db.info['messages'] = []

        approve_testing_main()

        # The update should have one positive karma and no negative karmas
        assert update._composite_karma == (1, 0)
        # The bodhi user shouldn't exist, since it shouldn't have made any comments
        assert self.db.query(models.User).filter_by(name='bodhi').count() == 0
        # There are two comments, but none from the non-existing bodhi user.
        assert self.db.query(models.Comment).count() == 2
        usernames = [
            c.user.name
            for c in self.db.query(models.Comment).order_by(models.Comment.timestamp).all()]
        assert usernames == ['guest', 'anonymous']

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
        update.autotime = False
        self.db.flush()
        # Clear pending messages
        self.db.info['messages'] = []

        with fml_testing.mock_sends(api.Message):
            approve_testing_main()
        update.comment(self.db, "Removed build", 0, 'bodhi')
        with fml_testing.mock_sends(api.Message):
            approve_testing_main()

        bodhi = self.db.query(models.User).filter_by(name='bodhi').one()
        cmnts = self.db.query(models.Comment).filter_by(update_id=update.id, user_id=bodhi.id)
        # There are 3 comments: testing_approval_msg, build change, testing_approval_msg
        assert cmnts.count() == 3
        assert cmnts[0].text == config.get('testing_approval_msg')
        assert cmnts[1].text == 'Removed build'
        assert cmnts[2].text == config.get('testing_approval_msg')

    def test_autotime_update_meeting_test_requirements_gets_pushed(self):
        """
        Ensure that an autotime update that meets the test requirements gets pushed to stable.
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = False
        update.autotime = True
        update.request = None
        update.stable_karma = 10
        update.stable_days = 7
        update.date_testing = datetime.utcnow() - timedelta(days=7)
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        with fml_testing.mock_sends(update_schemas.UpdateRequirementsMetStableV1,
                                    update_schemas.UpdateRequestStableV1):
            approve_testing_main()

        assert update.request == models.UpdateRequest.stable

    def test_autotime_update_does_not_meet_stable_days_doesnt_get_pushed(self):
        """
        Ensure that an autotime update that meets the test requirements but has a longer
        stable days define does not get push.
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = False
        update.autotime = True
        update.request = None
        update.stable_karma = 10
        update.stable_days = 10
        update.date_testing = datetime.utcnow() - timedelta(days=7)
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        with fml_testing.mock_sends(api.Message):
            approve_testing_main()

        assert update.request is None

    def test_autotime_update_meeting_stable_days_get_pushed(self):
        """
        Ensure that an autotime update that meets the stable days gets pushed.
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = False
        update.autotime = True
        update.request = None
        update.stable_karma = 10
        update.stable_days = 10
        update.date_testing = datetime.utcnow() - timedelta(days=10)
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        with fml_testing.mock_sends(api.Message, api.Message):
            approve_testing_main()

        assert update.request == models.UpdateRequest.stable

    def test_no_autotime_update_meeting_stable_days_and_test_requirement(self):
        """
        Ensure that a normal update that meets the stable days and test requirements
        doe not get pushed.
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = False
        update.autotime = False
        update.request = None
        update.stable_karma = 10
        update.stable_days = 10
        update.date_testing = datetime.utcnow() - timedelta(days=10)
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        with fml_testing.mock_sends(api.Message):
            approve_testing_main()

        assert update.request is None

    @patch.dict(config, [('fedora.mandatory_days_in_testing', 2)])
    def test_autotime_update_does_not_meet_test_requirements(self):
        """
        Ensure that an autotime update that does not meet the test requirements
        does not pushed to stable.
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = False
        update.autotime = True
        update.request = None
        update.stable_days = update.mandatory_days_in_testing
        update.stable_karma = 10
        update.date_testing = datetime.utcnow() - timedelta(days=1)
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        approve_testing_main()

        assert update.request is None

    @patch.dict(config, [('fedora.mandatory_days_in_testing', 0)])
    def test_autotime_update_does_no_mandatory_days_in_testing(self):
        """
        Ensure that an autotime update that does not have mandatory days in testing
        does get pushed to stable.
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = False
        update.autotime = True
        update.request = None
        update.stable_karma = 10
        update.date_testing = datetime.utcnow()
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        with fml_testing.mock_sends(api.Message, api.Message):
            approve_testing_main()

        assert update.request == models.UpdateRequest.stable

    @patch.dict(config, [('fedora.mandatory_days_in_testing', 0)])
    def test_autotime_update_zero_day_in_testing_meeting_test_requirements_gets_pushed(self):
        """
        Ensure that an autotime update with 0 mandatory_days_in_testing that meets
        the test requirements gets pushed to stable.
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = False
        update.autotime = True
        update.request = None
        update.stable_karma = 10
        update.stable_days = 0
        update.date_testing = datetime.utcnow() - timedelta(days=0)
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        with fml_testing.mock_sends(api.Message, api.Message):
            approve_testing_main()

        assert update.request == models.UpdateRequest.stable
        assert update.status == models.UpdateStatus.testing
        assert update.date_stable is None

    @pytest.mark.parametrize('from_side_tag', (None, 'f17-build-side-1234'))
    @patch.dict(config, [('fedora.mandatory_days_in_testing', 0)])
    @patch('bodhi.server.models.Update.add_tag')
    @patch('bodhi.server.models.Update.remove_tag')
    @patch('bodhi.server.buildsys.DevBuildsys.deleteTag')
    @patch('bodhi.server.models.mail')
    def test_autotime_update_zero_day_in_testing_no_gated_gets_pushed_to_rawhide(
            self, mail, delete_tag, remove_tag, add_tag, from_side_tag):
        """
        Ensure that an autotime update with 0 mandatory_days_in_testing that meets
        the test requirements gets pushed to stable in rawhide.

        Test for normal updates and such from a side tags, where it and its
        auxiliary tags need to be removed.
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = False
        update.autotime = True
        update.request = None
        update.release.composed_by_bodhi = False
        update.stable_karma = 10
        update.stable_days = 0
        update.date_testing = datetime.utcnow() - timedelta(days=0)
        update.status = models.UpdateStatus.testing
        update.from_tag = from_side_tag
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        with fml_testing.mock_sends(api.Message):
            approve_testing_main()

        assert update.request is None
        assert update.date_stable is not None
        assert update.status == models.UpdateStatus.stable
        assert update.pushed
        assert update.date_pushed is not None

        if not from_side_tag:
            # First pass, it adds f17=updates-pending, then since we're pushing
            # to stable directly, it adds f17-updates (the stable tag) then
            # removes f17-updates-testing-pending and f17-updates-pending
            assert remove_tag.call_args_list == \
                [call('f17-updates-testing-pending'), call('f17-updates-pending'),
                 call('f17-updates-signing-pending'), call('f17-updates-testing'),
                 call('f17-updates-candidate')]

            assert add_tag.call_args_list == \
                [call('f17-updates')]
            assert delete_tag.not_called()
        else:
            assert remove_tag.call_args_list == \
                [call(f'{from_side_tag}-signing-pending'),
                 call(f'{from_side_tag}-testing-pending'),
                 call(from_side_tag)]

            assert add_tag.call_args_list == \
                [call('f17-updates')]
            assert delete_tag.call_args_list == \
                [call(f'{from_side_tag}-signing-pending'),
                 call(f'{from_side_tag}-testing-pending'),
                 call(from_side_tag)]

        assert mail.send.call_count == 1

    @patch.dict(config, [('fedora.mandatory_days_in_testing', 0)])
    @patch.dict(config, [('test_gating.required', True)])
    def test_autotime_update_zero_day_in_testing_fail_gating_is_not_pushed(self):
        """
        Ensure that an autotime update with 0 mandatory days in testing that failed gating
        does not get pushed to stable.
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = False
        update.autotime = True
        update.request = None
        update.stable_karma = 10
        update.stable_days = 0
        update.test_gating_status = models.TestGatingStatus.failed
        update.date_testing = datetime.utcnow() - timedelta(days=0)
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        approve_testing_main()

        assert update.request is None

    def test_autotime_update_negative_karma_does_not_get_pushed(self):
        """
        Ensure that an autotime update with negative karma does not get pushed.
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = False
        update.autotime = True
        update.request = None
        update.stable_karma = 10
        update.stable_days = 0
        update.date_testing = datetime.utcnow() - timedelta(days=0)
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []

        update.comment(self.db, u'Failed to work', author=u'luke', karma=-1)
        with fml_testing.mock_sends(api.Message):
            self.db.commit()

        approve_testing_main()

        assert update.request is None

    def test_autotime_update_no_autokarma_met_karma_requirements_get_comments(self):
        """
        Ensure that an autotime update which met the karma requirements but has autokarma off
        get a comment to let the packager know that he can push the update to stable.
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = False
        update.autotime = True
        update.request = None
        update.stable_karma = 1
        update.stable_days = 10
        update.date_testing = datetime.utcnow() - timedelta(days=0)
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []

        update.comment(self.db, u'Works great', author=u'luke', karma=1)
        with fml_testing.mock_sends(api.Message):
            self.db.commit()

        with fml_testing.mock_sends(api.Message):
            approve_testing_main()

        assert update.request is None

        bodhi = self.db.query(models.User).filter_by(name='bodhi').one()
        cmnts = self.db.query(models.Comment).filter_by(update_id=update.id, user_id=bodhi.id)
        assert cmnts.count() == 1
        assert cmnts[0].text == config.get('testing_approval_msg')

    def test_autotime_update_no_autokarma_met_karma_and_time_requirements_get_pushed(self):
        """
        Ensure that an autotime update which met the karma and time requirements but
        has autokarma off gets pushed.
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = False
        update.autotime = True
        update.request = None
        update.stable_karma = 1
        update.stable_days = 0
        update.date_testing = datetime.utcnow() - timedelta(days=0)
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []

        update.comment(self.db, u'Works great', author=u'luke', karma=1)
        with fml_testing.mock_sends(api.Message):
            self.db.commit()

        with fml_testing.mock_sends(api.Message, api.Message):
            approve_testing_main()

        assert update.request == models.UpdateRequest.stable

        bodhi = self.db.query(models.User).filter_by(name='bodhi').one()
        cmnts = self.db.query(models.Comment).filter_by(update_id=update.id, user_id=bodhi.id)
        assert cmnts.count() == 1
        assert cmnts[0].text == 'This update has been submitted for stable by bodhi. '

    def test_autotime_update_with_autokarma_met_karma_and_time_requirements_get_pushed(self):
        """
        Ensure that an autotime update which met the karma and time requirements and has autokarma
        and autotime enable gets pushed.
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = True
        update.autotime = True
        update.request = None
        update.stable_karma = 1
        update.stable_days = 0
        update.date_testing = datetime.utcnow() - timedelta(days=0)
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []

        with fml_testing.mock_sends(api.Message, api.Message, api.Message):
            update.comment(self.db, u'Works great', author=u'luke', karma=1)
            self.db.commit()

        approve_testing_main()

        assert update.request == models.UpdateRequest.stable

        bodhi = self.db.query(models.User).filter_by(name='bodhi').one()
        cmnts = self.db.query(models.Comment).filter_by(update_id=update.id, user_id=bodhi.id)
        assert cmnts.count() == 1
        assert cmnts[0].text == 'This update has been submitted for stable by bodhi. '

    def test_autotime_update_no_autokarma_negative_karma_not_pushed(self):
        """
        Ensure that an autotime update which negative karma does not get pushed.
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = False
        update.autotime = True
        update.request = None
        update.stable_karma = 1
        update.stable_days = 0
        update.date_testing = datetime.utcnow() - timedelta(days=8)
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        update.comment(self.db, u'Broken', author=u'luke', karma=-1)
        with fml_testing.mock_sends(api.Message):
            self.db.commit()

        with fml_testing.mock_sends(api.Message):
            approve_testing_main()

        assert update.request is None
        assert update.autotime == False

    @patch("bodhi.server.buildsys.DevBuildsys.getLatestBuilds", return_value=[{
        'creation_time': '2007-08-25 19:38:29.422344'}])
    @pytest.mark.parametrize(('from_tag', 'update_status'),
                             [('f17-build-side-1234', models.UpdateStatus.pending),
                             (None, models.UpdateStatus.obsolete)])
    def test_update_conflicting_build_not_pushed(self, build_creation_time,
                                                 from_tag, update_status):
        """
        Ensure that an update that have conflicting builds will not get pushed.
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = False
        update.autotime = True
        update.request = None
        update.stable_karma = 1
        update.stable_days = 7
        update.date_testing = datetime.utcnow() - timedelta(days=8)
        update.status = models.UpdateStatus.testing
        update.release.composed_by_bodhi = False
        update.from_tag = from_tag

        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        with fml_testing.mock_sends(api.Message):
            approve_testing_main()

        assert update.status == update_status

        bodhi = self.db.query(models.User).filter_by(name='bodhi').one()
        cmnts = self.db.query(models.Comment).filter_by(update_id=update.id, user_id=bodhi.id)
        assert cmnts.count() == 1
        assert cmnts[0].text == "This update cannot be pushed to stable. "\
            "These builds bodhi-2.0-1.fc17 have a more recent build in koji's "\
            f"{update.release.stable_tag} tag."

    def test_autotime_update_gets_pushed_dont_send_duplicated_notification(self):
        """
        Ensure not emitting UpdateRequirementsMetStable notification when an autotime update
        gets pushed to stable if that was emitted before.

        When an update reaches its mandatory_days_in_testing threshold, the
        UpdateRequirementsMetStableV1 notification is sent along with a comment that informs
        the maintainer they can manually push the update to stable. The update IS NOT
        automatically pushed now.
        Then, when the update reaches its stable_days threshold, it is automatically pushed,
        but we don't want to emit UpdateRequirementsMetStable a second time.
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = False
        update.autotime = True
        update.request = None
        update.stable_karma = 10
        update.stable_days = 10
        update.date_testing = datetime.utcnow() - timedelta(days=7)
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        assert not update.has_stable_comment

        with fml_testing.mock_sends(update_schemas.UpdateRequirementsMetStableV1):
            approve_testing_main()

        assert update.has_stable_comment
        assert update.request == None
        assert update.status == models.UpdateStatus.testing

        update.date_testing = datetime.utcnow() - timedelta(days=10)
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        with fml_testing.mock_sends(update_schemas.UpdateRequestStableV1):
            approve_testing_main()

        assert update.request == models.UpdateRequest.stable

    def test_autotime_update_with_stable_comment_set_stable_on_branched(self):
        """
        Ensure update is pushed to stable on releases not composed by Bodhi if
        the update already has a stable comment.
        """
        update = self.db.query(models.Update).all()[0]
        update.autokarma = False
        update.autotime = True
        update.request = None
        update.stable_karma = 10
        update.stable_days = 10
        update.release.composed_by_bodhi = False
        update.date_testing = datetime.utcnow() - timedelta(days=7)
        update.status = models.UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        assert not update.has_stable_comment

        with fml_testing.mock_sends(update_schemas.UpdateRequirementsMetStableV1):
            approve_testing_main()

        assert update.has_stable_comment
        assert update.request == None
        assert update.status == models.UpdateStatus.testing

        update.date_testing = datetime.utcnow() - timedelta(days=10)
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        # No further notifications emitted
        approve_testing_main()

        assert update.status == models.UpdateStatus.stable
