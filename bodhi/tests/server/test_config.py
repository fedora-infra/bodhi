# Copyright © 2017-2019 Red Hat, Inc.
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

import pytest

from bodhi.server import config


class TestBodhiConfigGetItemTests:
    """Tests for the ``__getitem__`` method on the :class:`BodhiConfig` class."""

    def setup_method(self):
        self.config = config.BodhiConfig()
        self.config.load_config = mock.Mock()
        self.config['password'] = 'hunter2'

    def test_not_loaded(self):
        """Assert calling ``__getitem__`` causes the config to load."""
        assert not self.config.loaded
        assert 'hunter2' == self.config['password']
        self.config.load_config.assert_called_once()

    def test_loaded(self):
        """Assert calling ``__getitem__`` when the config is loaded doesn't reload the config."""
        self.config.loaded = True

        assert 'hunter2' == self.config['password']
        assert self.config.load_config.call_count == 0

    def test_missing(self):
        """Assert you still get normal dictionary errors from the config."""
        pytest.raises(KeyError, self.config.__getitem__, 'somemissingkey')


class TestBodhiConfigGetTests:
    """Tests for the ``get`` method on the :class:`BodhiConfig` class."""

    def setup_method(self):
        self.config = config.BodhiConfig()
        self.config.load_config = mock.Mock()
        self.config['password'] = 'hunter2'

    def test_not_loaded(self):
        """Assert calling ``get`` causes the config to load."""
        assert not self.config.loaded
        assert 'hunter2' == self.config.get('password')
        self.config.load_config.assert_called_once()

    def test_loaded(self):
        """Assert calling ``get`` when the config is loaded doesn't reload the config."""
        self.config.loaded = True

        assert 'hunter2' == self.config.get('password')
        assert self.config.load_config.call_count == 0

    def test_missing(self):
        """Assert you get ``None`` when the key is missing."""
        assert self.config.get('somemissingkey') is None


class TestBodhiConfigPopItemTests:
    """Tests for the ``pop`` method on the :class:`BodhiConfig` class."""

    def setup_method(self):
        self.config = config.BodhiConfig()
        self.config.load_config = mock.Mock()
        self.config['password'] = 'hunter2'

    def test_not_loaded(self):
        """Assert calling ``pop`` causes the config to load."""
        assert not self.config.loaded
        assert 'hunter2' == self.config.pop('password')
        self.config.load_config.assert_called_once()

    def test_loaded(self):
        """Assert calling ``pop`` when the config is loaded doesn't reload the config."""
        self.config.loaded = True

        assert 'hunter2' == self.config.pop('password')
        assert self.config.load_config.call_count == 0

    def test_removes(self):
        """Assert the configuration is removed with ``pop``."""
        assert 'hunter2' == self.config.pop('password')
        pytest.raises(KeyError, self.config.pop, 'password')

    def test_get_missing(self):
        """Assert you still get normal dictionary errors from the config."""
        pytest.raises(KeyError, self.config.pop, 'somemissingkey')


class TestBodhiConfigCopyTests:
    """Tests for the ``copy`` method on the :class:`BodhiConfig` class."""

    def setup_method(self):
        self.config = config.BodhiConfig()
        self.config.load_config = mock.Mock()
        self.config['password'] = 'hunter2'

    def test_not_loaded(self):
        """Assert calling ``copy`` causes the config to load."""
        assert not self.config.loaded
        assert {'password': 'hunter2'} == self.config.copy()
        self.config.load_config.assert_called_once()

    def test_loaded(self):
        """Assert calling ``copy`` when the config is loaded doesn't reload the config."""
        self.config.loaded = True

        assert {'password': 'hunter2'} == self.config.copy()
        assert self.config.load_config.call_count == 0


class TestBodhiConfigLoadConfig:

    @mock.patch('bodhi.server.config.get_appsettings')
    def test_loads_defaults(self, get_appsettings):
        """Test that defaults are loaded."""
        c = config.BodhiConfig()

        c.load_config({'session.secret': 'secret', 'authtkt.secret': 'secret'})

        assert c['top_testers_timeframe'] == 7

    @mock.patch('bodhi.server.config.get_configfile', mock.Mock(return_value='/some/config.ini'))
    @mock.patch('bodhi.server.config.get_appsettings')
    def test_marks_loaded(self, mock_appsettings):
        c = config.BodhiConfig()
        mock_appsettings.return_value = {'password': 'hunter2', 'session.secret': 'ssshhhhh',
                                         'authtkt.secret': 'keepitsafe'}

        c.load_config()

        mock_appsettings.assert_called_once_with('/some/config.ini')
        assert ('password', 'hunter2') in c.items()
        assert c.loaded

    @mock.patch('bodhi.server.config.get_appsettings')
    def test_validates(self, get_appsettings):
        """Test that the config is validated."""
        c = config.BodhiConfig()

        with pytest.raises(ValueError) as exc:
            c.load_config({'authtkt.secure': 'not a bool', 'session.secret': 'secret',
                           'authtkt.secret': 'secret'})

        assert (str(exc.value) == (
            'Invalid config values were set: \n\tauthtkt.secure: "not a bool" cannot be '
            'interpreted as a boolean value.'))

    @mock.patch('bodhi.server.config.get_appsettings')
    def test_with_settings(self, get_appsettings):
        """Test with the optional settings parameter."""
        c = config.BodhiConfig()

        c.load_config({'wiki_url': 'test', 'session.secret': 'secret', 'authtkt.secret': 'secret'})

        assert c['wiki_url'] == 'test'
        assert get_appsettings.call_count == 0

    @mock.patch('bodhi.server.config.log.error')
    @mock.patch('os.path.exists', return_value=False)
    def test_get_config_unable_to_find_file(self, exists, log_error):
        """Test we log an error if get_configfile() doesn't find a config file"""
        config.get_configfile()

        log_error.assert_called_once_with("Unable to find configuration to load!")


class TestBodhiConfigLoadDefaultsTests:
    """Test the BodhiConfig._load_defaults() method."""
    @mock.patch.dict('bodhi.server.config.BodhiConfig._defaults', {'one': {'value': 'default'}},
                     clear=True)
    def test_load_defaults(self):
        c = config.BodhiConfig()

        c._load_defaults()

        assert c == {'one': 'default'}


class TestBodhiConfigValidate:

    def test_dogpile_expire_is_int(self):
        """The dogpile.cache.expiration_time setting should be an int."""
        c = config.BodhiConfig()
        c.load_config()
        c['dogpile.cache.expiration_time'] = '3600'

        c._validate()

        assert isinstance(c['dogpile.cache.expiration_time'], int)
        assert c['dogpile.cache.expiration_time'] == 3600

    def test_koji_settings_are_strs(self):
        """
        Ensure that the koji related settings are strings.

        This test ensures that #1624[0] stays fixed.

        [0] https://github.com/fedora-infra/bodhi/issues/1624
        """
        c = config.BodhiConfig()
        c.load_config()
        # Let's set all of these to unicodes, and we'll assert that they get turned into strs.
        c['koji_hub'] = 'http://example.com/kojihub'
        c['krb_ccache'] = '/tmp/krb5cc_%{uid}'
        c['krb_keytab'] = '/etc/krb5.bodhi.keytab'
        c['krb_principal'] = 'bodhi/bodhi@FEDORAPROJECT.ORG'

        # This should not raise an Exception, but it should convert the above to strs.
        c._validate()

        for k in ('koji_hub', 'krb_ccache', 'krb_keytab', 'krb_principal'):
            assert type(c[k]) == str
        # And the values should match what we did above.
        assert c['koji_hub'] == 'http://example.com/kojihub'
        assert c['krb_ccache'] == '/tmp/krb5cc_%{uid}'
        assert c['krb_keytab'] == '/etc/krb5.bodhi.keytab'
        assert c['krb_principal'] == 'bodhi/bodhi@FEDORAPROJECT.ORG'

    def test_composer_paths_not_checked_for_existing(self):
        """We don't want compose specific paths to be checked for existence."""
        c = config.BodhiConfig()
        c.load_config()
        for s in ('pungi.cmd', 'compose_dir', 'compose_stage_dir'):
            c[s] = '/does/not/exist'

            # This should not raise an Exception.
            c._validate()

            assert c[s] == '/does/not/exist'

    def test_valid_config(self):
        """A valid config should not raise Exceptions."""
        c = config.BodhiConfig()
        c.load_config({'session.secret': 'secret', 'authtkt.secret': 'secret'})

        # This should not raise an Exception
        c._validate()


class TestGenerateListValidatorTests:
    """Tests the _generate_list_validator() function."""
    def test_custom_splitter(self):
        """Test with a non-default splitter."""
        result = config._generate_list_validator('|')('thing 1| thing 2')

        assert result == ['thing 1', 'thing 2']
        assert all([isinstance(v, str) for v in result])

    def test_custom_validator(self):
        """Test with a non-default validator."""
        result = config._generate_list_validator(validator=int)('1 23 456')

        assert result == [1, 23, 456]
        assert all([isinstance(v, int) for v in result])

    def test_with_defaults(self):
        """Test with the default parameters."""
        result = config._generate_list_validator()('play it again sam')

        assert result == ['play', 'it', 'again', 'sam']
        assert all([isinstance(v, str) for v in result])

    def test_with_list(self):
        """Test with a list."""
        result = config._generate_list_validator(validator=int)(['1', '23', 456])

        assert result == [1, 23, 456]
        assert all([isinstance(v, int) for v in result])

    def test_wrong_type(self):
        """Test with a non string, non list data type."""
        with pytest.raises(ValueError) as exc:
            config._generate_list_validator()({'lol': 'wut'})

        assert str(exc.value) == '"{\'lol\': \'wut\'}" cannot be interpreted as a list.'


class TestValidateBoolTests:
    """This class contains tests for the _validate_bool() function."""
    def test_bool(self):
        """Test with boolean values."""
        assert not config._validate_bool(False)
        assert config._validate_bool(True)

    def test_other(self):
        """Test with a non-string and non-bool type."""
        with pytest.raises(ValueError) as exc:
            config._validate_bool({'not a': 'bool'})

        assert str(exc.value) == "\"{'not a': 'bool'}\" is not a bool or a string."

    def test_string_falsey(self):
        """Test with "falsey" strings."""
        for s in ('f', 'false', 'n', 'no', 'off', '0'):
            assert not config._validate_bool(s)

    def test_string_other(self):
        """Test with an ambiguous string."""
        with pytest.raises(ValueError) as exc:
            config._validate_bool('oops typo')

        assert str(exc.value) == '"oops typo" cannot be interpreted as a boolean value.'

    def test_string_truthy(self):
        """Test with "truthy" strings."""
        for s in ('t', 'true', 'y', 'yes', 'on', '1'):
            assert config._validate_bool(s)


class TestValidateNoneOrTests:
    """Test the _validate_none_or() function."""
    def test_with_none(self):
        """Assert that None is allowed."""
        result = config._validate_none_or(str)(None)

        assert result is None

    def test_with_string(self):
        """Assert that a string is validated and converted to unicode."""
        result = config._validate_none_or(str)('unicode?')

        assert result == 'unicode?'
        assert isinstance(result, str)


class TestValidatePathTests:
    """Test the _validate_path() function."""
    def test_path_does_not_exist(self):
        """Test with a path that does not exist."""
        with pytest.raises(ValueError) as exc:
            config.validate_path('/does/not/exist')

        assert str(exc.value) == "'/does/not/exist' does not exist."

    def test_path_is_none(self):
        """Test with a None value."""
        with pytest.raises(ValueError) as exc:
            config.validate_path(None)

        assert str(exc.value) == "None does not exist."

    def test_path_exists(self):
        """Test with a path that exists."""
        result = config.validate_path(__file__)

        assert result == __file__
        assert isinstance(result, str)


class TestValidateRstrippedStrTests:
    """Test the _validate_rstripped_str() function."""
    def test_with_trailing_slash(self):
        """Ensure that a trailing slash is removed."""
        result = config._validate_rstripped_str('this/should/be/rstripped/')

        assert result == 'this/should/be/rstripped'

    def test_without_trailing_slash(self):
        """With no trailing slash, the string should be returned as is."""
        result = config._validate_rstripped_str('this/should/stay/the/same')

        assert result == 'this/should/stay/the/same'


class TestValidateSecretTests:
    """Test the _validate_secret() function."""
    def test_with_changeme(self):
        """Ensure that CHANGEME raises a ValueError."""
        with pytest.raises(ValueError) as exc:
            config._validate_secret('CHANGEME')

        assert str(exc.value) == 'This setting must be changed from its default value.'

    def test_with_secret(self):
        """Ensure that a secret gets changed to a unicode."""
        result = config._validate_secret('secret')

        assert result == 'secret'
        assert isinstance(result, str)


class TestValidateTLSURL:
    """Test the _validate_tls_url() function."""
    def test_with_http(self):
        """Ensure that http:// URLs raise a ValueError."""
        with pytest.raises(ValueError) as exc:
            config._validate_tls_url('http://example.com')

        assert str(exc.value) == 'This setting must be a URL starting with https://.'

    def test_with_https(self):
        """Ensure that https:// urls get converted to unicode."""
        result = config._validate_tls_url('https://example.com')

        assert result == 'https://example.com'
        assert isinstance(result, str)


class TestGenerateDictValidatorTests:
    """Tests the _generate_dict_validator() function."""
    def test_values_stripped(self):
        """Test whitespaces are stripped from final keys - values."""
        result = config._generate_dict_validator('key 1: value 1 , key 2 : value 2')
        assert result == {'key 1': 'value 1', 'key 2': 'value 2'}

    def test_with_dict(self):
        """Test with a dict."""
        result = config._generate_dict_validator({'key 1': 'value 1', 'key 2': 'value 2'})
        assert result == {'key 1': 'value 1', 'key 2': 'value 2'}

    def test_wrong_format(self):
        """Test with values in wrong format."""
        with pytest.raises(ValueError) as exc:
            config._generate_dict_validator('key 1 value 1, key 2, value 2')

        assert str(exc.value) == '"key 1 value 1, key 2, value 2" cannot be interpreted as a dict.'

    def test_wrong_type(self):
        """Test with a non string, non dict data type."""
        with pytest.raises(ValueError) as exc:
            config._generate_dict_validator(['lol', 'wut'])

        assert str(exc.value) == '"[\'lol\', \'wut\']" cannot be interpreted as a dict.'
