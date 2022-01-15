from unittest.mock import patch, MagicMock

from bodhi.server import buildsys, models
from bodhi.server.tasks import tag_update_builds_task
from bodhi.server.tasks.tag_update_builds import main as tag_update_builds_main
from ..base import BasePyTestCase
from .base import BaseTaskTestCase


class TestTask(BasePyTestCase):
    """Test the task in bodhi.server.tasks."""

    @patch("bodhi.server.tasks.buildsys")
    @patch("bodhi.server.tasks.initialize_db")
    @patch("bodhi.server.tasks.config")
    @patch("bodhi.server.tasks.tag_update_builds.main")
    def test_task(self, main_function, config_mock, init_db_mock, buildsys):
        tag_update_builds_task(tag=None, builds=[])
        config_mock.load_config.assert_called_with()
        init_db_mock.assert_called_with(config_mock)
        buildsys.setup_buildsystem.assert_called_with(config_mock)
        main_function.assert_called_with(None, [])


class TestMain(BaseTaskTestCase):
    """
    This class contains tests for the main() function.
    """

    def test_tag_pending_signing_builds(self):
        update = self.db.query(models.Update).first()
        pending_signing_tag = update.release.pending_signing_tag
        tag_update_builds_main(pending_signing_tag, update.builds)
        koji = buildsys.get_session()
        assert (pending_signing_tag, update.builds[0]) in koji.__added__

    def test_tag_pending_signing_side_tag(self):
        update = self.db.query(models.Update).first()
        update.from_tag = "f17-build-side-1234"
        side_tag_pending_signing = "f17-build-side-1234-signing-pending"
        self.db.commit()

        tag_update_builds_main(side_tag_pending_signing, update.builds)

        koji = buildsys.get_session()
        assert (side_tag_pending_signing, update.builds[0]) in koji.__added__

    def test_tag_raise_execption(self, caplog):
        mock_release = MagicMock()
        mock_release.get_pending_signing_side_tag.return_value = None
        update = self.db.query(models.Update).first()
        update.from_tag = "f17-build-side-1234"
        self.db.commit()
        with patch("bodhi.server.buildsys._buildsystem", return_value=None):
            tag_update_builds_main("f17-signing-pending", update.builds)

        assert "There was an error handling tagging builds in koji." in caplog.messages
