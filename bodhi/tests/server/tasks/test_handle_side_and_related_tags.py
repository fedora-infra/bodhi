from unittest.mock import patch

from bodhi.server import buildsys, models
from bodhi.server.tasks import handle_side_and_related_tags_task
from bodhi.server.tasks.handle_side_and_related_tags import main as handle_srtags_main
from bodhi.tests.server.base import BasePyTestCase
from .base import BaseTaskTestCase


class TestTask(BasePyTestCase):
    """Test the task in bodhi.server.tasks."""

    @patch("bodhi.server.tasks.buildsys")
    @patch("bodhi.server.tasks.initialize_db")
    @patch("bodhi.server.tasks.config")
    @patch("bodhi.server.tasks.handle_side_and_related_tags.main")
    def test_task(self, main_function, config_mock, init_db_mock, buildsys):
        handle_side_and_related_tags_task(updates=[], from_tag="")
        config_mock.load_config.assert_called_with()
        init_db_mock.assert_called_with(config_mock)
        buildsys.setup_buildsystem.assert_called_with(config_mock)
        main_function.assert_called_with([], "")


class TestMain(BaseTaskTestCase):
    """
    This class contains tests for the main() function.
    """

    def test_side_tag_composed_by_bodhi(self):
        updates = self.db.query(models.Update).all()
        handle_srtags_main(updates, "f17-build-side-1234")
        koji = buildsys.get_session()

        assert ('f17-updates-signing-pending', 'bodhi-2.0-1.fc17') in koji.__added__
        assert {'id': 1234, 'name': 'f17-build-side-1234'} in koji.__removed_side_tags__

    def test_side_tag_not_composed_by_bodhi(self):
        update = self.db.query(models.Update).first()
        update.release.composed_by_bodhi = False
        self.db.commit()
        handle_srtags_main([update], "f32-build-side-1234")
        koji = buildsys.get_session()

        assert ('f32-build-side-1234-signing-pending', 'bodhi-2.0-1.fc17') in koji.__added__
        assert "f32-build-side-1234-signing-pending" in koji.__tags__[0][0]
        assert "f32-build-side-1234-testing-pending" in koji.__tags__[1][0]
