# Copyright 2011-2019 Red Hat, Inc. and others.
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
"""This module contains tests for bodhi.server.services.user."""
from datetime import datetime, timedelta, timezone
from html import escape
from unittest import mock
from urllib import parse as urlparse
import copy
import re
import textwrap
import time

from fedora_messaging import api
from fedora_messaging import testing as fml_testing
from webtest import TestApp
import koji
import pytest
import requests

from bodhi.messages.schemas import base as base_schemas
from bodhi.messages.schemas import update as update_schemas
from bodhi.server import buildsys, main
from bodhi.server.config import config
from bodhi.server.exceptions import BodhiException, LockedUpdateException
from bodhi.server.models import (
    Build,
    BuildrootOverride,
    Compose,
    Group,
    ModulePackage,
    Release,
    ReleaseState,
    RpmBuild,
    RpmPackage,
    TestGatingStatus,
    Update,
    UpdateRequest,
    UpdateSeverity,
    UpdateStatus,
    UpdateSuggestion,
    UpdateType,
    User,
)
from bodhi.server.util import call_api

from ..base import BasePyTestCase


class TestSetEmailsPref(BasePyTestCase):
    """
    This class contains tests for the set_emails_pref() function.
    """
    def test_unauthenticated_endpoint_call(self, *args):
        """Check that endpoint is forbidden if user is not authenticated"""
        post_data = dict(emails_preference='off',
                         csrf_token=self.app.get('/csrf').json_body['csrf_token'])
        app = TestApp(main({}, session=self.db, **self.app_settings))
        app.post_json(f'/set_emails_pref', post_data, status=403)

    def test_bad_value_posted(self):
        """Posting a bad option should raise an error"""
        user = self.db.query(User).first()
        assert user.receive_emails == True
        with mock.patch('bodhi.server.Session.remove'):
            app = TestApp(main({}, testing=user.name, session=self.db, **self.app_settings))
            post_data = dict(emails_preference='BLAH',
                             csrf_token=app.get('/csrf').json_body['csrf_token'])
        res = app.post_json(f'/set_emails_pref', post_data, status=400)
        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == '"BLAH" is not one of on, off'
        assert user.receive_emails == True

    @mock.patch('bodhi.server.services.user.log.info')
    @pytest.mark.parametrize('set_status', ('on', 'off'))
    def test_set_preference(self, log_info, set_status):
        """Check a successful preference change"""
        user = self.db.query(User).first()
        if set_status == 'on':
            user.receive_emails = False
            self.db.commit()
        else:
            assert user.receive_emails == True
        with mock.patch('bodhi.server.Session.remove'):
            app = TestApp(main({}, testing=user.name, session=self.db, **self.app_settings))
            post_data = dict(emails_preference=set_status,
                             csrf_token=app.get('/csrf').json_body['csrf_token'])
        app.post_json(f'/set_emails_pref', post_data, status=200)
        if set_status == 'on':
            assert user.receive_emails == True
        else:
            assert user.receive_emails == False
        log_info.assert_any_call(f"User {user.name} set their email preference to {set_status}")

    @mock.patch('bodhi.server.services.user.log.warning')
    @pytest.mark.parametrize('set_status', ('on', 'off'))
    def test_set_preference_already_set(self, log_warning, set_status):
        """Trying to set the preference to the current value returns an error"""
        user = self.db.query(User).first()
        if set_status == 'on':
            assert user.receive_emails == True
        else:
            user.receive_emails = False
            self.db.commit()
        with mock.patch('bodhi.server.Session.remove'):
            app = TestApp(main({}, testing=user.name, session=self.db, **self.app_settings))
            post_data = dict(emails_preference=set_status,
                             csrf_token=app.get('/csrf').json_body['csrf_token'])
        res = app.post_json(f'/set_emails_pref', post_data, status=400)
        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == (
            f"User's email preference already set to {set_status}"
        )
        if set_status == 'on':
            assert user.receive_emails == True
        else:
            assert user.receive_emails == False
        log_warning.assert_any_call(f"User {user.name} email preference already set to {set_status}")
