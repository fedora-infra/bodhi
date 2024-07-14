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
from datetime import datetime, timedelta, timezone
from unittest.mock import call, patch

from fedora_messaging import testing as fml_testing
import pytest
import sqlalchemy.exc

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

    def setup_method(self):
        """
        Get an update to work with and set some common attributes that
        make sense for all or most of the tests.
        """
        super(TestMain, self).setup_method(self)
        # Clear pending messages
        self.db.info['messages'] = []
        # Get an update to work with
        self.update = self.db.query(models.Update).all()[0]
        self.update.status = models.UpdateStatus.testing
        self.update.request = None
        self.update.date_approved = None
        self.update.release.composed_by_bodhi = False
        with fml_testing.mock_sends():
            self.db.commit()
        # approve_testing never sends mail directly, so we always just
        # want to mock this out and not worry about it
        self.mailpatcher = patch('bodhi.server.models.mail')
        self.mailpatcher.start()

    def teardown_method(self):
        """Stop the mail patcher on teardown."""
        super(TestMain, self).teardown_method(self)
        self.mailpatcher.stop()

    def _assert_not_pushed(self):
        """Run all checks to ensure we did not push the update."""
        assert self.update.status == models.UpdateStatus.testing
        assert self.update.request is None
        assert self.update.date_pushed is None
        assert not self.update.pushed

    def _assert_commented(self, times):
        """Assert the testing_approval_msg was posted exactly (times) times."""
        try:
            bodhi = self.db.query(models.User).filter_by(name='bodhi').one()
            bodhicomments = self.db.query(models.Comment).filter_by(
                update_id=self.update.id, user_id=bodhi.id
            )
        except sqlalchemy.exc.NoResultFound:
            bodhicomments = []
        approvalcomments = [
            comment for comment in bodhicomments
            if comment.text == config.get('testing_approval_msg')
        ]
        assert len(approvalcomments) == times

    @patch('bodhi.server.models.Update.meets_testing_requirements', False)
    def test_update_not_approved(self):
        """
        Ensure that if the update does not meet testing requirements, we do
        nothing.
        """
        # for robustness, make it look like the update meets autotime
        # requirements, we should do nothing even so
        self.update.autotime = True
        self.update.stable_days = 0
        # this should publish no messages
        with fml_testing.mock_sends():
            approve_testing_main()
        # we should not have pushed
        self._assert_not_pushed()
        # we should not have posted approval comment
        self._assert_commented(0)
        # we should not have set date_approved
        assert self.update.date_approved is None

    @pytest.mark.parametrize("autotime_enabled", (True, False))
    @patch('bodhi.server.models.Update.meets_testing_requirements', True)
    def test_update_approved_only(self, autotime_enabled):
        """
        Ensure that if the update meets testing requirements but does not meet
        time-based autopush requirements, we comment on it exactly once, even
        on multiple runs.
        """
        # different ways of failing autotime requirements
        if autotime_enabled:
            # autotime is enabled, but we have not been in testing long enough
            self.update.autotime = True
            self.update.stable_days = 7
        else:
            # we have been in testing long enough, but autotime is not enabled
            self.update.autotime = False
            self.update.stable_days = 0
        with fml_testing.mock_sends(update_schemas.UpdateRequirementsMetStableV1):
            approve_testing_main()
        # we should not have pushed
        self._assert_not_pushed()
        # we should have posted approval comment once
        self._assert_commented(1)
        # we should have set date_approved
        assert self.update.date_approved is not None
        # re-run, this time no additional message should be published
        with fml_testing.mock_sends():
            approve_testing_main()
        # we should still only have posted approval comment once
        self._assert_commented(1)

    @pytest.mark.parametrize("stable_days", (0, 7, 14))
    @pytest.mark.parametrize("has_stable_comment", (True, False))
    @pytest.mark.parametrize("composed_by_bodhi", (True, False))
    @pytest.mark.parametrize('from_side_tag', (None, 'f17-build-side-1234'))
    @patch('bodhi.server.models.Update.add_tag')
    @patch('bodhi.server.models.Update.remove_tag')
    @patch('bodhi.server.buildsys.DevBuildsys.deleteTag')
    @patch('bodhi.server.models.Update.meets_testing_requirements', True)
    def test_update_approved_and_autotime(self, delete_tag, remove_tag, add_tag,
                                          from_side_tag, composed_by_bodhi, has_stable_comment,
                                          stable_days):
        """
        Ensure that if the update meets testing requirements *and* the autotime
        push threshold, we push it, publish RequirementsMetStable unless the
        update has the ready-for-stable comment (indicating it was previously
        approved), and set date_approved, but do not comment.
        """
        self.update.autotime = True
        # a sprinkling of possible cases just to make sure our logic isn't broken
        # and we're not somehow relying on defaults
        if stable_days < 7:
            # our test config sets it to 7, so need to override it
            config["fedora.mandatory_days_in_testing"] = stable_days
        self.update.stable_days = stable_days
        if stable_days > 0:
            # in this case we need to make sure we look like we've been in testing
            # this one
            self.update.date_testing = datetime.now(timezone.utc) - timedelta(days=stable_days + 1)
        self.update.release.composed_by_bodhi = composed_by_bodhi
        self.update.from_tag = from_side_tag
        # we publish UpdateRequirementsMet unless the update already has the
        # stable comment indicating it was previously approved
        # we publish UpdateRequestStable on the composed_by_bodhi path, because
        # we call update.set_request() which does that
        with patch('bodhi.server.models.Update.has_stable_comment', has_stable_comment):
            if composed_by_bodhi:
                if has_stable_comment:
                    with fml_testing.mock_sends(update_schemas.UpdateRequestStableV1):
                        approve_testing_main()
                else:
                    with fml_testing.mock_sends(update_schemas.UpdateRequirementsMetStableV1,
                                                update_schemas.UpdateRequestStableV1):
                        approve_testing_main()
            else:
                if has_stable_comment:
                    with fml_testing.mock_sends():
                        approve_testing_main()
                else:
                    with fml_testing.mock_sends(update_schemas.UpdateRequirementsMetStableV1):
                        approve_testing_main()
        # we should not have posted approval comment (yes, even if it
        # wasn't posted before; it's not useful information if we're
        # autopushing)
        self._assert_commented(0)
        # we should have set date_approved
        assert self.update.date_approved is not None
        # we should have pushed. this logic is not split out because it's
        # long and awkward to split out and only used here
        if self.update.release.composed_by_bodhi:
            # we should have set the request, but not done the push
            assert self.update.request == models.UpdateRequest.stable
            assert self.update.status == models.UpdateStatus.testing
            assert self.update.date_stable is None
        else:
            # we should have actually done the push
            assert self.update.request is None
            assert self.update.date_stable is not None
            assert self.update.status == models.UpdateStatus.stable
            assert self.update.pushed
            assert self.update.date_pushed is not None

            if from_side_tag:
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
            else:
                # First pass, it adds f17=updates-pending, then since we're pushing
                # to stable directly, it adds f17-updates (the stable tag) then
                # removes f17-updates-testing-pending and f17-updates-pending
                assert remove_tag.call_args_list == \
                    [call('f17-updates-testing-pending'), call('f17-updates-pending'),
                     call('f17-updates-signing-pending'), call('f17-updates-testing'),
                     call('f17-updates-candidate')]

                assert add_tag.call_args_list == \
                    [call('f17-updates')]
                delete_tag.assert_not_called()

    @pytest.mark.parametrize(('from_tag', 'update_status'),
                             [('f17-build-side-1234', models.UpdateStatus.pending),
                             (None, models.UpdateStatus.obsolete)])
    @patch("bodhi.server.buildsys.DevBuildsys.getLatestBuilds", return_value=[{
        'creation_time': '2007-08-25 19:38:29.422344'}])
    @patch('bodhi.server.models.Update.meets_testing_requirements', True)
    def test_update_conflicting_build_not_pushed(self, build_creation_time,
                                                 from_tag, update_status):
        """
        Ensure that an update that has conflicting builds is not pushed.
        """
        self.update.release.composed_by_bodhi = False
        self.update.from_tag = from_tag

        # message publishing happens before the conflicting build check, so
        # even when there's a conflicting build, we publish this message
        with fml_testing.mock_sends(update_schemas.UpdateRequirementsMetStableV1):
            approve_testing_main()

        assert self.update.status == update_status
        # date_approved is also set before the conflicting build check, so
        # we do set it in this case. this isn't really wrong, because that
        # date really indicates the first date an update met all the requirements
        # to be manually submitted stable, which is still the case here
        assert self.update.date_approved is not None

        bodhi = self.db.query(models.User).filter_by(name='bodhi').one()
        cmnts = self.db.query(models.Comment).filter_by(update_id=self.update.id, user_id=bodhi.id)
        assert cmnts.count() == 1
        assert cmnts[0].text == "This update cannot be pushed to stable. "\
            "These builds bodhi-2.0-1.fc17 have a more recent build in koji's "\
            f"{self.update.release.stable_tag} tag."

    @pytest.mark.parametrize('composed_by_bodhi', (True, False))
    @patch('bodhi.server.models.Update.comment', side_effect=IOError('The DB died lol'))
    @patch('bodhi.server.tasks.approve_testing.log')
    @patch('bodhi.server.models.Update.meets_testing_requirements', True)
    def test_exception_handler(self, log, comment, composed_by_bodhi):
        """The Exception handler prints the Exception, rolls back and closes the db, and exits."""
        self.update.autotime = False
        self.update.release.composed_by_bodhi = composed_by_bodhi
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
        log.info.assert_called_with(f'{self.update.alias} now meets testing requirements')
        log.exception.assert_called_with("There was an error approving testing updates.")

    @pytest.mark.parametrize('composed_by_bodhi', (True, False))
    @patch('bodhi.server.models.Update.comment', side_effect=[None, IOError('The DB died lol')])
    @patch('bodhi.server.tasks.approve_testing.log')
    @patch('bodhi.server.models.Update.meets_testing_requirements', True)
    def test_exception_handler_on_the_second_update(self, log, comment, composed_by_bodhi):
        """
        Ensure, that when the Exception is raised, all previous transactions are commited,
        the Exception handler prints the Exception, rolls back and closes the db, and exits.
        """
        self.update.autotime = False
        self.update.release.composed_by_bodhi = composed_by_bodhi

        update2 = self.create_update(['bodhi2-2.0-1.fc17'])
        update2.autotime = False
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
        log.info.assert_any_call(f'{self.update.alias} now meets testing requirements')
        log.info.assert_any_call(f'{update2.alias} now meets testing requirements')
        log.exception.assert_called_with("There was an error approving testing updates.")
