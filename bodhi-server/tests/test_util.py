# Copyright © 2007-2019 Red Hat, Inc. and others.
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
from xml.etree import ElementTree
import gzip
import os
import shutil
import subprocess
import tempfile

from webob.multidict import MultiDict
import bleach
import pkg_resources
import pytest

from bodhi.server import models, util
from bodhi.server.config import config
from bodhi.server.exceptions import RepodataException
from bodhi.server.models import TestGatingStatus, Update

from . import base


class TestAvatar:
    """Test the avatar() function."""

    def test_libravatar_disabled(self):
        """If libravatar_enabled is False, libravatar.org should be returned."""
        config['libravatar_enabled'] = False
        context = {'request': mock.MagicMock()}

        def cache_on_arguments():
            """A fake cache - we aren't testing this so let's just return f."""
            return lambda x: x

        context['request'].cache.cache_on_arguments = cache_on_arguments

        assert util.avatar(context, 'bowlofeggs', 50) == 'libravatar.org'

    @mock.patch('bodhi.server.util.libravatar.libravatar_url', return_value='cool url')
    def test_libravatar_dns_set_ssl_false(self, libravatar_url):
        """Test the correct return value when libravatar_dns is set in config."""
        config.update({
            'libravatar_enabled': True,
            'libravatar_dns': True,
            'libravatar_prefer_tls': False,
        })
        context = {'request': mock.MagicMock()}
        context['request'].registry.settings = config

        def cache_on_arguments():
            """A fake cache - we aren't testing this so let's just return f."""
            return lambda x: x

        context['request'].cache.cache_on_arguments = cache_on_arguments

        assert util.avatar(context, 'bowlofeggs', 50) == 'cool url'
        openid_user_host = config['openid_template'].format(username='bowlofeggs')
        libravatar_url.assert_called_once_with(openid=f'http://{openid_user_host}/',
                                               https=False, size=50, default='retro')

    @mock.patch('bodhi.server.util.libravatar.libravatar_url', return_value='cool url')
    def test_libravatar_dns_set_ssl_true(self, libravatar_url):
        """Test the correct return value when libravatar_dns is set in config."""
        config.update({
            'libravatar_enabled': True,
            'libravatar_dns': True,
            'libravatar_prefer_tls': True,
        })
        context = {'request': mock.MagicMock()}
        context['request'].registry.settings = config

        def cache_on_arguments():
            """A fake cache - we aren't testing this so let's just return f."""
            return lambda x: x

        context['request'].cache.cache_on_arguments = cache_on_arguments

        assert util.avatar(context, 'bowlofeggs', 50) == 'cool url'
        openid_user_host = config['openid_template'].format(username='bowlofeggs')
        libravatar_url.assert_called_once_with(openid=f'http://{openid_user_host}/',
                                               https=True, size=50, default='retro')


class TestBugLink:
    """Tests for the bug_link() function."""
    def test_short_false_with_title(self):
        """Test a call to bug_link() with short=False on a Bug that has a title."""
        bug = mock.MagicMock()
        bug.bug_id = 1234567
        bug.title = "Lucky bug number"

        link = util.bug_link(None, bug)

        assert link == \
            ("<a target='_blank' href='https://bugzilla.redhat.com/show_bug.cgi?id=1234567' "
             "class='notblue'>BZ#1234567</a> Lucky bug number")

    def test_short_false_with_title_sanitizes_safe_tags(self):
        """
        Test that a call to bug_link() with short=False on a Bug that has a title sanitizes even
        safe tags because really they should be rendered human readable.
        """
        bug = mock.MagicMock()
        bug.bug_id = 1234567
        bug.title = 'Check <b>this</b> out'

        link = util.bug_link(None, bug)

        assert link == \
            ("<a target='_blank' href='https://bugzilla.redhat.com/show_bug.cgi?id=1234567' "
             "class='notblue'>BZ#1234567</a> Check &lt;b&gt;this&lt;/b&gt; out")

    def test_short_false_with_title_sanitizes_unsafe_tags(self):
        """
        Test that a call to bug_link() with short=False on a Bug that has a title sanitizes unsafe
        tags.
        """
        bug = mock.MagicMock()
        bug.bug_id = 1473091
        bug.title = '<disk> <driver name="..."> should be optional'

        link = util.bug_link(None, bug)
        # bleach v3 fixed a bug that closed out tags when sanitizing. so we check for
        # either possible results here.
        # https://github.com/mozilla/bleach/issues/392
        bleach_v = pkg_resources.parse_version(bleach.__version__)
        if bleach_v >= pkg_resources.parse_version('3.0.0'):
            assert link == \
                ("<a target='_blank' href='https://bugzilla.redhat.com/show_bug.cgi?id=1473091' "
                 "class='notblue'>BZ#1473091</a> &lt;disk&gt; &lt;driver name=\"...\"&gt; should "
                 "be optional")
        else:
            assert link == \
                ("<a target='_blank' href='https://bugzilla.redhat.com/show_bug.cgi?id=1473091' "
                 "class='notblue'>BZ#1473091</a> &lt;disk&gt; &lt;driver name=\"...\"&gt; should "
                 "be optional&lt;/driver&gt;&lt;/disk&gt;")

    def test_short_false_without_title(self):
        """Test a call to bug_link() with short=False on a Bug that has no title."""
        bug = mock.MagicMock()
        bug.bug_id = 1234567
        bug.title = None

        link = util.bug_link(None, bug)

        assert link == \
            ("<a target='_blank' href='https://bugzilla.redhat.com/show_bug.cgi?id=1234567' "
             "class='notblue'>BZ#1234567</a> <i class='fa fa-spinner fa-spin fa-fw'></i>")

    def test_short_true(self):
        """Test a call to bug_link() with short=True."""
        bug = mock.MagicMock()
        bug.bug_id = 1234567
        bug.title = "Lucky bug number"

        link = util.bug_link(None, bug, True)

        assert link == \
            ("<a target='_blank' href='https://bugzilla.redhat.com/show_bug.cgi?id=1234567' "
             "class='notblue'>BZ#1234567</a>")


@mock.patch('bodhi.server.util.time.sleep')
class TestCallAPI:
    """Test the call_api() function."""

    @mock.patch('bodhi.server.util.http_session.get')
    def test_retries_failure(self, get, sleep):
        """Assert correct operation of the retries argument when they never succeed."""
        class FakeResponse(object):
            def __init__(self, status_code):
                self.status_code = status_code

            @property
            def text(self):
                return "Some stuff"

            def json(self):
                return {'some': 'stuff'}

        get.side_effect = [FakeResponse(503), FakeResponse(503)]

        with pytest.raises(RuntimeError) as exc:
            util.call_api('url', 'service_name', retries=1)

        assert str(exc.value) == \
            ('Bodhi failed to get a resource from '
             'service_name at the following URL "url". The '
             'status code was "503". The error was "{\'some\': \'stuff\'}".')
        assert get.mock_calls == [mock.call('url', timeout=60), mock.call('url', timeout=60)]
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

        assert res == {'some': 'stuff'}
        assert get.mock_calls == [mock.call('url', timeout=60), mock.call('url', timeout=60)]
        sleep.assert_called_once_with(1)


class TestMemoized:
    """Test the memoized class."""

    def test_caching(self):
        """Ensure that caching works for hashable parameters."""
        return_value = True

        @util.memoized
        def some_function(arg):
            return return_value

        assert some_function(42)
        # Let's flip the value of return_value just to make sure the cached value is used and not
        # the new value.
        return_value = False
        # It should still return True, indicating that some_function() was not called again.
        assert some_function(42)

    def test_caching_different_args(self):
        """Ensure that caching works for hashable parameters, but is sensitive to arguments."""
        return_value = True

        @util.memoized
        def some_function(arg):
            return return_value

        assert some_function(42)
        # Let's flip the value of return_value just to make sure the cached value is not used.
        return_value = False
        # It should return False because the argument is different.
        assert not some_function(41)

    def test_dont_cache_lists(self):
        """memoized should not cache calls with list arguments."""
        return_value = True

        @util.memoized
        def some_function(arg):
            return return_value

        assert some_function(['some', 'list'])
        # Let's flip the value of return_value just to make sure it isn't cached.
        return_value = False
        assert not some_function(['some', 'list'])

    def test___get__(self):
        """__get__() should allow us to set the function as an attribute of another object."""
        @util.memoized
        def some_function(arg):
            """Some docblock"""
            return 42

        class some_class(object):
            thing = some_function

        assert some_class().thing() == 42


class TestNoAutoflush:
    """Test the no_autoflush context manager."""
    def test_autoflush_disabled(self):
        """Test correct behavior when autoflush is disabled."""
        session = mock.MagicMock()
        session.autoflush = False

        with util.no_autoflush(session):
            assert session.autoflush is False

        # autoflush should still be False since that was the starting condition.
        assert session.autoflush is False

    def test_autoflush_enabled(self):
        """Test correct behavior when autoflush is enabled."""
        session = mock.MagicMock()
        session.autoflush = True

        with util.no_autoflush(session):
            assert not session.autoflush

        # autoflush should again be True since that was the starting condition.
        assert session.autoflush


class TestCanWaiveTestResults(base.BasePyTestCase):
    """Test the can_waive_test_results() function."""

    def test_access_token_undefined(self):
        """If Bodhi is not configured with an access token, the result should be False."""
        config.update({
            'test_gating.required': True,
            'waiverdb.access_token': None
        })
        u = Update.query.all()[0]
        u.test_gating_status = TestGatingStatus.failed
        u.status = models.UpdateStatus.testing

        assert not util.can_waive_test_results(None, u)

    def test_can_waive_test_results(self):
        config.update({
            'test_gating.required': True,
            'waiverdb.access_token': "secret"
        })
        u = Update.query.all()[0]
        u.test_gating_status = TestGatingStatus.failed
        u.status = models.UpdateStatus.testing
        assert util.can_waive_test_results(None, u)

    def test_gating_required_false(self):
        """
        Assert that it should return false if test_gating is not enabled, even if
        other conditions are met.
        """
        config.update({
            'test_gating.required': False,
            'waiverdb.access_token': "secret"
        })
        u = Update.query.all()[0]
        u.test_gating_status = TestGatingStatus.failed
        u.status = models.UpdateStatus.testing
        assert not util.can_waive_test_results(None, u)

    def test_all_tests_passed(self):
        """
        Assert that it should return false if all tests passed, even if
        other conditions are met.
        """
        config.update({
            'test_gating.required': True,
            'waiverdb.access_token': "secret"
        })
        u = Update.query.all()[0]
        u.test_gating_status = TestGatingStatus.passed
        u.status = models.UpdateStatus.testing
        assert not util.can_waive_test_results(None, u)

    def test_update_is_stable(self):
        """
        Assert that it should return false if the update is stable, even if
        other conditions are met.
        """
        config.update({
            'test_gating.required': True,
            'waiverdb.access_token': "secret"
        })
        u = Update.query.all()[0]
        u.test_gating_status = TestGatingStatus.failed
        u.status = models.UpdateStatus.stable
        assert not util.can_waive_test_results(None, u)


class TestPagesList:
    """Test the pages_list() function."""

    def test_page_in_middle(self):
        """Test for when the current page is in the middle of the pages."""
        val = util.pages_list(mock.MagicMock(), 15, 30)
        assert val == [1, "..."] + list(range(11, 20)) + ['...', 30]

    def test_page_near_end(self):
        """Test for when the current page is near the end of the pages."""
        val = util.pages_list(mock.MagicMock(), 6, 7)

        assert val == list(range(1, 8))


class TestSanityCheckRepodata(base.BasePyTestCase):
    """Test the sanity_check_repodata() function."""

    def setup_method(self, method):
        super().setup_method(method)
        self.tempdir = tempfile.mkdtemp('bodhi')

    def teardown_method(self, method):
        shutil.rmtree(self.tempdir)
        super().teardown_method(method)

    def test_correct_yum_repo(self):
        """No Exception should be raised if the repo is normal."""
        base.mkmetadatadir(self.tempdir)

        # No exception should be raised here.
        util.sanity_check_repodata(self.tempdir, repo_type='yum')

    def test_invalid_repo_type(self):
        """A ValueError should be raised with invalid repo type."""
        with pytest.raises(ValueError) as excinfo:
            util.sanity_check_repodata("so", "wrong")
        assert str(excinfo.value) == 'repo_type must be one of module, source, or yum.'

    @mock.patch('bodhi.server.util.librepo')
    def test_librepo_exception(self, librepo):
        """Verify that LibrepoExceptions are re-wrapped."""
        class MockException(Exception):
            pass
        librepo.LibrepoException = MockException
        librepo.Handle.return_value.perform.side_effect = MockException(-1, 'msg', 'general_msg')

        with pytest.raises(RepodataException) as excinfo:
            util.sanity_check_repodata('/tmp/', 'yum')
        assert str(excinfo.value) == 'msg'

    def _mkmetadatadir_w_modules(self):
        base.mkmetadatadir(self.tempdir)
        # We need to add a modules tag to repomd.
        repomd_path = os.path.join(self.tempdir, 'repodata', 'repomd.xml')
        repomd_tree = ElementTree.parse(repomd_path)
        ElementTree.register_namespace('', 'http://linux.duke.edu/metadata/repo')
        root = repomd_tree.getroot()
        modules_elem = ElementTree.SubElement(root, 'data', type='modules')
        # ensure librepo finds something
        ElementTree.SubElement(modules_elem, 'location', href='repodata/modules.yaml.gz')
        with gzip.open(os.path.join(self.tempdir, 'repodata', 'modules.yaml.gz'), 'w'):
            pass
        for data in root.findall('{http://linux.duke.edu/metadata/repo}data'):
            # module repos don't have drpms or comps.
            if data.attrib['type'] in ('group', 'prestodelta'):
                root.remove(data)
        repomd_tree.write(repomd_path, encoding='UTF-8', xml_declaration=True)

    @mock.patch('subprocess.check_output', return_value='Some output')
    def test_correct_module_repo(self, *args):
        """No Exception should be raised if the repo is a normal module repo."""
        self._mkmetadatadir_w_modules()
        # No exception should be raised here.
        util.sanity_check_repodata(self.tempdir, repo_type='module')

    @mock.patch('subprocess.check_output', return_value='')
    def test_module_repo_no_dnf_output(self, *args):
        """No Exception should be raised if the repo is a normal module repo."""
        self._mkmetadatadir_w_modules()

        with pytest.raises(util.RepodataException) as exc:
            util.sanity_check_repodata(self.tempdir, repo_type='module')
        assert str(exc.value) == \
            ("DNF did not return expected output when running test!"
             " Test: ['module', 'list'], expected: .*, output: ")

    def test_updateinfo_empty_tags(self):
        """RepodataException should be raised if <id/> is found in updateinfo."""
        updateinfo = os.path.join(self.tempdir, 'updateinfo.xml')
        with open(updateinfo, 'w') as uinfo:
            uinfo.write('<id/>')
        base.mkmetadatadir(self.tempdir, updateinfo=updateinfo)

        with pytest.raises(util.RepodataException) as exc:
            util.sanity_check_repodata(self.tempdir, repo_type='yum')
        assert str(exc.value) == 'updateinfo.xml.gz contains empty ID tags'

    def test_comps_invalid_notxml(self):
        """RepodataException should be raised if comps is invalid."""
        comps = os.path.join(self.tempdir, 'comps.xml')
        with open(comps, 'w') as uinfo:
            uinfo.write('this is not even xml')
        base.mkmetadatadir(self.tempdir, comps=comps)

        with pytest.raises(util.RepodataException) as exc:
            util.sanity_check_repodata(self.tempdir, repo_type='yum')
        assert str(exc.value) == 'Comps file unable to be parsed'

    def test_comps_invalid_nonsense(self):
        """RepodataException should be raised if comps is invalid."""
        comps = os.path.join(self.tempdir, 'comps.xml')
        with open(comps, 'w') as uinfo:
            uinfo.write('<whatever />')
        base.mkmetadatadir(self.tempdir, comps=comps)

        with pytest.raises(util.RepodataException) as exc:
            util.sanity_check_repodata(self.tempdir, repo_type='yum')
        assert str(exc.value) == 'Comps file empty'

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

        with pytest.raises(util.RepodataException) as exc:
            util.sanity_check_repodata(self.tempdir, repo_type='yum')
        assert str(exc.value) == 'Required parts not in repomd.xml: updateinfo'

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


class TestTestcaseLink(base.BasePyTestCase):
    """Test the testcase_link() function."""

    base_url = 'http://example.com/'
    displayed_name = 'test case name'

    def setup_method(self, method):
        super().setup_method(method)
        self.test = mock.Mock()
        self.test.name = 'QA:Testcase ' + self.displayed_name

    @property
    def expected_url(self):
        return self.base_url + self.test.name

    @pytest.mark.parametrize('short', (False, True))
    def test_fn(self, short):
        """Test the function."""
        print(self.base_url)
        config["test_case_base_url"] = self.base_url
        print(config["test_case_base_url"])
        retval = util.testcase_link(None, self.test, short=short)

        if short:
            assert not retval.startswith('Test Case ')
        else:
            assert retval.startswith('Test Case ')
        assert f"href='{self.expected_url}'" in retval
        assert f">{self.displayed_name}<" in retval


class TestType2Color:
    """Test the type2color() function."""

    def test_colors(self):
        """Test type2color() output."""
        context = {'request': mock.MagicMock()}
        assert util.type2color(context, 'bugfix') == 'rgba(150,180,205,0.5)'
        assert util.type2color(context, 'security') == 'rgba(205,150,180,0.5)'
        assert util.type2color(context, 'newpackage') == 'rgba(150,205,180,0.5)'
        assert util.type2color(context, 'enhancement') == 'rgba(205,205,150,0.5)'
        assert util.type2color(context, 'something_else') == 'rgba(200,200,200,0.5)'


class TestType2Icon:
    """Test the type2icon() function."""

    def test_consonant(self):
        """Test type2icon() with a kind that starts with a consonant."""
        assert util.type2icon(None, 'security') == \
            ("<span data-toggle='tooltip' title='This is a security update'>"
             "<i class='fa fa-fw fa-shield'></i></span>")

    def test_vowel(self):
        """Test type2icon() with a kind that starts with a vowel."""
        assert util.type2icon(None, 'enhancement') == \
            ("<span data-toggle='tooltip' title='This is an enhancement update'>"
             "<i class='fa fa-fw fa-bolt'></i></span>")


class TestUtils(base.BasePyTestCase):

    def test_get_critpath_components_dummy(self):
        """ Ensure that critpath packages can be found using the hardcoded
        list.
        """
        config.update({
            'critpath.type': None,
            'critpath_pkgs': ['kernel', 'glibc']
        })
        assert util.get_critpath_components() == ['kernel', 'glibc']

    @mock.patch('bodhi.server.util.http_session')
    @mock.patch('bodhi.server.util.time.sleep')
    def test_get_critpath_components_pdc_error(self, sleep, session):
        """ Ensure an error is thrown in Bodhi if there is an error in PDC
        getting the critpath packages.
        """
        config.update({
            'critpath.type': 'pdc',
            'pdc_url': 'http://domain.local'
        })
        session.get.return_value.status_code = 500
        session.get.return_value.json.return_value = \
            {'error': 'some error'}
        with pytest.raises(RuntimeError) as exc:
            util.get_critpath_components('f25')
        # We are not testing the whole error message because there is no
        # guarantee of the ordering of the GET parameters.
        assert 'Bodhi failed to get a resource from PDC' in str(exc.value)
        assert 'The status code was "500".' in str(exc.value)
        assert sleep.mock_calls == [mock.call(1), mock.call(1), mock.call(1)]

    @mock.patch('bodhi.server.util.log')
    def test_get_critpath_components_not_pdc_not_rpm(self, mock_log):
        """ Ensure a warning is logged when the critpath system is not pdc
        and the type of components to search for is not rpm.
        """
        config.update({
            'critpath.type': None,
            'critpath_pkgs': ['kernel', 'glibc']
        })
        pkgs = util.get_critpath_components('f25', 'module')
        assert 'kernel' in pkgs
        warning = ('The critpath.type of "module" does not support searching '
                   'for non-RPM components')
        mock_log.warning.assert_called_once_with(warning)

    @mock.patch('bodhi.server.util.http_session')
    def test_get_critpath_components_pdc_paging_exception(self, session):
        """Ensure that an Exception is raised if components are used and the response is paged."""
        config.update({
            'critpath.type': 'pdc',
            'pdc_url': 'http://domain.local'
        })
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

        with pytest.raises(Exception) as exc:
            util.get_critpath_components('f26', 'rpm', frozenset(['gcc']))

        assert str(exc.value) == 'We got paging when requesting a single component?!'
        assert session.get.mock_calls == \
            [mock.call(
                ('http://domain.local/rest_api/v1/component-branches/?active=true'
                 '&critical_path=true&fields=global_component&name=f26&page_size=100&type=rpm'
                 '&global_component=gcc'),
                timeout=60),
             mock.call().json()]

    @mock.patch('bodhi.server.util.http_session')
    def test_get_critpath_pdc_with_components(self, session):
        """Test the components argument to get_critpath_components()."""
        config.update({
            'critpath.type': 'pdc',
            'pdc_url': 'http://domain.local'
        })
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

        assert pkgs == ['gcc']
        assert session.get.mock_calls == \
            [mock.call(
                ('http://domain.local/rest_api/v1/component-branches/?active=true'
                 '&critical_path=true&fields=global_component&name=f26&page_size=100&type=rpm'
                 '&global_component=gcc'),
                timeout=60),
             mock.call().json()]

    @mock.patch('bodhi.server.util.http_session')
    def test_get_critpath_components_pdc_success(self, session):
        """ Ensure that critpath packages can be found using PDC.
        """
        config.update({
            'critpath.type': 'pdc',
            'pdc_url': 'http://domain.local'
        })
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
        assert 'python' in pkgs
        assert 'gcc' in pkgs
        # At least make sure it called the next url to cycle through the pages.
        # We can't verify all the calls made because the URL GET parameters
        # in the URL may have different orders based on the system/Python
        # version.
        session.get.assert_called_with(pdc_next_url, timeout=60)
        # Verify there were two GET requests made and two .json() calls
        assert session.get.call_count == 2
        assert session.get.return_value.json.call_count == 2

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
        assert rv == expected_json

    @mock.patch('bodhi.server.util.http_session')
    @mock.patch('bodhi.server.util.time.sleep')
    def test_pagure_api_get_non_500_error(self, sleep, session):
        """ Ensure that an API request to Pagure that raises an error that is
        not a 500 error returns the actual error message from the JSON.
        """
        session.get.return_value.status_code = 404
        session.get.return_value.json.return_value = {
            "error": "Project not found",
            "error_code": "ENOPROJECT"
        }
        with pytest.raises(RuntimeError) as exc:
            util.pagure_api_get('http://domain.local/api/0/rpms/python')
        expected_error = (
            'Bodhi failed to get a resource from Pagure at the following URL '
            '"http://domain.local/api/0/rpms/python". The status code was '
            '"404". The error was "Project not found".')
        assert str(exc.value) == expected_error
        assert sleep.mock_calls == [mock.call(1), mock.call(1), mock.call(1)]

    @mock.patch('bodhi.server.util.http_session')
    @mock.patch('bodhi.server.util.time.sleep')
    def test_pagure_api_get_500_error(self, sleep, session):
        """ Ensure that an API request to Pagure that triggers a 500 error
        raises the expected error message.
        """
        session.get.return_value.status_code = 500
        with pytest.raises(RuntimeError) as exc:
            util.pagure_api_get('http://domain.local/api/0/rpms/python')

        expected_error = (
            'Bodhi failed to get a resource from Pagure at the following URL '
            '"http://domain.local/api/0/rpms/python". The status code was '
            '"500".')
        assert str(exc.value) == expected_error
        assert sleep.mock_calls, [mock.call(1), mock.call(1), mock.call(1)]

    @mock.patch('bodhi.server.util.http_session')
    @mock.patch('bodhi.server.util.time.sleep')
    def test_pagure_api_get_non_500_error_no_json(self, sleep, session):
        """ Ensure that an API request to Pagure that raises an error that is
        not a 500 error and has no JSON returns an error.
        """
        session.get.return_value.status_code = 404
        session.get.return_value.json.side_effect = ValueError('Not JSON')
        with pytest.raises(RuntimeError) as exc:
            util.pagure_api_get('http://domain.local/api/0/rpms/python')

        expected_error = (
            'Bodhi failed to get a resource from Pagure at the following URL '
            '"http://domain.local/api/0/rpms/python". The status code was '
            '"404". The error was "".')
        assert str(exc.value) == expected_error
        assert sleep.mock_calls, [mock.call(1), mock.call(1), mock.call(1)]

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
        assert rv == expected_json

    @mock.patch('bodhi.server.util.http_session')
    @mock.patch('bodhi.server.util.time.sleep')
    def test_pdc_api_get_500_error(self, sleep, session):
        """ Ensure that an API request to PDC that triggers a 500 error
        raises the expected error message.
        """
        session.get.return_value.status_code = 500
        with pytest.raises(RuntimeError) as exc:
            util.pdc_api_get(
                'http://domain.local/rest_api/v1/component-branch-slas/')
        expected_error = (
            'Bodhi failed to get a resource from PDC at the following URL '
            '"http://domain.local/rest_api/v1/component-branch-slas/". The '
            'status code was "500".')
        assert str(exc.value) == expected_error
        assert sleep.mock_calls == [mock.call(1), mock.call(1), mock.call(1)]

    @mock.patch('bodhi.server.util.http_session')
    @mock.patch('bodhi.server.util.time.sleep')
    def test_pdc_api_get_non_500_error(self, sleep, session):
        """ Ensure that an API request to PDC that raises an error that is
        not a 500 error returns the returned JSON.
        """
        session.get.return_value.status_code = 404
        session.get.return_value.json.return_value = {
            "detail": "Not found."
        }
        with pytest.raises(RuntimeError) as exc:
            util.pdc_api_get(
                'http://domain.local/rest_api/v1/component-branch-slas/3/')

        expected_error = (
            'Bodhi failed to get a resource from PDC at the following URL '
            '"http://domain.local/rest_api/v1/component-branch-slas/3/". The '
            'status code was "404". The error was '
            '"{\'detail\': \'Not found.\'}".')
        assert str(exc.value) == expected_error
        assert sleep.mock_calls == [mock.call(1), mock.call(1), mock.call(1)]

    @mock.patch('bodhi.server.util.http_session')
    @mock.patch('bodhi.server.util.time.sleep')
    def test_pdc_api_get_non_500_error_no_json(self, sleep, session):
        """ Ensure that an API request to PDC that raises an error that is
        not a 500 error and has no JSON returns an error.
        """
        session.get.return_value.status_code = 404
        session.get.return_value.json.side_effect = ValueError('Not JSON')
        with pytest.raises(RuntimeError) as exc:
            util.pdc_api_get(
                'http://domain.local/rest_api/v1/component-branch-slas/3/')

        expected_error = (
            'Bodhi failed to get a resource from PDC at the following URL '
            '"http://domain.local/rest_api/v1/component-branch-slas/3/". The '
            'status code was "404". The error was "".')
        assert str(exc.value) == expected_error
        assert sleep.mock_calls == [mock.call(1), mock.call(1), mock.call(1)]

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
        assert decision == expected_json

    @mock.patch('bodhi.server.util.http_session')
    @mock.patch('bodhi.server.util.time.sleep')
    def test_greenwave_api_post_500_error(self, sleep, session):
        """ Ensure that a POST request to Greenwave that triggers a 500 error
        raises the expected error message.
        """
        session.post.return_value.status_code = 500
        with pytest.raises(RuntimeError) as exc:
            data = {
                'product_version': 'fedora-26',
                'decision_context': 'bodhi_push_update_stable',
                'subjects': ['foo-1.0.0-1.f26']
            }
            util.greenwave_api_post('http://domain.local/api/v1.0/decision',
                                    data)

        expected_error = (
            'Bodhi failed to send POST request to Greenwave at the following URL '
            '"http://domain.local/api/v1.0/decision". The status code was "500".')
        assert str(exc.value) == expected_error
        assert sleep.mock_calls == [mock.call(1), mock.call(1), mock.call(1)]

    @mock.patch('bodhi.server.util.http_session')
    @mock.patch('bodhi.server.util.time.sleep')
    def test_greenwave_api_post_non_500_error(self, sleep, session):
        """ Ensure that a POST request to Greenwave that raises an error that is
        not a 500 error returns the returned JSON.
        """
        session.post.return_value.status_code = 404
        session.post.return_value.json.return_value = {
            "message": "Not found."
        }
        with pytest.raises(RuntimeError) as exc:
            data = {
                'product_version': 'fedora-26',
                'decision_context': 'bodhi_push_update_stable',
                'subjects': ['foo-1.0.0-1.f26']
            }
            util.greenwave_api_post('http://domain.local/api/v1.0/decision',
                                    data)

        expected_error = (
            'Bodhi failed to send POST request to Greenwave at the following URL '
            '"http://domain.local/api/v1.0/decision". The status code was "404". '
            'The error was "{\'message\': \'Not found.\'}".')
        assert str(exc.value) == expected_error
        assert sleep.mock_calls == [mock.call(1), mock.call(1), mock.call(1)]

    @mock.patch('bodhi.server.util.http_session')
    @mock.patch('bodhi.server.util.time.sleep')
    def test_greenwave_api_post_non_500_error_no_json(self, sleep, session):
        """ Ensure that a POST request to Greenwave that raises an error that is
        not a 500 error and has no JSON returns an error.
        """
        session.post.return_value.status_code = 404
        session.post.return_value.json.side_effect = ValueError('Not JSON')
        with pytest.raises(RuntimeError) as exc:
            data = {
                'product_version': 'fedora-26',
                'decision_context': 'bodhi_push_update_stable',
                'subjects': ['foo-1.0.0-1.f26']
            }
            util.greenwave_api_post('http://domain.local/api/v1.0/decision',
                                    data)

        expected_error = (
            'Bodhi failed to send POST request to Greenwave at the following URL '
            '"http://domain.local/api/v1.0/decision". The status code was "404". '
            'The error was "".')
        assert str(exc.value) == expected_error
        assert sleep.mock_calls == [mock.call(1), mock.call(1), mock.call(1)]

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
        assert waiver == expected_json

    def test_markup_escapes(self):
        """Ensure we correctly parse markdown & escape HTML"""
        text = (
            '# this is a header\n'
            'this is some **text**\n'
            '<script>alert("pants")</script>'
        )
        html = util.markup(None, text)

        # Markdown has changed html parser between 3.2.2 and 3.3.0
        from markdown import __version_info__ as mvi
        if mvi[0] >= 3 and mvi[1] >= 3:
            assert html == \
                (
                    '<div class="markdown"><h1>this is a header</h1>\n'
                    '<p>this is some <strong>text</strong></p>\n'
                    '&lt;script&gt;alert("pants")&lt;/script&gt;\n</div>'
                )
        else:
            assert html == \
                (
                    '<div class="markdown"><h1>this is a header</h1>\n'
                    '<p>this is some <strong>text</strong>\n'
                    '&lt;script&gt;alert("pants")&lt;/script&gt;</p></div>'
                )

    @mock.patch('bodhi.server.util.bleach.clean', return_value='cleaned text')
    def test_markup_with_bleach(self, clean):
        """Use mocking to ensure we correctly use the bleach 2 API."""
        text = '# this is a header\nthis is some **text**'

        result = util.markup(None, text)

        assert result == 'cleaned text'
        expected_text = (
            '<div class="markdown"><h1>this is a header</h1>\n<p>this is some <strong>text'
            '</strong></p></div>')
        expected_tags = [
            "h1", "h2", "h3", "h4", "h5", "h6", "b", "i", "strong", "em", "tt", "p", "br", "span",
            "div", "blockquote", "code", "hr", "pre", "ul", "ol", "li", "dd", "dt", "img", "a"]
        expected_attributes = {
            "img": ["src", "alt", "title"], "a": ["href", "alt", "title"], "div": ["class"]}
        # The bleach 2 API should get these attrs passed.
        clean.assert_called_once_with(expected_text, tags=expected_tags,
                                      attributes=expected_attributes)

    def test_markup_without_bodhi_extensions(self):
        """Ensure Bodhi extensions are not used with bodhi=False"""
        text = (
            'rhbz#12345\n'
            '@mattia\n'
            'FEDORA-EPEL-2019-1a2b3c4d5e'
        )
        html = util.markup(None, text, bodhi=False)
        assert html == \
            (
                '<p>rhbz#12345\n'
                '@mattia\n'
                'FEDORA-EPEL-2019-1a2b3c4d5e</p>'
            )

    def test_rpm_header(self):
        h = util.get_rpm_header('libseccomp')
        assert h['name'] == 'libseccomp'

    def test_rpm_header_exception(self):
        with pytest.raises(Exception):
            util.get_rpm_header('raise-exception')

    def test_rpm_header_not_found(self):
        with pytest.raises(ValueError) as exc:
            util.get_rpm_header("do-not-find-anything")
        expected_error = "No rpm headers found in koji for 'do-not-find-anything'"
        assert str(exc.value) == expected_error

    def test_cmd_failure_exceptions_off(self):
        ret = util.cmd('false', raise_on_error=False)
        assert (b'', b'', 1) == ret

    def test_cmd_failure_exceptions_on(self):
        with pytest.raises(RuntimeError) as exc:
            util.cmd('false', raise_on_error=True)
        assert str(exc.value) == "f a l s e returned a non-0 exit code: 1"

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
        #  u5 contains pkgd-1.0, which is < pkgd-2.0 from u6
        #  u2 contains somepkg-1.0, which is < somepkg-2.0 from u1
        assert sync == [u5, u6, u2, u1]
        # This ordering is because neither u3 nor u4 overlap with other updates
        assert async_ == [u3, u4]

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
        assert sync == [u2, u3]
        # This ordering is because u1 doesn't overlap with anything
        assert async_ == [u1]

    def test_splitter(self):
        splitlist = util.splitter(["build-0.1", "build-0.2"])
        assert splitlist == ['build-0.1', 'build-0.2']

        splitcommastring = util.splitter("build-0.1, build-0.2")
        assert splitcommastring == ['build-0.1', 'build-0.2']

        splitspacestring = util.splitter("build-0.1 build-0.2")
        assert splitspacestring == ['build-0.1', 'build-0.2']

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
        assert 'Problem talking to' in msg
        assert 'status code was %r' % mock_get.return_value.status_code in msg

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

        assert results == ['datum1', 'datum2', 'datum3']
        assert mock_get.return_value.json.call_count == 2
        assert mock_get.call_count == 2
        assert mock_get.call_args[0][0] == 'url2'
        assert mock_get.call_args[1]['timeout'] == 60

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

        assert mock_get.call_count == 5
        assert results == ['datum'] * 5
        assert 'Too many result pages, aborting at' in log_debug.call_args[0][0]


class TestCMDFunctions:
    @mock.patch('bodhi.server.log.debug')
    @mock.patch('bodhi.server.log.error')
    @mock.patch('subprocess.Popen')
    def test_no_err_out_zero_return_code(self, mock_popen, mock_error, mock_debug):
        """
        Verify behavior without any output and a zero exit code.
        """
        mock_popen.return_value = mock.Mock()
        mock_popen_obj = mock_popen.return_value
        mock_popen_obj.communicate.return_value = (None, None)
        mock_popen_obj.returncode = 0

        assert util.cmd(['/bin/true'], '"home/imgs/catpix"') == (None, None, 0)

        mock_popen.assert_called_once_with(
            ['/bin/true'], cwd='"home/imgs/catpix"', stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            shell=False)

        mock_error.assert_not_called()
        mock_debug.assert_called_once_with('Running /bin/true')

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

        assert mock_error.mock_calls == \
            [mock.call('/bin/echo returned a non-0 exit code: 1'), mock.call('output\nerror')]
        mock_debug.assert_called_once_with('Running /bin/echo')
        assert mock_error.mock_calls == \
            [mock.call('/bin/echo returned a non-0 exit code: 1'), mock.call('output\nerror')]

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
        assert mock_debug.mock_calls == \
            [mock.call('Running /bin/echo'), mock.call('subprocess output: output\nNone')]

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
        mock_debug.assert_called_with('subprocess output: output\nerror')

    @mock.patch('bodhi.server.buildsys.get_session')
    def test__get_build_repository(self, session):
        session.return_value = mock.Mock()
        session.return_value.getBuild.side_effect = [
            {
                'extra': {
                    'image': {
                        'index': {
                            'pull': [pullspec]
                        }
                    }
                }
            }
            for pullspec in [
                'candidate-registry.fedoraproject.org/f29/cockpit:176-5.fc28',
                'candidate-registry.fedoraproject.org/myrepo@sha256:abcdefg123456'
            ]
        ]
        build = mock.Mock()
        build.nvr = 'cockpit-167-5'
        assert util._get_build_repository(build) == 'f29/cockpit'
        assert util._get_build_repository(build) == 'myrepo'
        session.return_value.getBuild.assert_called_with('cockpit-167-5')

    def test_build_evr(self):
        """Test the test_build_evr() function."""
        build = {'epoch': None, 'version': '1', 'release': '2.fc30'}

        assert util.build_evr(build) == ('0', '1', '2.fc30')

        build['epoch'] = 2
        assert util.build_evr(build) == ('2', '1', '2.fc30')


@mock.patch('bodhi.server.util.cmd', autospec=True)
@mock.patch('bodhi.server.util._container_image_url', new=lambda sr, r, st: f'{sr}:{r}:{st}')
@mock.patch('bodhi.server.util._get_build_repository', new=lambda b: 'testrepo')
class TestCopyContainer(base.BasePyTestCase):
    """Test the copy_container() function."""

    def setup_method(self, method):
        super().setup_method(method)
        self.build = mock.Mock()
        self.build.nvr_version = '1'
        self.build.nvr_release = '1'
        config.update({
            'container.source_registry': 'src',
            'container.destination_registry': 'dest',
            'skopeo.cmd': 'skopeo',
        })

    def test_default(self, cmd):
        """Test the default code path."""
        util.copy_container(self.build)

        cmd.assert_called_once_with(['skopeo', 'copy', 'src:testrepo:1-1', 'dest:testrepo:1-1'],
                                    raise_on_error=True)

    def test_with_destination_registry(self, cmd):
        """Test with specified destination_registry."""
        util.copy_container(self.build, destination_registry='boo')

        cmd.assert_called_once_with(['skopeo', 'copy', 'src:testrepo:1-1', 'boo:testrepo:1-1'],
                                    raise_on_error=True)

    def test_with_destination_tag(self, cmd):
        """Test with specified destination_tag."""
        util.copy_container(self.build, destination_tag='2-2')

        cmd.assert_called_once_with(['skopeo', 'copy', 'src:testrepo:1-1', 'dest:testrepo:2-2'],
                                    raise_on_error=True)

    def test_with_extra_copy_flags(self, cmd):
        """Test with extra copy flags configured."""
        config['skopeo.extra_copy_flags'] = '--quiet,--remove-signatures'
        util.copy_container(self.build)

        cmd.assert_called_once_with(['skopeo', 'copy', '--quiet', '--remove-signatures',
                                     'src:testrepo:1-1', 'dest:testrepo:1-1'],
                                    raise_on_error=True)


class TestTransactionalSessionMaker(base.BasePyTestCase):
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

        with pytest.raises(ValueError) as exc_context:
            with tsm():
                raise exception
        assert exc_context.value is exception

        log_exception.assert_called_once_with(
            'An Exception was raised while rolling back a transaction.')
        assert Session.return_value.commit.call_count == 0
        Session.return_value.rollback.assert_called_once_with()
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

        with pytest.raises(ValueError) as exc_context:
            with tsm():
                raise exception
        assert exc_context.value is exception

        assert log_exception.call_count == 0
        assert Session.return_value.commit.call_count == 0
        Session.return_value.rollback.assert_called_once_with()
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

        assert log_exception.call_count == 0
        assert Session.return_value.rollback.call_count == 0
        Session.return_value.commit.assert_called_once_with()
        Session.remove.assert_called_once_with()


class TestPyfileToModule(base.BasePyTestCase):
    """Test the pyfile_to_module() function."""

    def setup_method(self, method):
        super().setup_method(method)
        self.tempdir = tempfile.mkdtemp('bodhi')

    def teardown_method(self, method):
        shutil.rmtree(self.tempdir)
        super().teardown_method(method)

    def test_basic_call(self):
        filepath = os.path.join(self.tempdir, "testfile.py")
        with open(filepath, "w") as fh:
            fh.write("FOO = 'bar'\n")
        result = util.pyfile_to_module(filepath, "testfile")
        assert getattr(result, "FOO") == "bar"
        assert result.__file__ == filepath
        assert result.__name__ == "testfile"

    def test_invalid_path(self):
        filepath = os.path.join(self.tempdir, "does-not-exist.py")
        with pytest.raises(IOError) as cm:
            util.pyfile_to_module(filepath, "testfile")
        assert str(cm.value) == \
            ("[Errno 2] Unable to load file (No such file or directory):"
             f" '{self.tempdir}/does-not-exist.py'")

    def test_invalid_path_silent(self):
        filepath = os.path.join(self.tempdir, "does-not-exist.py")
        try:
            result = util.pyfile_to_module(filepath, "testfile", silent=True)
        except IOError as e:
            self.fail("pyfile_to_module raised an exception in silent mode: {}".format(e))
        assert not result


class TestJsonEscape:
    """Tests for the json_escape() function."""
    def test_doublequotes_escaped(self):
        """Test that double quotes are escaped correctly for JSON.parse()."""
        title = 'This is a "terrible" bug title!'
        assert util.json_escape(title) == 'This is a \\"terrible\\" bug title!'


class TestPageUrl:
    """Tests for the page_url() method."""
    def test_multi_values_parameter(self):
        """Ensure correct url is generated from multiple values for same filter."""
        context = mock.Mock()
        context.get().path_url = 'http://localhost:6543'
        context.get().params = MultiDict([('search', ''),
                                          ('status', 'pending'),
                                          ('status', 'testing')])
        page = 2
        expected_url = 'http://localhost:6543?search=&status=pending&status=testing&page=2'
        assert util.page_url(context, page) == expected_url
