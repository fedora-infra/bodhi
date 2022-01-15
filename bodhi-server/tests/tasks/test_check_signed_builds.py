# Copyright © 2020 Mattia Verga.
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
This module contains tests for the bodhi.server.tasks.check_signed_builds module.
"""

from datetime import datetime
from unittest.mock import patch

from bodhi.server import models
from bodhi.server.tasks import check_signed_builds_task
from bodhi.server.tasks.check_signed_builds import main as check_signed_builds_main
from ..base import BasePyTestCase
from .base import BaseTaskTestCase


class TestTask(BasePyTestCase):
    """Test the task in bodhi.server.tasks."""

    @patch("bodhi.server.tasks.buildsys")
    @patch("bodhi.server.tasks.initialize_db")
    @patch("bodhi.server.tasks.config")
    @patch("bodhi.server.tasks.check_signed_builds.main")
    def test_task(self, main_function, config_mock, init_db_mock, buildsys):
        check_signed_builds_task()
        config_mock.load_config.assert_called_with()
        init_db_mock.assert_called_with(config_mock)
        buildsys.setup_buildsystem.assert_called_with(config_mock)
        main_function.assert_called()


class TestCheckSignedBuilds(BaseTaskTestCase):
    """This test class contains tests for the main() function."""

    @patch('bodhi.server.tasks.check_signed_builds.buildsys')
    @patch('bodhi.server.tasks.check_signed_builds.log.debug')
    def test_check_signed_builds_exclude_archived(self, debug, buildsys):
        """
        The task should ignore archived releases.
        """
        release = models.Release.query.first()
        release.state = models.ReleaseState.archived

        self.db.commit()

        check_signed_builds_main()

        debug.assert_called_once_with('No stuck Updates found')
        buildsys.get_session.assert_not_called()

    @patch('bodhi.server.tasks.check_signed_builds.buildsys')
    @patch('bodhi.server.tasks.check_signed_builds.log.debug')
    def test_check_signed_builds_ignore_fresh_update(self, debug, buildsys):
        """
        The task should ignore fresh updates.
        """
        update = models.Update.query.first()
        update.date_submitted = datetime.utcnow()
        update.builds[0].signed = False

        self.db.commit()

        listTags = [
            {'arches': 'i386 x86_64 ppc ppc64', 'id': 10, 'locked': True,
             'name': 'f17-updates-candidate', 'perm': None, 'perm_id': None},
            {'arches': 'i386 x86_64 ppc ppc64', 'id': 10, 'locked': True,
             'name': 'f17-updates-pending', 'perm': None, 'perm_id': None}, ]

        buildsys.get_session.return_value.listTags.return_value = listTags
        check_signed_builds_main()

        update = models.Update.query.first()
        buildsys.get_session.assert_called_once()
        assert update.builds[0].signed == False

    @patch('bodhi.server.tasks.check_signed_builds.buildsys')
    @patch('bodhi.server.tasks.check_signed_builds.log.debug')
    def test_check_signed_builds_ignore_signed_builds(self, debug, buildsys):
        """
        The task should not touch builds already marked as signed in db.
        """
        update = models.Update.query.first()
        assert update.builds[0].signed

        self.db.commit()

        check_signed_builds_main()

        buildsys.get_session.assert_called_once()
        debug.assert_called_once_with('bodhi-2.0-1.fc17 already marked as signed')

    @patch('bodhi.server.tasks.check_signed_builds.buildsys')
    @patch('bodhi.server.tasks.check_signed_builds.log.debug')
    def test_check_signed_builds_still_not_signed(self, debug, buildsys):
        """
        The task should NOT mark signed builds if it is still pending-signing.

        Instead it should try to resubmit the builds to signing.
        """
        update = models.Update.query.first()
        update.builds[0].signed = False

        self.db.commit()

        listTags = [
            {'arches': 'i386 x86_64 ppc ppc64', 'id': 10, 'locked': True,
             'name': 'f17-updates-candidate', 'perm': None, 'perm_id': None},
            {'arches': 'i386 x86_64 ppc ppc64', 'id': 10, 'locked': True,
             'name': 'f17-updates-signing-pending', 'perm': None, 'perm_id': None}, ]

        buildsys.get_session.return_value.listTags.return_value = listTags
        check_signed_builds_main()

        update = models.Update.query.first()
        buildsys.get_session.assert_called_once()
        assert update.builds[0].signed == False
        debug.assert_called_once_with('bodhi-2.0-1.fc17 is stuck waiting to be signed, '
                                      'let\'s try again')
        buildsys.get_session.return_value.untagBuild.assert_called_once_with(
            'f17-updates-signing-pending', 'bodhi-2.0-1.fc17', force=True)
        buildsys.get_session.return_value.tagBuild.assert_called_once_with(
            'f17-updates-signing-pending', 'bodhi-2.0-1.fc17', force=True)

    @patch('bodhi.server.tasks.check_signed_builds.buildsys')
    @patch('bodhi.server.tasks.check_signed_builds.log.debug')
    def test_check_signed_builds_never_sent_to_signing(self, debug, buildsys):
        """
        When an Update is created, its builds should have been sent to pending-signing.

        If an update exists with a build which is not marked neither pending-signing or
        pending-testing, something is wrong and we must re-try to push the build
        to signing-pending.
        """
        update = models.Update.query.first()
        update.builds[0].signed = False

        self.db.commit()

        listTags = [
            {'arches': 'i386 x86_64 ppc ppc64', 'id': 10, 'locked': True,
             'name': 'f17-updates-candidate', 'perm': None, 'perm_id': None}, ]

        buildsys.get_session.return_value.listTags.return_value = listTags
        check_signed_builds_main()

        update = models.Update.query.first()
        buildsys.get_session.assert_called_once()
        assert update.builds[0].signed == False
        debug.assert_called_once_with('Oh, no! We\'ve never sent bodhi-2.0-1.fc17 for signing, '
                                      'let\'s fix it')
        buildsys.get_session.return_value.tagBuild.assert_called_once_with(
            'f17-updates-signing-pending', 'bodhi-2.0-1.fc17', force=True)

    @patch('bodhi.server.tasks.check_signed_builds.buildsys')
    @patch('bodhi.server.tasks.check_signed_builds.log.debug')
    def test_check_signed_builds_mark_signed(self, debug, buildsys):
        """
        The task should mark signed builds with correct tags.
        """
        update = models.Update.query.first()
        update.builds[0].signed = False

        self.db.commit()

        listTags = [
            {'arches': 'i386 x86_64 ppc ppc64', 'id': 10, 'locked': True,
             'name': 'f17-updates-candidate', 'perm': None, 'perm_id': None},
            {'arches': 'i386 x86_64 ppc ppc64', 'id': 10, 'locked': True,
             'name': 'f17-updates-testing-pending', 'perm': None, 'perm_id': None}, ]

        buildsys.get_session.return_value.listTags.return_value = listTags
        check_signed_builds_main()

        update = models.Update.query.first()
        buildsys.get_session.assert_called_once()
        debug.assert_called_once_with('Changing signed status of bodhi-2.0-1.fc17')
        assert update.builds[0].signed == True

    @patch('bodhi.server.tasks.check_signed_builds.buildsys')
    @patch('bodhi.server.tasks.check_signed_builds.log.debug')
    def test_check_signed_builds_obsolete_empty_update(self, debug, buildsys):
        """
        The task should obsolete an Update if there are no Builds attached to it.
        """
        update = models.Update.query.first()
        update.builds = []

        self.db.commit()

        check_signed_builds_main()

        update = models.Update.query.first()
        buildsys.get_session.assert_called_once()
        debug.assert_called_once_with(f'Obsoleting empty update {update.alias}')
        assert update.status == models.UpdateStatus.obsolete
