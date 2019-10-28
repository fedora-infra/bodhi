# Copyright © 2014-2019 Red Hat, Inc. and others.
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

from unittest import mock
import copy

import webtest

from bodhi.server import main, util
from bodhi.server.models import (Update, UpdateStatus)
from bodhi.tests.server import base


class TestExceptionView(base.BaseTestCase):
    """Test the exception_view() handler."""
    @mock.patch('bodhi.server.views.generic.log.exception')
    @mock.patch('bodhi.server.views.generic._generate_home_page_stats',
                mock.MagicMock(side_effect=RuntimeError("BOOM")))
    def test_status_500_html(self, exception):
        """Assert that a status 500 code causes the exception to get logged."""
        headers = {'Accept': 'text/html'}
        res = self.app.get('/', status=500, headers=headers)

        self.assertEqual('text/html', res.content_type)
        self.assertIn('Server Error', res)
        self.assertIn('BOOM', res)
        exception.assert_called_once_with("Error caught.  Handling HTML response.")

    @mock.patch('bodhi.server.views.generic.log.exception')
    @mock.patch('bodhi.server.views.generic._generate_home_page_stats',
                mock.MagicMock(side_effect=RuntimeError("BOOM")))
    def test_status_500_json(self, exception):
        """Assert that a status 500 code causes the exception to get logged."""
        headers = {'Content-Type': 'application/json'}
        res = self.app.get('/', status=500, headers=headers)

        self.assertEqual('application/json', res.content_type)
        self.assertEqual(
            res.json_body,
            {
                "status": "error",
                "errors": [{"location": "body", "name": "RuntimeError", "description": "BOOM"}]
            },
        )
        exception.assert_called_once_with("Error caught.  Handling JSON response.")


class TestGenericViews(base.BaseTestCase):

    def test_home(self):
        res = self.app.get('/', status=200)
        self.assertIn('Log out', res)
        self.assertIn('Fedora Update System', res)
        self.assertIn('My Active Updates', res)

        # Test the unlogged in user view
        anonymous_settings = copy.copy(self.app_settings)
        anonymous_settings.update({
            'authtkt.secret': 'whatever',
            'authtkt.secure': True,
        })
        app = webtest.TestApp(main({}, session=self.db, **anonymous_settings))
        res = app.get('/', status=200)
        self.assertIn('Create, test, and publish package updates for Fedora.', res)
        self.assertNotIn('Log out', res)
        self.assertNotIn('My Active Updates', res)

    def test_critical_update_link_home(self):
        update = Update.query.first()
        update.critpath = True
        update.status = UpdateStatus.testing
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.commit()

        res = self.app.get('/', headers={'Accept': 'text/html'})

        self.assertRegex(str(res), ('status=testing&critpath=True'))
        self.assertRegex(str(res), ('critical path updates in testing'))

    def test_markdown(self):
        res = self.app.get('/markdown', {'text': 'wat'}, status=200)
        self.assertEqual(
            res.json_body['html'],
            '<div class="markdown">'
            '<p>wat</p>'
            '</div>'
        )

    def test_markdown_with_html_blocked_tag(self):
        res = self.app.get('/markdown', {'text': '<script>bold</script>'}, status=200)
        self.assertEqual(
            res.json_body['html'],
            '<div class="markdown">'
            '&lt;script&gt;bold&lt;/script&gt;\n'
            '</div>'
        )

    def test_markdown_with_html_whitelisted_tag(self):
        res = self.app.get('/markdown', {'text': '<pre>sudo dnf install pants</pre>'}, status=200)
        self.assertEqual(
            res.json_body['html'],
            '<div class="markdown">'
            '<pre>sudo dnf install pants</pre>\n'
            '</div>'
        )

    def test_markdown_with_html_blocked_attribute(self):
        res = self.app.get('/markdown',
                           {'text': '<b onclick="alert(\'pants\')">bold</b>'},
                           status=200)
        self.assertEqual(
            res.json_body['html'],
            '<div class="markdown">'
            '<p><b>bold</b></p>'
            '</div>'
        )

    def test_markdown_with_html_whitelisted_attribute(self):
        res = self.app.get('/markdown',
                           {'text': '<img src="pants.png">'},
                           status=200)
        self.assertEqual(
            res.json_body['html'],
            '<div class="markdown">'
            '<p><img src="pants.png"></p>'
            '</div>'
        )

    def test_markdown_with_mention(self):
        res = self.app.get('/markdown', {
            'text': 'my @colleague is distinguished',
        }, status=200)
        self.assertEqual(
            res.json_body['html'],
            '<div class="markdown">'
            '<p>my <a href="http://localhost/users/colleague">@colleague</a>'
            ' is distinguished</p>'
            '</div>'
        )

    def test_markdown_with_mention_at_start(self):
        res = self.app.get('/markdown', {
            'text': '@pingou is on it',
        }, status=200)
        self.assertEqual(
            res.json_body['html'],
            '<div class="markdown">'
            '<p><a href="http://localhost/users/pingou">@pingou</a>'
            ' is on it</p>'
            "</div>"
        )

    def test_markdown_with_mention_at_start_with_comma(self):
        res = self.app.get('/markdown', {
            'text': '@kevin, thanks for that',
        }, status=200)
        self.assertEqual(
            res.json_body['html'],
            '<div class="markdown">'
            '<p><a href="http://localhost/users/kevin">@kevin</a>'
            ', thanks for that</p>'
            "</div>"
        )

    def test_markdown_with_mention_with_numbers(self):
        res = self.app.get('/markdown', {
            'text': 'I vote for @number80',
        }, status=200)
        self.assertEqual(
            res.json_body['html'],
            '<div class="markdown">'
            '<p>I vote for '
            '<a href="http://localhost/users/number80">@number80</a></p>'
            "</div>"
        )

    def test_markdown_with_unprefixed_bugzilla(self):
        res = self.app.get('/markdown', {
            'text': 'Crazy.  #12345 is still busted.',
        }, status=200)
        self.assertEqual(
            res.json_body['html'],
            '<div class="markdown">'
            '<p>Crazy.  #12345 is still busted.</p>'
            "</div>"
        )

    def test_markdown_with_prefixed_bugzilla(self):
        res = self.app.get('/markdown', {
            'text': 'Crazy.  RHBZ#12345 is still busted.',
        }, status=200)
        self.assertEqual(
            res.json_body['html'],
            '<div class="markdown">'
            '<p>Crazy.  '
            '<a href="https://bugzilla.redhat.com/show_bug.cgi?id=12345">'
            '#12345</a> is still busted.</p>'
            "</div>"
        )

    def test_markdown_with_prefixed_bugzilla_in_braces(self):
        """
        Assert that bug tracker prefixes wrapped in chars other than letters
        get matched. E.g. (RHBZ#12345)
        """
        res = self.app.get('/markdown', {
            'text': 'Crazy.  (RHBZ#12345) is still busted.',
        }, status=200)
        self.assertEqual(
            res.json_body['html'],
            '<div class="markdown">'
            '<p>Crazy.  '
            '(<a href="https://bugzilla.redhat.com/show_bug.cgi?id=12345">'
            '#12345</a>) is still busted.</p>'
            "</div>"
        )

    def test_markdown_with_unknown_prefixed_bugzilla(self):
        res = self.app.get('/markdown', {
            'text': 'Crazy.  upstream#12345 is still busted.',
        }, status=200)
        self.assertEqual(
            res.json_body['html'],
            '<div class="markdown">'
            '<p>Crazy.  upstream#12345 is still busted.</p>'
            "</div>"
        )

    def test_markdown_with_unknown_prefix_known_substring(self):
        """
        Assert that bugtracker prefixes that contain a valid prefix
        as a substring but contain other alpha characters are not
        matched
        """
        res = self.app.get('/markdown', {
            'text': 'Crazy.  aRHBZa#12345 is still busted.',
        }, status=200)
        self.assertEqual(
            res.json_body['html'],
            '<div class="markdown">'
            '<p>Crazy.  aRHBZa#12345 is still busted.</p>'
            "</div>"
        )

    def test_markdown_with_fenced_code_block(self):
        res = self.app.get('/markdown', {
            'text': '```\nsudo dnf install bodhi\n```',
        }, status=200)
        self.assertEqual(
            res.json_body['html'],
            '<div class="markdown">'
            '<pre><code>sudo dnf install bodhi\n</code></pre>\n'
            "</div>"
        )

    def test_markdown_with_email_autolink(self):
        res = self.app.get('/markdown', {
            'text': 'email me at dude@mcpants.org',
        }, status=200)
        self.assertEqual(
            res.json_body['html'],
            '<div class="markdown">'
            '<p>email me at <a href="mailto:dude@mcpants.org">dude@mcpants.org</a></p>'
            "</div>"
        )

    def test_markdown_with_email_in_lt_gt(self):
        res = self.app.get('/markdown', {
            'text': 'email me at <dude@mcpants.org>',
        }, status=200)
        self.assertEqual(
            res.json_body['html'],
            '<div class="markdown">'
            '<p>email me at <a href="mailto:dude@mcpants.org">dude@mcpants.org</a></p>'
            "</div>"
        )

    def test_markdown_with_autolink(self):
        res = self.app.get('/markdown', {
            'text': 'http://getfedora.org',
        }, status=200)
        self.assertEqual(
            res.json_body['html'],
            '<div class="markdown">'
            '<p><a href="http://getfedora.org">http://getfedora.org</a></p>'
            "</div>"
        )

    def test_markdown_with_autolink_without_http(self):
        res = self.app.get('/markdown', {
            'text': 'getfedora.org',
        }, status=200)
        self.assertEqual(
            res.json_body['html'],
            '<div class="markdown">'
            '<p><a href="http://getfedora.org">getfedora.org</a></p>'
            "</div>"
        )

    def test_latest_builds(self):
        res = self.app.get('/latest_builds')
        body = res.json_body
        self.assertIn('f17-updates', body)
        self.assertIn('f17-updates-pending', body)
        self.assertIn('f17-updates-candidate', body)
        self.assertIn('f17-updates-testing', body)
        self.assertIn('f17-updates-testing-pending', body)
        self.assertIn('f17-override', body)
        self.assertEqual(body['f17-updates'], 'TurboGears-1.0.2.2-2.fc17')

    @mock.patch("bodhi.server.buildsys.DevBuildsys.getLatestBuilds", side_effect=Exception())
    def test_latest_builds_exception(self, mock_getlatestbuilds):
        """
        Test that the latest_builds() just passes if it hits an exception
        the result here is that there should be no builds returned
        """
        res = self.app.get('/latest_builds')
        body = res.json_body

        self.assertNotIn('f17-updates', body)
        self.assertNotIn('f17-updates-pending', body)
        self.assertNotIn('f17-updates-candidate', body)
        self.assertNotIn('f17-updates-testing', body)
        self.assertNotIn('f17-updates-testing-pending', body)
        self.assertNotIn('f17-override', body)

    def test_candidate(self):
        res = self.app.get('/latest_candidates')
        body = res.json_body
        self.assertEqual(len(body), 1)

        res = self.app.get('/latest_candidates', {'package': 'TurboGears'})
        body = res.json_body
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]['nvr'], 'TurboGears-1.0.2.2-3.fc17')
        self.assertEqual(body[0]['id'], 16059)
        self.assertEqual(body[0]['owner_name'], 'lmacken')
        self.assertEqual(body[0]['package_name'], 'TurboGears')
        self.assertEqual(body[0]['release_name'], 'Fedora 17')

        res = self.app.get('/latest_candidates', {'package': 'TurboGears', 'testing': True})
        body = res.json_body
        self.assertEqual(len(body), 2)
        self.assertEqual(body[0]['nvr'], 'TurboGears-1.0.2.2-3.fc17')
        self.assertEqual(body[0]['id'], 16059)
        self.assertEqual(body[0]['owner_name'], 'lmacken')
        self.assertEqual(body[0]['package_name'], 'TurboGears')
        self.assertEqual(body[0]['release_name'], 'Fedora 17')
        self.assertEqual(body[1]['nvr'], 'TurboGears-1.0.2.2-4.fc17')
        self.assertEqual(body[1]['id'], 16060)
        self.assertEqual(body[1]['owner_name'], 'lmacken')
        self.assertEqual(body[1]['package_name'], 'TurboGears')
        self.assertEqual(body[1]['release_name'], 'Fedora 17')

        # check that we prune duplicate builds coming from koji
        with mock.patch('bodhi.server.buildsys.DevBuildsys.multiCall', create=True) as multicall:
            multicall.return_value = [[[{'owner_name': 'lmacken', 'id': 16059,
                                         'nvr': 'TurboGears-1.0.2.2-3.fc17',
                                         'package_name': 'TurboGears',
                                         'tag_name': 'f17-updates-candidate'},
                                        {'owner_name': 'lmacken', 'id': 16059,
                                         'nvr': 'TurboGears-1.0.2.2-3.fc17',
                                         'package_name': 'TurboGears',
                                         'tag_name': 'f17-updates-candidate'}]]]
            res = self.app.get('/latest_candidates', {'package': 'TurboGears'})
            body = res.json_body
            self.assertEqual(len(body), 1)
            self.assertEqual(body[0]['nvr'], 'TurboGears-1.0.2.2-3.fc17')
            self.assertEqual(body[0]['id'], 16059)
            self.assertEqual(body[0]['owner_name'], 'lmacken')
            self.assertEqual(body[0]['package_name'], 'TurboGears')
            self.assertEqual(body[0]['release_name'], 'Fedora 17')

    @mock.patch('bodhi.server.views.generic.log.error')
    @mock.patch("bodhi.server.buildsys.DevBuildsys.multiCall")
    def test_candidate_koji_error(self, mock_listTagged, log_error):
        # if the koji multicall returns errors, it returns a dict in
        # the main list containing the traceback from koji. e.g. if a
        # tag that is defined in bodhi doesnt exist on koji. This test
        # checks that we log this to the bodhi error log.

        error = {'faultcode': 1000, 'traceback': ['Traceback']}
        mock_listTagged.return_value = [error]
        self.app.get('/latest_candidates', {'package': 'TurboGears'})
        # mock_listTagged.assert_called_once()
        # self.assertEquals(res.json_body, "")
        # log_error.assert_called()
        log_error.assert_called_with(error)

    def test_get_sidetags(self):
        """Test the get_sidetags endpoint."""

        # test without any parameters
        res = self.app.get('/get_sidetags')
        body = res.json_body
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]['id'], 7777)
        self.assertEqual(body[0]['name'], 'f17-build-side-7777')
        self.assertEqual(len(body[0]['builds']), 1)
        self.assertEqual(body[0]['builds'][0]['name'], 'gnome-backgrounds')

        # test with a user parameter.
        # the actual user filtering is done on the koji side, so results
        # are the same
        res = self.app.get('/get_sidetags', {'user': 'dudemcpants'})
        body = res.json_body
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]['id'], 7777)
        self.assertEqual(body[0]['name'], 'f17-build-side-7777')
        self.assertEqual(len(body[0]['builds']), 1)
        self.assertEqual(body[0]['builds'][0]['name'], 'gnome-backgrounds')

        # test that the contains_builds flag works
        with mock.patch('bodhi.server.buildsys.DevBuildsys.multiCall', create=True) as multicall:
            multicall.side_effect = [
                [[{'id': 1234, 'name': 'side-pants', 'extra': {'sidetag_user': 'mcpants'}}]],
                [[[]]]]
            res = self.app.get('/get_sidetags', {'user': 'dudemcpants', 'contains_builds': True})

        body = res.json_body
        self.assertEqual(len(body), 0)

    def test_latest_builds_in_tag(self):
        """Test the latest_builds_in_tag endpoint."""

        # test we get a badrequest error if no tag given
        self.app.get('/latest_builds_in_tag', status=400)

        # test normal behaviour
        res = self.app.get('/latest_builds_in_tag', {'tag': 'f17-build-side-7777'})
        body = res.json_body
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]['name'], 'gnome-backgrounds')

    def test_version(self):
        res = self.app.get('/api_version')
        self.assertIn('version', res.json_body)

    def test_new_update_form(self):
        """Test the new update Form page"""

        headers = {'Accept': 'text/html'}

        # Test that a logged in user sees the New Update form
        res = self.app.get('/updates/new', headers=headers)
        self.assertIn('Creating a new update requires JavaScript', res)
        # Make sure that unspecified comes first, as it should be the default.
        regex = '<select id="suggest" name="suggest">\\n.*<option value="unspecified"'
        self.assertRegex(str(res), regex)

        # Test that the unlogged in user cannot see the New Update form
        anonymous_settings = copy.copy(self.app_settings)
        anonymous_settings.update({
            'authtkt.secret': 'whatever',
            'authtkt.secure': True,
        })
        app = webtest.TestApp(main({}, session=self.db, **anonymous_settings))
        res = app.get('/updates/new', status=403, headers=headers)
        self.assertIn('<h1>403 <small>Forbidden</small></h1>', res)
        self.assertIn('<p class="lead">Access was denied to this resource.</p>', res)

    def test_api_version(self):
        """Test the API Version JSON call"""
        res = self.app.get('/api_version')
        self.assertIn(str(util.version()), res)


class TestNotfoundView(base.BaseTestCase):
    """Test the notfound_view() handler."""
    def test_notfound(self):
        """Assert that we correctly deal with 404's."""
        res = self.app.get('/makemerich', status=404)

        self.assertIn('404 <small>Not Found</small>', res)
        self.assertIn('The resource could not be found.', res)
