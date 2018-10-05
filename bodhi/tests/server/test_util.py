# -*- coding: utf-8 -*-
# Copyright © 2007-2018 Red Hat, Inc. and others.
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
from xml.etree import ElementTree
import json
import os
import shutil
import subprocess
import tempfile
import unittest

import mock
import six

from bodhi.server import util, models
from bodhi.server.config import config
from bodhi.server.models import (ComposeState, TestGatingStatus, Update, UpdateRequest,
                                 UpdateSeverity)
from bodhi.tests.server import base

if six.PY2:
    import pkgdb2client


class TestAvatar(unittest.TestCase):
    """Test the avatar() function."""

    @mock.patch.dict(config, {'libravatar_enabled': False})
    def test_libravatar_disabled(self):
        """If libravatar_enabled is False, libravatar.org should be returned."""
        context = {'request': mock.MagicMock()}

        def cache_on_arguments():
            """A fake cache - we aren't testing this so let's just return f."""
            return lambda x: x

        context['request'].cache.cache_on_arguments = cache_on_arguments

        self.assertEqual(util.avatar(context, 'bowlofeggs', 50), 'libravatar.org')

    @mock.patch.dict(config,
                     {'libravatar_enabled': True, 'libravatar_dns': True, 'prefer_ssl': False})
    @mock.patch('bodhi.server.util.libravatar.libravatar_url', return_value='cool url')
    def test_libravatar_dns_set_ssl_false(self, libravatar_url):
        """Test the correct return value when libravatar_dns is set in config."""
        context = {'request': mock.MagicMock()}
        context['request'].registry.settings = config

        def cache_on_arguments():
            """A fake cache - we aren't testing this so let's just return f."""
            return lambda x: x

        context['request'].cache.cache_on_arguments = cache_on_arguments

        self.assertEqual(util.avatar(context, 'bowlofeggs', 50), 'cool url')
        libravatar_url.assert_called_once_with(openid='http://bowlofeggs.id.fedoraproject.org/',
                                               https=False, size=50, default='retro')

    @mock.patch.dict(config,
                     {'libravatar_enabled': True, 'libravatar_dns': True, 'prefer_ssl': True})
    @mock.patch('bodhi.server.util.libravatar.libravatar_url', return_value='cool url')
    def test_libravatar_dns_set_ssl_true(self, libravatar_url):
        """Test the correct return value when libravatar_dns is set in config."""
        context = {'request': mock.MagicMock()}
        context['request'].registry.settings = config

        def cache_on_arguments():
            """A fake cache - we aren't testing this so let's just return f."""
            return lambda x: x

        context['request'].cache.cache_on_arguments = cache_on_arguments

        self.assertEqual(util.avatar(context, 'bowlofeggs', 50), 'cool url')
        libravatar_url.assert_called_once_with(openid='http://bowlofeggs.id.fedoraproject.org/',
                                               https=True, size=50, default='retro')


class TestBugLink(base.BaseTestCase):
    """Tests for the bug_link() function."""
    def test_short_false_with_title(self):
        """Test a call to bug_link() with short=False on a Bug that has a title."""
        bug = mock.MagicMock()
        bug.bug_id = 1234567
        bug.title = "Lucky bug number"

        link = util.bug_link(None, bug)

        self.assertEqual(
            link,
            ("<a target='_blank' href='https://bugzilla.redhat.com/show_bug.cgi?id=1234567'>"
             "#1234567</a> Lucky bug number"))

    def test_short_false_with_title_sanitizes_safe_tags(self):
        """
        Test that a call to bug_link() with short=False on a Bug that has a title sanitizes even
        safe tags because really they should be rendered human readable.
        """
        bug = mock.MagicMock()
        bug.bug_id = 1234567
        bug.title = 'Check <b>this</b> out'

        link = util.bug_link(None, bug)

        self.assertTrue(
            link.startswith(
                ("<a target='_blank' href='https://bugzilla.redhat.com/show_bug.cgi?id=1234567'>"
                 "#1234567</a> Check &lt;b&gt;this&lt;/b&gt; out")))

    def test_short_false_with_title_sanitizes_unsafe_tags(self):
        """
        Test that a call to bug_link() with short=False on a Bug that has a title sanitizes unsafe
        tags.
        """
        bug = mock.MagicMock()
        bug.bug_id = 1473091
        bug.title = '<disk> <driver name="..."> should be optional'

        link = util.bug_link(None, bug)

        self.assertTrue(
            link.startswith(
                ("<a target='_blank' href='https://bugzilla.redhat.com/show_bug.cgi?id=1473091'>"
                 "#1473091</a> &lt;disk&gt; &lt;driver name=\"...\"&gt; should be optional")))

    def test_short_false_without_title(self):
        """Test a call to bug_link() with short=False on a Bug that has no title."""
        bug = mock.MagicMock()
        bug.bug_id = 1234567
        bug.title = None

        link = util.bug_link(None, bug)

        self.assertEqual(
            link,
            ("<a target='_blank' href='https://bugzilla.redhat.com/show_bug.cgi?id=1234567'>"
             "#1234567</a> <img class='spinner' src='static/img/spinner.gif'>"))

    def test_short_true(self):
        """Test a call to bug_link() with short=True."""
        bug = mock.MagicMock()
        bug.bug_id = 1234567
        bug.title = "Lucky bug number"

        link = util.bug_link(None, bug, True)

        self.assertEqual(
            link,
            ("<a target='_blank' href='https://bugzilla.redhat.com/show_bug.cgi?id=1234567'>"
             "#1234567</a>"))


@mock.patch('bodhi.server.util.time.sleep')
class TestCallAPI(unittest.TestCase):
    """Test the call_api() function."""

    @mock.patch('bodhi.server.util.http_session.get')
    def test_retries_failure(self, get, sleep):
        """Assert correct operation of the retries argument when they never succeed."""
        class FakeResponse(object):
            def __init__(self, status_code):
                self.status_code = status_code

            def json(self):
                return {'some': 'stuff'}

        get.side_effect = [FakeResponse(503), FakeResponse(503)]

        with self.assertRaises(RuntimeError) as exc:
            util.call_api('url', 'service_name', retries=1)

        self.assertEqual(
            str(exc.exception),
            ('Bodhi failed to get a resource from service_name at the following URL "url". The '
             'status code was "503". The error was "{\'some\': \'stuff\'}".'))
        self.assertEqual(get.mock_calls,
                         [mock.call('url', timeout=60), mock.call('url', timeout=60)])
        sleep.assert_called_once_with(1)

    @mock.patch('bodhi.server.util.http_session.get')
    def test_retries_success(self, get, sleep):
        """Assert correct operation of the retries argument when they succeed eventually."""
        class FakeResponse(object):
            def __init__(self, status_code):
                self.status_code = status_code

            def json(self):
                return {'some': 'stuff'}

        get.side_effect = [FakeResponse(503), FakeResponse(200)]

        res = util.call_api('url', 'service_name', retries=1)

        self.assertEqual(res, {'some': 'stuff'})
        self.assertEqual(get.mock_calls,
                         [mock.call('url', timeout=60), mock.call('url', timeout=60)])
        sleep.assert_called_once_with(1)


class TestGreenwaveUnsatisfiedRequirementsHTML(base.BaseTestCase):
    """Test the greenwave_unsatisfied_requirements_html() function."""

    def test_no_unsatisfied_requirements(self):
        u = Update.query.first()
        u.greenwave_unsatisfied_requirements = None

        self.assertEqual(util.greenwave_unsatisfied_requirements_html(None, u), '')

    def test_unsatisfied_requirements(self):
        u = Update.query.first()
        u.greenwave_unsatisfied_requirements = json.dumps([
            {'testcase': 'dist.rpmdeplint',
             'item': {'item': 'python-rpdb-0.1.6-7.fc27', 'type': 'koji_build'},
             'type': 'test-result-missing', 'scenario': None},
            {'testcase': 'dist.rpmdeplint',
             'item': {'original_spec_nvr': 'python-rpdb-0.1.6-7.fc27'},
             'type': 'test-result-missing', 'scenario': None},
            {'testcase': 'dist.rpmdeplint',
             'item': {'item': 'FEDORA-2018-6b448bbc48', 'type': 'bodhi_update'},
             'type': 'test-result-missing', 'scenario': None},
            {'testcase': 'dist.rpmdeplint',
             'item': {'item': 'bodhi-3.6.1-1.fc28', 'type': 'koji_build'},
             'type': 'test-result-missing', 'scenario': None},
            {'testcase': 'dist.someothertest',
             'item': {'item': 'bodhi-3.6.1-1.fc28', 'type': 'koji_build'},
             'type': 'test-result-sucks', 'scenario': None},
            {'testcase': 'dist.anothertest',
             'item': {'item': 'python-rpdb-0.1.6-7.fc27', 'type': 'koji_build'},
             'type': 'test-result-missing', 'scenario': None}])

        html = util.greenwave_unsatisfied_requirements_html(None, u)

        # The bodhi_update type gets ignored in the HTML for now (we might change this later).
        # We can't assert the order of the divs in the html because they are different between
        # Python 2 and 3. We also don't really care what order they appear in anyway, so let's just
        # make sure they appear in the resulting HTML.
        self.assertTrue(html.startswith('<div>Unsatisfied requirements:'))
        self.assertIn(
            ('<div>test-result-missing:  '
             'dist.rpmdeplint (python-rpdb-0.1.6-7.fc27, bodhi-3.6.1-1.fc28),  '
             'dist.anothertest (python-rpdb-0.1.6-7.fc27)</div>'),
            html)
        self.assertIn(
            '<div>test-result-sucks:  dist.someothertest (bodhi-3.6.1-1.fc28)</div>', html)
        # Let's make sure we close things out correctly.
        self.assertTrue(html.endswith('</div></div>'))


class TestKarma2HTML(unittest.TestCase):
    """Test the karma2html() function."""

    def test_karma_danger(self):
        """If karma is less than -2, the danger class should be used."""
        self.assertEqual(util.karma2html(mock.MagicMock(), -3),
                         "<span class='label label-danger'>-3</span>")


class TestMemoized(unittest.TestCase):
    """Test the memoized class."""

    def test_caching(self):
        """Ensure that caching works for hashable parameters."""
        return_value = True

        @util.memoized
        def some_function(arg):
            return return_value

        self.assertIs(some_function(42), True)
        # Let's flip the value of return_value just to make sure the cached value is used and not
        # the new value.
        return_value = False
        # It should still return True, indicating that some_function() was not called again.
        self.assertIs(some_function(42), True)

    def test_caching_different_args(self):
        """Ensure that caching works for hashable parameters, but is sensitive to arguments."""
        return_value = True

        @util.memoized
        def some_function(arg):
            return return_value

        self.assertIs(some_function(42), True)
        # Let's flip the value of return_value just to make sure the cached value is not used.
        return_value = False
        # It should return False because the argument is different.
        self.assertIs(some_function(41), False)

    def test_dont_cache_lists(self):
        """memoized should not cache calls with list arguments."""
        return_value = True

        @util.memoized
        def some_function(arg):
            return return_value

        self.assertIs(some_function(['some', 'list']), True)
        # Let's flip the value of return_value just to make sure it isn't cached.
        return_value = False
        self.assertIs(some_function(['some', 'list']), False)

    def test___get__(self):
        """__get__() should allow us to set the function as an attribute of another object."""
        @util.memoized
        def some_function(arg):
            """Some docblock"""
            return 42

        class some_class(object):
            thing = some_function

        self.assertEqual(some_class().thing(), 42)


class TestNoAutoflush(unittest.TestCase):
    """Test the no_autoflush context manager."""
    def test_autoflush_disabled(self):
        """Test correct behavior when autoflush is disabled."""
        session = mock.MagicMock()
        session.autoflush = False

        with util.no_autoflush(session):
            self.assertFalse(session.autoflush)

        # autoflush should still be False since that was the starting condition.
        self.assertFalse(session.autoflush)

    def test_autoflush_enabled(self):
        """Test correct behavior when autoflush is enabled."""
        session = mock.MagicMock()
        session.autoflush = True

        with util.no_autoflush(session):
            self.assertFalse(session.autoflush)

        # autoflush should again be True since that was the starting condition.
        self.assertTrue(session.autoflush)


class TestPushToBatchedOrStableButton(base.BaseTestCase):
    """Test the push_to_batched_or_stable_button() function."""
    def test_request_is_batched(self):
        """The function should render a Push to Stable button if the request is batched."""
        u = Update.query.all()[0]
        u.request = UpdateRequest.batched

        a = util.push_to_batched_or_stable_button(None, u)

        self.assertTrue('id="stable"' in a)
        self.assertTrue('</span> Push to Stable</a>' in a)

    def test_request_is_none(self):
        """The function should render a Push to Stable button if the request is None."""
        u = Update.query.all()[0]
        u.request = None

        a = util.push_to_batched_or_stable_button(None, u)

        self.assertTrue('id="batched"' in a)
        self.assertTrue('</span> Push to Batched</a>' in a)

    def test_request_is_other(self):
        """The function should return '' request is something else, like testing."""
        u = Update.query.all()[0]
        u.request = UpdateRequest.testing

        a = util.push_to_batched_or_stable_button(None, u)

        self.assertEqual(a, '')

    def test_request_is_stable(self):
        """The function should render a Push to Batched button if the request is stable."""
        u = Update.query.all()[0]
        u.request = UpdateRequest.stable

        a = util.push_to_batched_or_stable_button(None, u)

        self.assertTrue('id="batched"' in a)
        self.assertTrue('</span> Push to Batched</a>' in a)

    def test_severity_is_urgent(self):
        """The function should render a Push to Stable button if the severity is urgent."""
        u = Update.query.all()[0]
        u.severity = UpdateSeverity.urgent

        a = util.push_to_batched_or_stable_button(None, u)

        self.assertTrue('id="stable"' in a)
        self.assertTrue('</span> Push to Stable</a>' in a)


class TestComposeState2HTML(unittest.TestCase):
    """Assert correct behavior from the composestate2html() function."""
    def test_requested(self):
        """Assert correct return value with the requested state."""
        self.assertEqual(util.composestate2html(None, ComposeState.requested),
                         "<span class='label label-primary'>Requested</span>")

    def test_pending(self):
        """Assert correct return value with the pending state."""
        self.assertEqual(util.composestate2html(None, ComposeState.pending),
                         "<span class='label label-primary'>Pending</span>")

    def test_initializing(self):
        """Assert correct return value with the initializing state."""
        self.assertEqual(util.composestate2html(None, ComposeState.initializing),
                         "<span class='label label-warning'>Initializing</span>")

    def test_updateinfo(self):
        """Assert correct return value with the updateinfo state."""
        self.assertEqual(util.composestate2html(None, ComposeState.updateinfo),
                         "<span class='label label-warning'>Generating updateinfo.xml</span>")

    def test_punging(self):
        """Assert correct return value with the punging state."""
        self.assertEqual(util.composestate2html(None, ComposeState.punging),
                         "<span class='label label-warning'>Waiting for Pungi to finish</span>")

    def test_notifying(self):
        """Assert correct return value with the notifying state."""
        self.assertEqual(util.composestate2html(None, ComposeState.notifying),
                         "<span class='label label-warning'>Sending notifications</span>")

    def test_success(self):
        """Assert correct return value with the success state."""
        self.assertEqual(util.composestate2html(None, ComposeState.success),
                         "<span class='label label-success'>Success</span>")

    def test_failed(self):
        """Assert correct return value with the failed state."""
        self.assertEqual(util.composestate2html(None, ComposeState.failed),
                         "<span class='label label-danger'>Failed</span>")

    def test_cleaning(self):
        """Assert correct return value with the cleaning state."""
        self.assertEqual(util.composestate2html(None, ComposeState.cleaning),
                         "<span class='label label-warning'>Cleaning old composes</span>")


class TestCanWaiveTestResults(base.BaseTestCase):
    """Test the can_waive_test_results() function."""

    @mock.patch.dict('bodhi.server.util.config',
                     {'test_gating.required': True, 'waiverdb.access_token': None})
    def test_access_token_undefined(self):
        """If Bodhi is not configured with an access token, the result should be False."""
        u = Update.query.all()[0]
        u.test_gating_status = TestGatingStatus.failed
        u.status = models.UpdateStatus.testing

        self.assertFalse(util.can_waive_test_results(None, u))

    @mock.patch.dict('bodhi.server.util.config',
                     {'test_gating.required': True, 'waiverdb.access_token': 'secret'})
    def test_can_waive_test_results(self):
        u = Update.query.all()[0]
        u.test_gating_status = TestGatingStatus.failed
        u.status = models.UpdateStatus.testing
        self.assertTrue(util.can_waive_test_results(None, u))

    @mock.patch.dict('bodhi.server.util.config',
                     {'test_gating.required': False, 'waiverdb.access_token': 'secret'})
    def test_gating_required_false(self):
        """
        Assert that it should return false if test_gating is not enabled, even if
        other conditions are met.
        """
        u = Update.query.all()[0]
        u.test_gating_status = TestGatingStatus.failed
        u.status = models.UpdateStatus.testing
        self.assertFalse(util.can_waive_test_results(None, u))

    @mock.patch.dict('bodhi.server.util.config',
                     {'test_gating.required': True, 'waiverdb.access_token': 'secret'})
    def test_all_tests_passed(self):
        """
        Assert that it should return false if all tests passed, even if
        other conditions are met.
        """
        u = Update.query.all()[0]
        u.test_gating_status = TestGatingStatus.passed
        u.status = models.UpdateStatus.testing
        self.assertFalse(util.can_waive_test_results(None, u))

    @mock.patch.dict('bodhi.server.util.config',
                     {'test_gating.required': True, 'waiverdb.access_token': 'secret'})
    def test_update_is_stable(self):
        """
        Assert that it should return false if the update is stable, even if
        other conditions are met.
        """
        u = Update.query.all()[0]
        u.test_gating_status = TestGatingStatus.failed
        u.status = models.UpdateStatus.stable
        self.assertFalse(util.can_waive_test_results(None, u))


class TestPagesList(unittest.TestCase):
    """Test the pages_list() function."""

    def test_page_in_middle(self):
        """Test for when the current page is in the middle of the pages."""
        val = util.pages_list(mock.MagicMock(), 6, 20)

        self.assertEqual(val, range(2, 11))

    def test_page_near_end(self):
        """Test for when the current page is near the end of the pages."""
        val = util.pages_list(mock.MagicMock(), 6, 7)

        self.assertEqual(val, range(1, 8))


class TestSanityCheckRepodata(unittest.TestCase):
    """Test the sanity_check_repodata() function."""

    def setUp(self):
        self.tempdir = tempfile.mkdtemp('bodhi')

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_correct_yum_repo(self):
        """No Exception should be raised if the repo is normal."""
        base.mkmetadatadir(self.tempdir)

        # No exception should be raised here.
        util.sanity_check_repodata(self.tempdir, repo_type='yum')

    def test_correct_module_repo(self):
        """No Exception should be raised if the repo is a normal module repo."""
        base.mkmetadatadir(self.tempdir)
        # We need to add a modules tag to repomd.
        repomd_path = os.path.join(self.tempdir, 'repodata', 'repomd.xml')
        repomd_tree = ElementTree.parse(repomd_path)
        ElementTree.register_namespace('', 'http://linux.duke.edu/metadata/repo')
        root = repomd_tree.getroot()
        ElementTree.SubElement(root, 'data', type='modules')
        for data in root.findall('{http://linux.duke.edu/metadata/repo}data'):
            # module repos don't have drpms or comps.
            if data.attrib['type'] in ('group', 'prestodelta'):
                root.remove(data)
        repomd_tree.write(repomd_path, encoding='UTF-8', xml_declaration=True)

        # No exception should be raised here.
        util.sanity_check_repodata(self.tempdir, repo_type='module')

    def test_updateinfo_empty_tags(self):
        """RepodataException should be raised if <id/> is found in updateinfo."""
        updateinfo = os.path.join(self.tempdir, 'updateinfo.xml')
        with open(updateinfo, 'w') as uinfo:
            uinfo.write('<id/>')
        base.mkmetadatadir(self.tempdir, updateinfo=updateinfo)

        with self.assertRaises(util.RepodataException) as exc:
            util.sanity_check_repodata(self.tempdir, repo_type='yum')

        self.assertEqual(str(exc.exception), 'updateinfo.xml.gz contains empty ID tags')

    def test_comps_invalid_notxml(self):
        """RepodataException should be raised if comps is invalid."""
        comps = os.path.join(self.tempdir, 'comps.xml')
        with open(comps, 'w') as uinfo:
            uinfo.write('this is not even xml')
        base.mkmetadatadir(self.tempdir, comps=comps)

        with self.assertRaises(util.RepodataException) as exc:
            util.sanity_check_repodata(self.tempdir, repo_type='yum')

        self.assertEqual(str(exc.exception), 'Comps file unable to be parsed')

    def test_comps_invalid_nonsense(self):
        """RepodataException should be raised if comps is invalid."""
        comps = os.path.join(self.tempdir, 'comps.xml')
        with open(comps, 'w') as uinfo:
            uinfo.write('<whatever />')
        base.mkmetadatadir(self.tempdir, comps=comps)

        with self.assertRaises(util.RepodataException) as exc:
            util.sanity_check_repodata(self.tempdir, repo_type='yum')

        self.assertEqual(str(exc.exception), 'Comps file empty')

    def test_repomd_missing_updateinfo(self):
        """If the updateinfo data tag is missing in repomd.xml, an Exception should be raised."""
        base.mkmetadatadir(self.tempdir)
        repomd_path = os.path.join(self.tempdir, 'repodata', 'repomd.xml')
        repomd = ElementTree.parse(repomd_path)
        ElementTree.register_namespace('', 'http://linux.duke.edu/metadata/repo')
        root = repomd.getroot()
        # Find the <data type="updateinfo"> tag and delete it
        for data in root.findall('{http://linux.duke.edu/metadata/repo}data'):
            if data.attrib['type'] == 'updateinfo':
                root.remove(data)
        repomd.write(repomd_path, encoding='UTF-8', xml_declaration=True)

        with self.assertRaises(util.RepodataException) as exc:
            util.sanity_check_repodata(self.tempdir, repo_type='yum')

        self.assertEqual(str(exc.exception), 'Required part not in repomd.xml: updateinfo')

    def test_source_true(self):
        """It should not fail source repos for missing prestodelta or comps."""
        base.mkmetadatadir(self.tempdir)
        repomd_path = os.path.join(self.tempdir, 'repodata', 'repomd.xml')
        repomd = ElementTree.parse(repomd_path)
        ElementTree.register_namespace('', 'http://linux.duke.edu/metadata/repo')
        root = repomd.getroot()
        for data in root.findall('{http://linux.duke.edu/metadata/repo}data'):
            # Source repos don't have drpms or comps.
            if data.attrib['type'] in ('group', 'prestodelta'):
                root.remove(data)
        repomd.write(repomd_path, encoding='UTF-8', xml_declaration=True)

        # No exception should be raised.
        util.sanity_check_repodata(self.tempdir, repo_type='source')


class TestType2Icon(unittest.TestCase):
    """Test the type2icon() function."""

    def test_consonant(self):
        """Test type2icon() with a kind that starts with a consonant."""
        self.assertEqual(
            util.type2icon(None, 'security'),
            ("<span class='label label-danger' data-toggle='tooltip' "
             "title='This is a security update'><i class='fa fa-fw fa-shield'></i></span>"))

    def test_vowel(self):
        """Test type2icon() with a kind that starts with a vowel."""
        self.assertEqual(
            util.type2icon(None, 'enhancement'),
            ("<span class='label label-success' data-toggle='tooltip' "
             "title='This is an enhancement update'><i class='fa fa-fw fa-bolt'></i></span>"))


class TestUpdate2HTML(base.BaseTestCase):
    """Test the update2html() function."""

    def test_long_title(self):
        """If the update's title is too long, it should be trimmed."""
        context = {'request': mock.MagicMock()}
        context['request'].registry.settings = {'max_update_length_for_ui': 10}
        context['request'].route_url.return_value = 'https://example.com/'
        update = models.Update.query.first()

        html = util.update2html(context, update)

        # The update's title gets trimmed to 10 characters and 3 dots.
        self.assertEqual(html, '<a href="https://example.com/">bodhi-2.0-...</a>')


class TestUtils(base.BaseTestCase):

    def test_config(self):
        assert config.get('sqlalchemy.url'), config
        assert config['sqlalchemy.url'], config

    @mock.patch.dict(util.config, {'critpath.type': None, 'critpath_pkgs': ['kernel', 'glibc']})
    def test_get_critpath_components_dummy(self):
        """ Ensure that critpath packages can be found using the hardcoded
        list.
        """
        self.assertEqual(util.get_critpath_components(), ['kernel', 'glibc'])

    if six.PY2:
        @mock.patch.object(pkgdb2client.PkgDB, 'get_critpath_packages')
        @mock.patch.dict(util.config, {
            'critpath.type': 'pkgdb',
            'pkgdb_url': 'http://domain.local'
        })
        def test_get_critpath_components_pkgdb_success(self, mock_get_critpath):
            """ Ensure that critpath packages can be found using PkgDB.
            """
            # A subset of critpath packages
            critpath_pkgs = [
                'pth',
                'xorg-x11-server-utils',
                'giflib',
                'basesystem'
            ]
            mock_get_critpath.return_value = {
                'pkgs': {
                    'f20': critpath_pkgs
                }
            }
            pkgs = util.get_critpath_components('f20')
            assert critpath_pkgs == pkgs, pkgs

    @mock.patch('bodhi.server.util.http_session')
    @mock.patch.dict(util.config, {
        'critpath.type': 'pdc',
        'pdc_url': 'http://domain.local'
    })
    def test_get_critpath_components_pdc_error(self, session):
        """ Ensure an error is thrown in Bodhi if there is an error in PDC
        getting the critpath packages.
        """
        session.get.return_value.status_code = 500
        session.get.return_value.json.return_value = \
            {'error': 'some error'}
        try:
            util.get_critpath_components('f25')
            assert False, 'Did not raise a RuntimeError'
        except RuntimeError as error:
            actual_error = six.text_type(error)
        # We are not testing the whole error message because there is no
        # guarantee of the ordering of the GET parameters.
        assert 'Bodhi failed to get a resource from PDC' in actual_error
        assert 'The status code was "500".' in actual_error

    @mock.patch('bodhi.server.util.log')
    @mock.patch.dict(util.config, {'critpath.type': None, 'critpath_pkgs': ['kernel', 'glibc']})
    def test_get_critpath_components_not_pdc_not_rpm(self, mock_log):
        """ Ensure a warning is logged when the critpath system is not pdc
        and the type of components to search for is not rpm.
        """
        pkgs = util.get_critpath_components('f25', 'module')
        assert 'kernel' in pkgs, pkgs
        warning = ('The critpath.type of "module" does not support searching '
                   'for non-RPM components')
        mock_log.warning.assert_called_once_with(warning)

    @mock.patch('bodhi.server.util.http_session')
    @mock.patch.dict(util.config, {'critpath.type': 'pdc', 'pdc_url': 'http://domain.local'})
    def test_get_critpath_components_pdc_paging_exception(self, session):
        """Ensure that an Exception is raised if components are used and the response is paged."""
        pdc_url = 'http://domain.local/rest_api/v1/component-branches/?page_size=1'
        pdc_next_url = '{0}&page=2'.format(pdc_url)
        session.get.return_value.status_code = 200
        session.get.return_value.json.side_effect = [
            {
                'count': 2,
                'next': pdc_next_url,
                'previous': None,
                'results': [
                    {
                        'active': True,
                        'critical_path': True,
                        'global_component': 'gcc',
                        'id': 6,
                        'name': 'f26',
                        'slas': [],
                        'type': 'rpm'
                    }]}]

        with self.assertRaises(Exception) as exc:
            util.get_critpath_components('f26', 'rpm', frozenset(['gcc']))

        self.assertEqual(str(exc.exception), 'We got paging when requesting a single component?!')
        self.assertEqual(
            session.get.mock_calls,
            [mock.call(
                ('http://domain.local/rest_api/v1/component-branches/?active=true'
                 '&critical_path=true&fields=global_component&name=f26&page_size=100&type=rpm'
                 '&global_component=gcc'),
                timeout=60),
             mock.call().json()])

    @mock.patch('bodhi.server.util.http_session')
    @mock.patch.dict(util.config, {'critpath.type': 'pdc', 'pdc_url': 'http://domain.local'})
    def test_get_critpath_pdc_with_components(self, session):
        """Test the components argument to get_critpath_components()."""
        session.get.return_value.status_code = 200
        session.get.return_value.json.return_value = {
            'count': 1,
            'next': None,
            'previous': None,
            'results': [{
                'active': True,
                'critical_path': True,
                'global_component': 'gcc',
                'id': 6,
                'name': 'f26',
                'slas': [],
                'type': 'rpm'}]}

        pkgs = util.get_critpath_components('f26', 'rpm', frozenset(['gcc']))

        self.assertEqual(pkgs, ['gcc'])
        self.assertEqual(
            session.get.mock_calls,
            [mock.call(
                ('http://domain.local/rest_api/v1/component-branches/?active=true'
                 '&critical_path=true&fields=global_component&name=f26&page_size=100&type=rpm'
                 '&global_component=gcc'),
                timeout=60),
             mock.call().json()])

    @mock.patch('bodhi.server.util.http_session')
    @mock.patch.dict(util.config, {
        'critpath.type': 'pdc',
        'pdc_url': 'http://domain.local'
    })
    def test_get_critpath_components_pdc_success(self, session):
        """ Ensure that critpath packages can be found using PDC.
        """
        pdc_url = \
            'http://domain.local/rest_api/v1/component-branches/?page_size=1'
        pdc_next_url = '{0}&page=2'.format(pdc_url)
        session.get.return_value.status_code = 200
        session.get.return_value.json.side_effect = [
            {
                'count': 2,
                'next': pdc_next_url,
                'previous': None,
                'results': [
                    {
                        'active': True,
                        'critical_path': True,
                        'global_component': 'gcc',
                        'id': 6,
                        'name': 'f26',
                        'slas': [],
                        'type': 'rpm'
                    }
                ]
            },
            {
                'count': 2,
                'next': None,
                'previous': pdc_url,
                'results': [
                    {
                        'active': True,
                        'critical_path': True,
                        'global_component': 'python',
                        'id': 7,
                        'name': 'f26',
                        'slas': [],
                        'type': 'rpm'
                    }
                ]
            }
        ]
        pkgs = util.get_critpath_components('f26')
        assert 'python' in pkgs and 'gcc' in pkgs, pkgs
        # At least make sure it called the next url to cycle through the pages.
        # We can't verify all the calls made because the URL GET parameters
        # in the URL may have different orders based on the system/Python
        # version.
        session.get.assert_called_with(pdc_next_url, timeout=60)
        # Verify there were two GET requests made and two .json() calls
        assert session.get.call_count == 2, session.get.call_count
        assert session.get.return_value.json.call_count == 2, \
            session.get.return_value.json.call_count

    @mock.patch('bodhi.server.util.http_session')
    def test_pagure_api_get(self, session):
        """ Ensure that an API request to Pagure works as expected.
        """
        session.get.return_value.status_code = 200
        expected_json = {
            "access_groups": {
                "admin": [],
                "commit": [],
                "ticket": []
            },
            "access_users": {
                "admin": [],
                "commit": [],
                "owner": [
                    "mprahl"
                ],
                "ticket": []
            },
            "close_status": [],
            "custom_keys": [],
            "date_created": "1494947106",
            "description": "Python",
            "fullname": "rpms/python",
            "id": 2,
            "milestones": {},
            "name": "python",
            "namespace": "rpms",
            "parent": None,
            "priorities": {},
            "tags": [],
            "user": {
                "fullname": "Matt Prahl",
                "name": "mprahl"
            }
        }
        session.get.return_value.json.return_value = expected_json
        rv = util.pagure_api_get('http://domain.local/api/0/rpms/python')
        assert rv == expected_json, rv

    @mock.patch('bodhi.server.util.http_session')
    def test_pagure_api_get_non_500_error(self, session):
        """ Ensure that an API request to Pagure that raises an error that is
        not a 500 error returns the actual error message from the JSON.
        """
        session.get.return_value.status_code = 404
        session.get.return_value.json.return_value = {
            "error": "Project not found",
            "error_code": "ENOPROJECT"
        }
        try:
            util.pagure_api_get('http://domain.local/api/0/rpms/python')
            assert False, 'Did not raise a RuntimeError'
        except RuntimeError as error:
            actual_error = six.text_type(error)

        expected_error = (
            'Bodhi failed to get a resource from Pagure at the following URL '
            '"http://domain.local/api/0/rpms/python". The status code was '
            '"404". The error was "Project not found".')
        assert actual_error == expected_error, actual_error

    @mock.patch('bodhi.server.util.http_session')
    def test_pagure_api_get_500_error(self, session):
        """ Ensure that an API request to Pagure that triggers a 500 error
        raises the expected error message.
        """
        session.get.return_value.status_code = 500
        try:
            util.pagure_api_get('http://domain.local/api/0/rpms/python')
            assert False, 'Did not raise a RuntimeError'
        except RuntimeError as error:
            actual_error = six.text_type(error)

        expected_error = (
            'Bodhi failed to get a resource from Pagure at the following URL '
            '"http://domain.local/api/0/rpms/python". The status code was '
            '"500".')
        assert actual_error == expected_error, actual_error

    @mock.patch('bodhi.server.util.http_session')
    def test_pagure_api_get_non_500_error_no_json(self, session):
        """ Ensure that an API request to Pagure that raises an error that is
        not a 500 error and has no JSON returns an error.
        """
        session.get.return_value.status_code = 404
        session.get.return_value.json.side_effect = ValueError('Not JSON')
        try:
            util.pagure_api_get('http://domain.local/api/0/rpms/python')
            assert False, 'Did not raise a RuntimeError'
        except RuntimeError as error:
            actual_error = six.text_type(error)

        expected_error = (
            'Bodhi failed to get a resource from Pagure at the following URL '
            '"http://domain.local/api/0/rpms/python". The status code was '
            '"404". The error was "".')
        assert actual_error == expected_error, actual_error

    @mock.patch('bodhi.server.util.http_session')
    def test_pdc_api_get(self, session):
        """ Ensure that an API request to PDC works as expected.
        """
        session.get.return_value.status_code = 200
        expected_json = {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": 1,
                    "sla": "security_fixes",
                    "branch": {
                        "id": 1,
                        "name": "2.7",
                        "global_component": "python",
                        "type": "rpm",
                        "active": True,
                        "critical_path": True
                    },
                    "eol": "2018-04-27"
                }
            ]
        }
        session.get.return_value.json.return_value = expected_json
        rv = util.pdc_api_get(
            'http://domain.local/rest_api/v1/component-branch-slas/')
        assert rv == expected_json, rv

    @mock.patch('bodhi.server.util.http_session')
    def test_pdc_api_get_500_error(self, session):
        """ Ensure that an API request to PDC that triggers a 500 error
        raises the expected error message.
        """
        session.get.return_value.status_code = 500
        try:
            util.pdc_api_get(
                'http://domain.local/rest_api/v1/component-branch-slas/')
            assert False, 'Did not raise a RuntimeError'
        except RuntimeError as error:
            actual_error = six.text_type(error)

        expected_error = (
            'Bodhi failed to get a resource from PDC at the following URL '
            '"http://domain.local/rest_api/v1/component-branch-slas/". The '
            'status code was "500".')
        assert actual_error == expected_error, actual_error

    @mock.patch('bodhi.server.util.http_session')
    def test_pdc_api_get_non_500_error(self, session):
        """ Ensure that an API request to PDC that raises an error that is
        not a 500 error returns the returned JSON.
        """
        session.get.return_value.status_code = 404
        session.get.return_value.json.return_value = {
            "detail": "Not found."
        }
        try:
            util.pdc_api_get(
                'http://domain.local/rest_api/v1/component-branch-slas/3/')
            assert False, 'Did not raise a RuntimeError'
        except RuntimeError as error:
            actual_error = six.text_type(error)

        expected_error = (
            'Bodhi failed to get a resource from PDC at the following URL '
            '"http://domain.local/rest_api/v1/component-branch-slas/3/". The '
            'status code was "404". The error was '
            '"{\'detail\': \'Not found.\'}".')
        assert actual_error == expected_error, actual_error

    @mock.patch('bodhi.server.util.http_session')
    def test_pdc_api_get_non_500_error_no_json(self, session):
        """ Ensure that an API request to PDC that raises an error that is
        not a 500 error and has no JSON returns an error.
        """
        session.get.return_value.status_code = 404
        session.get.return_value.json.side_effect = ValueError('Not JSON')
        try:
            util.pdc_api_get(
                'http://domain.local/rest_api/v1/component-branch-slas/3/')
            assert False, 'Did not raise a RuntimeError'
        except RuntimeError as error:
            actual_error = six.text_type(error)

        expected_error = (
            'Bodhi failed to get a resource from PDC at the following URL '
            '"http://domain.local/rest_api/v1/component-branch-slas/3/". The '
            'status code was "404". The error was "".')
        assert actual_error == expected_error, actual_error

    @mock.patch('bodhi.server.util.http_session')
    def test_greenwave_api_post(self, session):
        """ Ensure that a POST request to Greenwave works as expected.
        """
        session.post.return_value.status_code = 200
        expected_json = {
            'policies_satisfied': True,
            'summary': 'All tests passed',
            'applicable_policies': ['taskotron_release_critical_tasks'],
            'unsatisfied_requirements': []
        }
        session.post.return_value.json.return_value = expected_json
        data = {
            'product_version': 'fedora-26',
            'decision_context': 'bodhi_push_update_stable',
            'subjects': ['foo-1.0.0-1.f26']
        }
        decision = util.greenwave_api_post('http://domain.local/api/v1.0/decision',
                                           data)
        assert decision == expected_json, decision

    @mock.patch('bodhi.server.util.http_session')
    def test_greenwave_api_post_500_error(self, session):
        """ Ensure that a POST request to Greenwave that triggers a 500 error
        raises the expected error message.
        """
        session.post.return_value.status_code = 500
        try:
            data = {
                'product_version': 'fedora-26',
                'decision_context': 'bodhi_push_update_stable',
                'subjects': ['foo-1.0.0-1.f26']
            }
            util.greenwave_api_post('http://domain.local/api/v1.0/decision',
                                    data)
            assert False, 'Did not raise a RuntimeError'
        except RuntimeError as error:
            actual_error = six.text_type(error)

        expected_error = (
            'Bodhi failed to send POST request to Greenwave at the following URL '
            '"http://domain.local/api/v1.0/decision". The status code was "500".')
        assert actual_error == expected_error, actual_error

    @mock.patch('bodhi.server.util.http_session')
    def test_greenwave_api_post_non_500_error(self, session):
        """ Ensure that a POST request to Greenwave that raises an error that is
        not a 500 error returns the returned JSON.
        """
        session.post.return_value.status_code = 404
        session.post.return_value.json.return_value = {
            "message": "Not found."
        }
        try:
            data = {
                'product_version': 'fedora-26',
                'decision_context': 'bodhi_push_update_stable',
                'subjects': ['foo-1.0.0-1.f26']
            }
            util.greenwave_api_post('http://domain.local/api/v1.0/decision',
                                    data)
            assert False, 'Did not raise a RuntimeError'
        except RuntimeError as error:
            actual_error = six.text_type(error)

        expected_error = (
            'Bodhi failed to send POST request to Greenwave at the following URL '
            '"http://domain.local/api/v1.0/decision". The status code was "404". '
            'The error was "{\'message\': \'Not found.\'}".')
        assert actual_error == expected_error, actual_error

    @mock.patch('bodhi.server.util.http_session')
    def test_greenwave_api_post_non_500_error_no_json(self, session):
        """ Ensure that a POST request to Greenwave that raises an error that is
        not a 500 error and has no JSON returns an error.
        """
        session.post.return_value.status_code = 404
        session.post.return_value.json.side_effect = ValueError('Not JSON')
        try:
            data = {
                'product_version': 'fedora-26',
                'decision_context': 'bodhi_push_update_stable',
                'subjects': ['foo-1.0.0-1.f26']
            }
            util.greenwave_api_post('http://domain.local/api/v1.0/decision',
                                    data)
            assert False, 'Did not raise a RuntimeError'
        except RuntimeError as error:
            actual_error = six.text_type(error)

        expected_error = (
            'Bodhi failed to send POST request to Greenwave at the following URL '
            '"http://domain.local/api/v1.0/decision". The status code was "404". '
            'The error was "".')
        assert actual_error == expected_error, actual_error

    @mock.patch('bodhi.server.util.http_session')
    def test_waiverdb_api_post(self, session):
        """ Ensure that a POST request to WaiverDB works as expected.
        """
        session.post.return_value.status_code = 200
        expected_json = {
            'comment': 'this is not true!',
            'id': 15,
            'product_version': 'fedora-26',
            'result_subject': {'productmd.compose.id': 'Fedora-9000-19700101.n.18'},
            'result_testcase': 'compose.install_no_user',
            'timestamp': '2017-11-28T17:42:04.209638',
            'username': 'foo',
            'waived': True,
            'proxied_by': 'bodhi'
        }
        session.post.return_value.json.return_value = expected_json
        data = {
            'product_version': 'fedora-26',
            'waived': True,
            'proxy_user': 'foo',
            'result_subject': {'productmd.compose.id': 'Fedora-9000-19700101.n.18'},
            'result_testcase': 'compose.install_no_user',
            'comment': 'this is not true!'
        }
        waiver = util.waiverdb_api_post('http://domain.local/api/v1.0/waivers/',
                                        data)
        assert waiver == expected_json, waiver

    def test_markup_escapes(self):
        """Ensure we correctly parse markdown & escape HTML"""
        text = (
            '# this is a header\n'
            'this is some **text**\n'
            '<script>alert("pants")</script>'
        )
        html = util.markup(None, text)
        assert html == (
            '<div class="markdown"><h1>this is a header</h1>\n'
            '<p>this is some <strong>text</strong>\n'
            '&lt;script&gt;alert("pants")&lt;/script&gt;</p></div>'
        ), html

    @mock.patch('bodhi.server.util.bleach.clean', return_value='cleaned text')
    @mock.patch.object(util.bleach, '__version__', u'1.4.3')
    def test_markup_with_bleach_1(self, clean):
        """Use mocking to ensure we correctly use the bleach 1 API."""
        text = '# this is a header\nthis is some **text**'

        result = util.markup(None, text)

        self.assertEqual(result, 'cleaned text')
        expected_text = (
            u'<div class="markdown"><h1>this is a header</h1>\n<p>this is some <strong>text'
            u'</strong></p></div>')
        expected_tags = [
            "h1", "h2", "h3", "h4", "h5", "h6", "b", "i", "strong", "em", "tt", "p", "br", "span",
            "div", "blockquote", "code", "hr", "pre", "ul", "ol", "li", "dd", "dt", "img", "a"]
        # The bleach 1 API shoudl get these attrs passed.
        clean.assert_called_once_with(expected_text, tags=expected_tags,
                                      attributes=["src", "href", "alt", "title", "class"])

    @mock.patch('bodhi.server.util.bleach.clean', return_value='cleaned text')
    @mock.patch.object(util.bleach, '__version__', u'2.0')
    def test_markup_with_bleach_2(self, clean):
        """Use mocking to ensure we correctly use the bleach 2 API."""
        text = '# this is a header\nthis is some **text**'

        result = util.markup(None, text)

        self.assertEqual(result, 'cleaned text')
        expected_text = (
            u'<div class="markdown"><h1>this is a header</h1>\n<p>this is some <strong>text'
            u'</strong></p></div>')
        expected_tags = [
            "h1", "h2", "h3", "h4", "h5", "h6", "b", "i", "strong", "em", "tt", "p", "br", "span",
            "div", "blockquote", "code", "hr", "pre", "ul", "ol", "li", "dd", "dt", "img", "a"]
        expected_attributes = {
            "img": ["src", "alt", "title"], "a": ["href", "alt", "title"], "div": ["class"]}
        # The bleach 2 API shoudl get these attrs passed.
        clean.assert_called_once_with(expected_text, tags=expected_tags,
                                      attributes=expected_attributes)

    def test_rpm_header(self):
        h = util.get_rpm_header('libseccomp')
        assert h['name'] == 'libseccomp', h

    def test_rpm_header_exception(self):
        try:
            util.get_rpm_header('raise-exception')
            assert False
        except Exception:
            pass

    def test_rpm_header_not_found(self):
        try:
            util.get_rpm_header("do-not-find-anything")
            assert False
        except ValueError:
            pass

    def test_cmd_failure(self):
        try:
            util.cmd('false')
            assert False
        except Exception:
            pass

    def test_sorted_updates_async_removal(self):
        u1 = self.create_update(['bodhi-1.0-1.fc24', 'somepkg-2.0-3.fc24'])
        u2 = self.create_update(['somepkg-1.0-3.fc24'])

        us = [u1, u2]
        sync, async_ = util.sorted_updates(us)

        assert len(sync) == 2
        assert len(async_) == 0
        assert sync[0] == u2
        assert sync[1] == u1

    def test_sorted_updates_general(self):
        u1 = self.create_update(['bodhi-1.0-1.fc24', 'somepkg-2.0-3.fc24'])
        u2 = self.create_update(['somepkg-1.0-3.fc24'])
        u3 = self.create_update(['pkga-1.0-3.fc24'])
        u4 = self.create_update(['pkgb-1.0-3.fc24'])
        u5 = self.create_update(['pkgc-1.0-3.fc24', 'pkgd-1.0-3.fc24'])
        u6 = self.create_update(['pkgd-2.0-3.fc24'])

        us = [u1, u2, u3, u4, u5, u6]
        sync, async_ = util.sorted_updates(us)

        # This ordering is because:
        #  u5 contains pkgd-1.0, which is < pkgdb-2.0 from u6
        #  u2 contains somepkg-1.0, which is < somepkg-2.0 from u1
        self.assertEqual(sync, [u5, u6, u2, u1])
        # This ordering is because neither u3 nor u4 overlap with other updates
        self.assertEqual(async_, [u3, u4])

    def test_sorted_updates_insanity(self):
        """
        Test that sorted_updates is predictable in the case of insanity.

        The updates as submitted should never be done, as this is a purely insane combination,
        but we want to make sure that we at least don't crash, and produce predictable ordering.
        """
        u1 = self.create_update(['bodhi-1.0-1.fc24', 'somepkg-2.0-3.fc24'])
        u2 = self.create_update(['pkga-1.0-3.fc24', 'pkgb-2.0-1.fc24'])  # Newer pkgb, thus >u3
        u3 = self.create_update(['pkga-2.0-1.fc24', 'pkgb-1.0-3.fc24'])  # Newer pkga, thus >u2

        us = [u1, u2, u3]
        sync, async_ = util.sorted_updates(us)

        # This ordering is actually insane, since both u2 and u3 contain a newer and an older build
        self.assertEqual(sync, [u2, u3])
        # This ordering is because u1 doesn't overlap with anything
        self.assertEqual(async_, [u1])

    def test_splitter(self):
        splitlist = util.splitter(["build-0.1", "build-0.2"])
        self.assertEqual(splitlist, ['build-0.1', 'build-0.2'])

        splitcommastring = util.splitter("build-0.1, build-0.2")
        self.assertEqual(splitcommastring, ['build-0.1', 'build-0.2'])

        splitspacestring = util.splitter("build-0.1 build-0.2")
        self.assertEqual(splitspacestring, ['build-0.1', 'build-0.2'])

    @mock.patch('bodhi.server.util.requests.get')
    @mock.patch('bodhi.server.util.log.exception')
    def test_taskotron_results_non_200(self, log_exception, mock_get):
        '''Query should stop when error is encountered'''
        mock_get.return_value.status_code = 500
        mock_get.return_value.json.return_value = {'error': 'some error'}
        settings = {'resultsdb_api_url': ''}

        list(util.taskotron_results(settings))

        log_exception.assert_called_once()
        msg = log_exception.call_args[0][0]
        self.assertIn('Problem talking to', msg)
        self.assertIn('status code was %r' % mock_get.return_value.status_code, msg)

    @mock.patch('bodhi.server.util.requests.get')
    def test_taskotron_results_paging(self, mock_get):
        '''Next pages should be retrieved'''
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.side_effect = [
            {'data': ['datum1', 'datum2'],
             'next': 'url2'},
            {'data': ['datum3'],
             'next': None}
        ]
        settings = {'resultsdb_api_url': ''}

        results = list(util.taskotron_results(settings))

        self.assertEqual(results, ['datum1', 'datum2', 'datum3'])
        self.assertEqual(mock_get.return_value.json.call_count, 2)
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(mock_get.call_args[0][0], 'url2')
        self.assertEqual(mock_get.call_args[1]['timeout'], 60)

    @mock.patch('bodhi.server.util.requests.get')
    @mock.patch('bodhi.server.util.log.debug')
    def test_taskotron_results_max_queries(self, log_debug, mock_get):
        '''Only max_queries should be performed'''
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            'data': ['datum'],
            'next': 'next_url'
        }
        settings = {'resultsdb_api_url': ''}

        results = list(util.taskotron_results(settings, max_queries=5))

        self.assertEqual(mock_get.call_count, 5)
        self.assertEqual(results, ['datum'] * 5)
        self.assertIn('Too many result pages, aborting at', log_debug.call_args[0][0])


class TestCMDFunctions(base.BaseTestCase):
    @mock.patch('bodhi.server.log.debug')
    @mock.patch('bodhi.server.log.error')
    @mock.patch('subprocess.Popen')
    def test_err_nonzero_return_code(self, mock_popen, mock_error, mock_debug):
        """
        Ensures proper behavior when there is err output and the exit code isn't 0.
        See https://github.com/fedora-infra/bodhi/issues/1412
        """
        mock_popen.return_value = mock.Mock()
        mock_popen_obj = mock_popen.return_value
        mock_popen_obj.communicate.return_value = ('output', 'error')
        mock_popen_obj.returncode = 1

        util.cmd(['/bin/echo'], '"home/imgs/catpix"')

        mock_popen.assert_called_once_with(
            ['/bin/echo'], cwd='"home/imgs/catpix"', stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            shell=False)

        self.assertEqual(
            mock_error.mock_calls,
            [mock.call('/bin/echo returned a non-0 exit code: 1'), mock.call('output\nerror')])
        mock_debug.assert_called_once_with('Running /bin/echo')
        self.assertEqual(
            mock_error.mock_calls,
            [mock.call('/bin/echo returned a non-0 exit code: 1'), mock.call('output\nerror')])

    @mock.patch('bodhi.server.log.debug')
    @mock.patch('bodhi.server.log.error')
    @mock.patch('subprocess.Popen')
    def test_no_err_zero_return_code(self, mock_popen, mock_error, mock_debug):
        """
        Ensures proper behavior when there is no err output and the exit code is 0.
        See https://github.com/fedora-infra/bodhi/issues/1412
        """
        mock_popen.return_value = mock.Mock()
        mock_popen_obj = mock_popen.return_value
        mock_popen_obj.communicate.return_value = ('output', None)
        mock_popen_obj.returncode = 0

        util.cmd(['/bin/echo'], '"home/imgs/catpix"')

        mock_popen.assert_called_once_with(
            ['/bin/echo'], cwd='"home/imgs/catpix"', stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            shell=False)
        mock_error.assert_not_called()
        self.assertEqual(mock_debug.mock_calls,
                         [mock.call('Running /bin/echo'), mock.call('output\nNone')])

    @mock.patch('bodhi.server.log.debug')
    @mock.patch('bodhi.server.log.error')
    @mock.patch('subprocess.Popen')
    def test_err_zero_return_code(self, mock_popen, mock_error, mock_debug):
        """
        Ensures proper behavior when there is err output, but the exit code is 0.
        See https://github.com/fedora-infra/bodhi/issues/1412
        """
        mock_popen.return_value = mock.Mock()
        mock_popen_obj = mock_popen.return_value
        mock_popen_obj.communicate.return_value = ('output', 'error')
        mock_popen_obj.returncode = 0

        util.cmd(['/bin/echo'], '"home/imgs/catpix"')

        mock_popen.assert_called_once_with(
            ['/bin/echo'], cwd='"home/imgs/catpix"', stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            shell=False)
        mock_error.assert_not_called()
        mock_debug.assert_called_with('output\nerror')


class TestTransactionalSessionMaker(base.BaseTestCase):
    """This class contains tests on the TransactionalSessionMaker class."""
    @mock.patch('bodhi.server.util.log.exception')
    @mock.patch('bodhi.server.util.Session')
    def test___call___fail_rollback_failure(self, Session, log_exception):
        """
        Ensure that __call__() correctly handles the failure case when rolling back itself fails.

        If the wrapped code raises an Exception *and* session.rollback() itself raises an Exception,
        __call__() should log the failure to roll back, and then close and remove the Session, and
        should raise the original Exception again.
        """
        tsm = util.TransactionalSessionMaker()
        exception = ValueError("u can't do that lol")
        # Now let's make it super bad by having rollback raise an Exception
        Session.return_value.rollback.side_effect = IOError("lol now u can't connect to the db")

        with self.assertRaises(ValueError) as exc_context:
            with tsm():
                raise exception

        log_exception.assert_called_once_with(
            'An Exception was raised while rolling back a transaction.')
        self.assertTrue(exc_context.exception is exception)
        self.assertEqual(Session.return_value.commit.call_count, 0)
        Session.return_value.rollback.assert_called_once_with()
        Session.return_value.close.assert_called_once_with()
        Session.remove.assert_called_once_with()

    @mock.patch('bodhi.server.util.log.exception')
    @mock.patch('bodhi.server.util.Session')
    def test___call___fail_rollback_success(self, Session, log_exception):
        """
        Ensure that __call__() correctly handles the failure case when rolling back is successful.

        If the wrapped code raises an Exception, __call__() should roll back the transaction, and
        close and remove the Session, and should raise the original Exception again.
        """
        tsm = util.TransactionalSessionMaker()
        exception = ValueError("u can't do that lol")

        with self.assertRaises(ValueError) as exc_context:
            with tsm():
                raise exception

        self.assertEqual(log_exception.call_count, 0)
        self.assertTrue(exc_context.exception is exception)
        self.assertEqual(Session.return_value.commit.call_count, 0)
        Session.return_value.rollback.assert_called_once_with()
        Session.return_value.close.assert_called_once_with()
        Session.remove.assert_called_once_with()

    @mock.patch('bodhi.server.util.log.exception')
    @mock.patch('bodhi.server.util.Session')
    def test___call___success(self, Session, log_exception):
        """
        Ensure that __call__() correctly handles the success case.

        __call__() should commit the transaction, and close and remove the Session upon a successful
        operation.
        """
        tsm = util.TransactionalSessionMaker()

        with tsm():
            pass

        self.assertEqual(log_exception.call_count, 0)
        self.assertEqual(Session.return_value.rollback.call_count, 0)
        Session.return_value.commit.assert_called_once_with()
        Session.return_value.close.assert_called_once_with()
        Session.remove.assert_called_once_with()
