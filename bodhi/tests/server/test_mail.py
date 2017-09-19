# -*- coding: utf-8 -*-
# Copyright 2017 Red Hat, Inc.
#
# This file is part of Bodhi.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""Tests for bodhi.server.mail."""
import mock

from bodhi.server import mail, models
from bodhi.tests.server import base


class TestSend(base.BaseTestCase):
    """Test the send() function."""
    @mock.patch.dict('bodhi.server.mail.config', {'smtp_server': 'smtp.example.com'})
    @mock.patch('bodhi.server.mail.smtplib.SMTP')
    def test_nvr_in_subject(self, SMTP):
        """Assert that the sent e-mail has the full NVR in the subject."""
        update = models.Update.query.all()[0]

        mail.send('fake@news.com', 'comment', update, agent='bowlofeggs')

        SMTP.assert_called_once_with('smtp.example.com')
        sendmail = SMTP.return_value.sendmail
        self.assertEqual(sendmail.call_count, 1)
        self.assertEqual(sendmail.mock_calls[0][1][0], 'updates@fedoraproject.org')
        self.assertEqual(sendmail.mock_calls[0][1][1], ['fake@news.com'])
        self.assertTrue('X-Bodhi-Update-Title: bodhi-2.0-1.fc17' in sendmail.mock_calls[0][1][2])
        self.assertTrue(
            'Subject: [Fedora Update] [comment] bodhi-2.0-1.fc17' in sendmail.mock_calls[0][1][2])
