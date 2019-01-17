# Copyright 2014-2018 Red Hat, Inc. and others.
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

from datetime import datetime
import copy
import mock
import re

import webtest

from bodhi.server import main, util
from bodhi.server.models import (
    User, Update, Release, ReleaseState, UpdateStatus, UpdateType)
from bodhi.server.views import generic
from bodhi.tests.server import base


class TestExceptionView(base.BaseTestCase):
    """Test the exception_view() handler."""
    @mock.patch('bodhi.server.views.generic.log.exception')
    @mock.patch('bodhi.server.views.metrics.compute_ticks_and_data',
                mock.MagicMock(side_effect=RuntimeError("BOOM")))
    def test_status_500(self, exception):
        """Assert that a status 500 code causes the exception to get logged."""
        res = self.app.get('/metrics', status=500)

        self.assertIn('Server Error', res)
        self.assertIn('BOOM', res)
        exception.assert_called_once_with("Error caught.  Handling HTML response.")


class TestGenericViews(base.BaseTestCase):

    def test_home(self):
        res = self.app.get('/', status=200)
        self.assertIn('Log out', res)
        self.assertIn('Fedora Update System', res)

    def test_critical_update_link_home(self):
        update = Update.query.first()
        update.critpath = True
        update.status = UpdateStatus.testing
        self.db.commit()

        res = self.app.get('/', headers={'Accept': 'text/html'})

        self.assertRegexpMatches(str(res), ('status=testing&critpath=True.*'
                                 'Latest Critical Path Updates in Need of Testing'))

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

    def test_metrics(self):
        res = self.app.get('/metrics')
        self.assertIn('$.plot', res)

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
        self.assertEqual(body, [])

        res = self.app.get('/latest_candidates', {'package': 'TurboGears'})
        body = res.json_body
        self.assertEqual(len(body), 2)
        self.assertEqual(body[0]['nvr'], 'TurboGears-1.0.2.2-2.fc17')
        self.assertEqual(body[0]['id'], 16058)
        self.assertEqual(body[1]['nvr'], 'TurboGears-1.0.2.2-3.fc17')
        self.assertEqual(body[1]['id'], 16059)

        res = self.app.get('/latest_candidates', {'package': 'TurboGears', 'testing': True})
        body = res.json_body
        self.assertEqual(len(body), 3)
        self.assertEqual(body[0]['nvr'], 'TurboGears-1.0.2.2-2.fc17')
        self.assertEqual(body[0]['id'], 16058)
        self.assertEqual(body[1]['nvr'], 'TurboGears-1.0.2.2-3.fc17')
        self.assertEqual(body[1]['id'], 16059)
        self.assertEqual(body[2]['nvr'], 'TurboGears-1.0.2.2-4.fc17')
        self.assertEqual(body[2]['id'], 16060)

    def test_version(self):
        res = self.app.get('/api_version')
        self.assertIn('version', res.json_body)

    def test_popup_toggle(self):
        """Check that the toggling of pop-up notifications works"""
        # first we check that popups are enabled by default
        res = self.app.get('/')
        self.assertIn('Disable popups', res)

        # toggle popups off
        self.app.post('/popup_toggle')

        # now check popups are off
        res = self.app.get('/')
        self.assertIn('Enable popups', res)

        # test that the unlogged in user cannot toggle popups
        anonymous_settings = copy.copy(self.app_settings)
        anonymous_settings.update({
            'authtkt.secret': 'whatever',
            'authtkt.secure': True,
        })
        app = webtest.TestApp(main({}, session=self.db, **anonymous_settings))
        res = app.post('/popup_toggle', status=403)
        self.assertIn('<h1>403 <small>Forbidden</small></h1>', res)
        self.assertIn('<p class="lead">Access was denied to this resource.</p>', res)

    def test_new_override_form(self):
        """Test the New Override form page"""

        # Test that the New Override form shows when logged in
        res = self.app.get('/overrides/new')
        self.assertIn('<span>New Buildroot Override Form Requires JavaScript</span>', res)

        # Test that the unlogged in user cannot see the New Override form
        anonymous_settings = copy.copy(self.app_settings)
        anonymous_settings.update({
            'authtkt.secret': 'whatever',
            'authtkt.secure': True,
        })
        app = webtest.TestApp(main({}, session=self.db, **anonymous_settings))
        res = app.get('/overrides/new', status=403)
        self.assertIn('<h1>403 <small>Forbidden</small></h1>', res)
        self.assertIn('<p class="lead">Access was denied to this resource.</p>', res)

    def test_new_update_form(self):
        """Test the new update Form page"""

        # Test that a logged in user sees the New Update form
        res = self.app.get('/updates/new')
        self.assertIn('Creating a new update requires JavaScript', res)
        # Make sure that unspecified comes first, as it should be the default.
        regex = r''
        for value in ('unspecified', 'reboot', 'logout'):
            regex = regex + r'name="suggest" value="{}".*'.format(value)
        self.assertTrue(re.search(regex, res.body.decode('utf8').replace('\n', ' ')))

        # Test that the unlogged in user cannot see the New Update form
        anonymous_settings = copy.copy(self.app_settings)
        anonymous_settings.update({
            'authtkt.secret': 'whatever',
            'authtkt.secure': True,
        })
        app = webtest.TestApp(main({}, session=self.db, **anonymous_settings))
        res = app.get('/updates/new', status=403)
        self.assertIn('<h1>403 <small>Forbidden</small></h1>', res)
        self.assertIn('<p class="lead">Access was denied to this resource.</p>', res)

    def test_api_version(self):
        """Test the API Version JSON call"""
        res = self.app.get('/api_version')
        self.assertIn(str(util.version()), res)


class TestFrontpageView(base.BaseTestCase):
    def setUp(self, *args, **kwargs):
        super(TestFrontpageView, self).setUp(*args, **kwargs)

        def _add_updates(updateslist, user, release, packagesuffix):
            """Private method that adds updates to the database for testing

            """
            count = 0
            for i in updateslist:
                for j in i[1]:
                    for k in range(0, j[1]):
                        update = Update(
                            title=u'bodhi-2.0-1%s.%s' % (str(count), packagesuffix),
                            user=user,
                            status=i[0],
                            type=j[0],
                            notes=u'Useful details!',
                            release=release,
                            date_submitted=datetime(1984, 11, 2),
                            requirements=u'rpmlint',
                            stable_karma=3,
                            unstable_karma=-3,
                        )
                        self.db.add(update)
                        self.db.flush()
                        count = count + 1

        user2 = User(name=u'dudemcpants')
        self.db.flush()
        self.db.add(user2)

        release = Release(
            name=u'F18', long_name=u'Fedora 18',
            id_prefix=u'FEDORA', version=u'18',
            dist_tag=u'f18', stable_tag=u'f18-updates',
            testing_tag=u'f18-updates-testing',
            candidate_tag=u'f18-updates-candidate',
            pending_signing_tag=u'f18-updates-testing-signing',
            pending_testing_tag=u'f18-updates-testing-pending',
            pending_stable_tag=u'f18-updates-pending',
            override_tag=u'f18-override',
            branch=u'f18', state=ReleaseState.pending)
        self.db.add(release)

        currentrelease = self.db.query(Release).filter_by(name=u'F17').one()
        addedupdates = [[UpdateStatus.pending,
                         [[UpdateType.security, 5],
                          [UpdateType.bugfix, 4],
                          [UpdateType.enhancement, 3],
                          [UpdateType.newpackage, 2]]],
                        [UpdateStatus.testing,
                         [[UpdateType.security, 15],
                          [UpdateType.bugfix, 14],
                          [UpdateType.enhancement, 13],
                          [UpdateType.newpackage, 12]]],
                        [UpdateStatus.stable,
                         [[UpdateType.security, 25],
                          [UpdateType.bugfix, 24],
                          [UpdateType.enhancement, 23],
                          [UpdateType.newpackage, 22]]]]
        _add_updates(addedupdates, user2, currentrelease, "fc17")

        pendingrelease = self.db.query(Release).filter_by(name=u'F18').one()
        addedupdates2 = [[UpdateStatus.pending,
                         [[UpdateType.security, 2],
                          [UpdateType.bugfix, 2],
                          [UpdateType.enhancement, 2],
                          [UpdateType.newpackage, 2]]],
                         [UpdateStatus.testing,
                          [[UpdateType.security, 3],
                           [UpdateType.bugfix, 3],
                           [UpdateType.enhancement, 3],
                           [UpdateType.newpackage, 3]]],
                         [UpdateStatus.stable,
                          [[UpdateType.security, 4],
                           [UpdateType.bugfix, 4],
                           [UpdateType.enhancement, 4],
                           [UpdateType.newpackage, 4]]]]
        _add_updates(addedupdates2, user2, pendingrelease, "fc18")
        self.db.flush()
        # Clear the caches
        Release._tag_cache = None
        generic._generate_home_page_stats.invalidate()

    def test_home_counts(self):
        """Test the frontpage update counts"""
        res = self.app.get('/', status=200)

        # Assert that pending updates counts in a current release are displayed properly
        # Note the bug update count here is one more than what we generate above
        # because there is already a single update in the test data.
        self.assertIn("""<div class="front-count-total">
          <a href="http://localhost/updates/?releases=F17&amp;status=pending">
          15
          </a>
        </div>
        <h4>updates pending</h4>
          <a class="text-danger" title="Security updates" data-toggle="tooltip" href=\
"http://localhost/updates/?releases=F17&amp;status=pending&amp;type=security">
            <span class="fa fa-shield"></span> 5
          </a>
          <a class="text-warning" title="Bugfix updates" data-toggle="tooltip" href=\
"http://localhost/updates/?releases=F17&amp;status=pending&amp;type=bugfix">
            <span class="fa fa-bug"></span> 5
          </a>
          <a class="text-success" title="Enhancement updates" data-toggle="tooltip" href=\
"http://localhost/updates/?releases=F17&amp;status=pending&amp;type=enhancement">
            <span class="fa fa-bolt text-success"></span> 3
          </a>
          <a class="text-primary" title="New Package updates" data-toggle="tooltip" href=\
"http://localhost/updates/?releases=F17&amp;status=pending&amp;type=newpackage">
            <span class="fa fa-archive"></span> 2
          </a>""", res)

        # Assert that testing updates counts in a current release are displayed properly
        self.assertIn("""<div class="front-count-total">
          <a href="http://localhost/updates/?releases=F17&amp;status=testing">
          54
          </a>
          </div>
        <h4>updates in testing</h4>
        <a class="text-danger" title="Security updates" data-toggle="tooltip" \
href="http://localhost/updates/?releases=F17&amp;status=testing&amp;type=security">
          <span class="fa fa-shield"></span> 15
        </a>
        <a class="text-warning" title="Bugfix updates" data-toggle="tooltip" \
href="http://localhost/updates/?releases=F17&amp;status=testing&amp;type=bugfix">
          <span class="fa fa-bug"></span> 14
        </a>
        <a class="text-success" title="Enhancement updates" data-toggle="tooltip" \
href="http://localhost/updates/?releases=F17&amp;status=testing&amp;type=enhancement">
          <span class="fa fa-bolt"></span> 13
        </a>
        <a class="text-primary" title="New Package updates" data-toggle="tooltip" \
href="http://localhost/updates/?releases=F17&amp;status=testing&amp;type=newpackage">
          <span class="fa fa-archive"></span> 12
        </a>""", res)

        # Assert that stable updates counts in a current release are displayed properly
        self.assertIn("""<div class="front-count-total">
          <a href="http://localhost/updates/?releases=F17&amp;status=stable">
          94
          </a>
        </div>
        <h4>updates in stable</h4>
        <a class="text-danger" title="Security updates" data-toggle="tooltip" href="\
http://localhost/updates/?releases=F17&amp;status=stable&amp;type=security">
        <span class="fa fa-shield"></span> 25
        </a>
        <a class="text-warning" title="Bugfix updates" data-toggle="tooltip" href="\
http://localhost/updates/?releases=F17&amp;status=stable&amp;type=bugfix">
        <span class="fa fa-bug"></span> 24
        </a>
        <a class="text-success" title="Enhancement updates" data-toggle="tooltip" href="\
http://localhost/updates/?releases=F17&amp;status=stable&amp;type=enhancement">
        <span class="fa fa-bolt"></span> 23
        </a>
        <a class="text-primary" title="New Package updates" data-toggle="tooltip" href="\
http://localhost/updates/?releases=F17&amp;status=stable&amp;type=newpackage">
        <span class="fa fa-archive"></span> 22
        </a>""", res)

        # Assert that pending updates counts in a pending release are displayed properly
        self.assertIn("""<div class="front-count-total">
          <a href="http://localhost/updates/?releases=F18&amp;status=pending">
          8
          </a>
        </div>
        <h4>updates pending</h4>
          <a class="text-danger" title="Security updates" data-toggle="tooltip" href="\
http://localhost/updates/?releases=F18&amp;status=pending&amp;type=security">
            <span class="fa fa-shield"></span> 2
          </a>
          <a class="text-warning" title="Bugfix updates" data-toggle="tooltip" href="\
http://localhost/updates/?releases=F18&amp;status=pending&amp;type=bugfix">
            <span class="fa fa-bug"></span> 2
          </a>
          <a class="text-success" title="Enhancement updates" data-toggle="tooltip" href="\
http://localhost/updates/?releases=F18&amp;status=pending&amp;type=enhancement">
            <span class="fa fa-bolt text-success"></span> 2
          </a>
          <a class="text-primary" title="New Package updates" data-toggle="tooltip" href="\
http://localhost/updates/?releases=F18&amp;status=pending&amp;type=newpackage">
            <span class="fa fa-archive"></span> 2
          </a>""", res)

        # Assert that testing updates counts in a pending release are displayed properly
        self.assertIn("""<div class="front-count-total">
          <a href="http://localhost/updates/?releases=F18&amp;status=testing">
          12
          </a>
          </div>
        <h4>updates in testing</h4>
        <a class="text-danger" title="Security updates" data-toggle="tooltip" \
href="http://localhost/updates/?releases=F18&amp;status=testing&amp;type=security">
          <span class="fa fa-shield"></span> 3
        </a>
        <a class="text-warning" title="Bugfix updates" data-toggle="tooltip" \
href="http://localhost/updates/?releases=F18&amp;status=testing&amp;type=bugfix">
          <span class="fa fa-bug"></span> 3
        </a>
        <a class="text-success" title="Enhancement updates" data-toggle="tooltip" \
href="http://localhost/updates/?releases=F18&amp;status=testing&amp;type=enhancement">
          <span class="fa fa-bolt"></span> 3
        </a>
        <a class="text-primary" title="New Package updates" data-toggle="tooltip" \
href="http://localhost/updates/?releases=F18&amp;status=testing&amp;type=newpackage">
          <span class="fa fa-archive"></span> 3
        </a>""", res)

        # Assert that stable updates counts in a pending release are displayed properly
        self.assertIn("""<div class="front-count-total">
          <a href="http://localhost/updates/?releases=F18&amp;status=stable">
          16
          </a>
        </div>
        <h4>updates in stable</h4>
        <a class="text-danger" title="Security updates" data-toggle="tooltip" href="\
http://localhost/updates/?releases=F18&amp;status=stable&amp;type=security">
        <span class="fa fa-shield"></span> 4
        </a>
        <a class="text-warning" title="Bugfix updates" data-toggle="tooltip" href="\
http://localhost/updates/?releases=F18&amp;status=stable&amp;type=bugfix">
        <span class="fa fa-bug"></span> 4
        </a>
        <a class="text-success" title="Enhancement updates" data-toggle="tooltip" href="\
http://localhost/updates/?releases=F18&amp;status=stable&amp;type=enhancement">
        <span class="fa fa-bolt"></span> 4
        </a>
        <a class="text-primary" title="New Package updates" data-toggle="tooltip" href="\
http://localhost/updates/?releases=F18&amp;status=stable&amp;type=newpackage">
        <span class="fa fa-archive"></span> 4
        </a>""", res)

        # Assert that the title for a pending release has the "prerelease" label
        self.assertIn("""      <h3>
        <a class="notblue" href="http://localhost/releases/F18">
  Fedora 18
        </a>
          <span class="label label-default">prerelease</span>
      </h3>""", res)


class TestNotfoundView(base.BaseTestCase):
    """Test the notfound_view() handler."""
    def test_notfound(self):
        """Assert that we correctly deal with 404's."""
        res = self.app.get('/makemerich', status=404)

        self.assertIn('404 <small>Not Found</small>', res)
        self.assertIn('The resource could not be found.', res)
