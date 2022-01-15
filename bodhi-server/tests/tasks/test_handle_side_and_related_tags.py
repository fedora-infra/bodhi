from unittest.mock import patch

from bodhi.server import buildsys, models
from bodhi.server.tasks import handle_side_and_related_tags_task
from bodhi.server.tasks.handle_side_and_related_tags import main as handle_srtags_main
from ..base import BasePyTestCase
from .base import BaseTaskTestCase


class TestTask(BasePyTestCase):
    """Test the task in bodhi.server.tasks."""

    @patch("bodhi.server.tasks.buildsys")
    @patch("bodhi.server.tasks.initialize_db")
    @patch("bodhi.server.tasks.config")
    @patch("bodhi.server.tasks.handle_side_and_related_tags.main")
    def test_task(self, main_function, config_mock, init_db_mock, buildsys):
        handle_side_and_related_tags_task(builds=[], pending_signing_tag="", from_tag="")
        config_mock.load_config.assert_called_with()
        init_db_mock.assert_called_with(config_mock)
        buildsys.setup_buildsystem.assert_called_with(config_mock)
        main_function.assert_called_with([], "", "", None, None)


class TestMain(BaseTaskTestCase):
    """
    This class contains tests for the main() function.
    """

    def test_side_tag_composed_by_bodhi(self):
        u = self.db.query(models.Update).first()
        from_tag = "f17-build-side-1234"
        builds = [b.nvr for b in u.builds]
        handle_srtags_main(builds, u.release.pending_signing_tag, from_tag,
                           None, u.release.candidate_tag)

        koji = buildsys.get_session()
        assert ('f17-updates-signing-pending', 'bodhi-2.0-1.fc17') in koji.__added__
        assert ('f17-updates-candidate', 'bodhi-2.0-1.fc17') in koji.__added__

    def test_side_tag_not_composed_by_bodhi(self):
        u = self.db.query(models.Update).first()
        from_tag = "f32-build-side-1234"
        side_tag_signing_pending = u.release.get_pending_signing_side_tag(from_tag)
        side_tag_testing_pending = u.release.get_pending_testing_side_tag(from_tag)
        builds = [b.nvr for b in u.builds]
        handle_srtags_main(builds, side_tag_signing_pending, from_tag,
                           side_tag_testing_pending, None)

        koji = buildsys.get_session()
        assert ('f32-build-side-1234-signing-pending', 'bodhi-2.0-1.fc17') in koji.__added__
        assert "f32-build-side-1234-signing-pending" in koji.__tags__[0][0]
        assert "f32-build-side-1234-testing-pending" in koji.__tags__[1][0]

    def test_side_tag_raise_exception(self, caplog):
        update = self.db.query(models.Update).first()
        builds = [b.nvr for b in update.builds]
        update.release.pending_signing_tag = None
        handle_srtags_main(builds, update.release.pending_signing_tag, None, None,
                           update.release.candidate_tag)
        assert "There was an error handling side-tags updates" in caplog.messages
