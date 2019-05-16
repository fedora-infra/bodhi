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
import unittest

from bodhi.server import config


class BodhiConfigGetItemTests(unittest.TestCase):
    """Tests for the ``__getitem__`` method on the :class:`BodhiConfig` class."""

    def setUp(self):
        self.config = config.BodhiConfig()
        self.config.load_config = mock.Mock()
        self.config['password'] = 'hunter2'

    def test_not_loaded(self):
        """Assert calling ``__getitem__`` causes the config to load."""
        self.assertFalse(self.config.loaded)
        self.assertEqual('hunter2', self.config['password'])
        self.config.load_config.assert_called_once()

    def test_loaded(self):
        """Assert calling ``__getitem__`` when the config is loaded doesn't reload the config."""
        self.config.loaded = True

        self.assertEqual('hunter2', self.config['password'])
        self.assertEqual(0, self.config.load_config.call_count)

    def test_missing(self):
        """Assert you still get normal dictionary errors from the config."""
        self.assertRaises(KeyError, self.config.__getitem__, 'somemissingkey')


class BodhiConfigGetTests(unittest.TestCase):
    """Tests for the ``get`` method on the :class:`BodhiConfig` class."""

    def setUp(self):
        self.config = config.BodhiConfig()
        self.config.load_config = mock.Mock()
        self.config['password'] = 'hunter2'

    def test_not_loaded(self):
        """Assert calling ``get`` causes the config to load."""
        self.assertFalse(self.config.loaded)
        self.assertEqual('hunter2', self.config.get('password'))
        self.config.load_config.assert_called_once()

    def test_loaded(self):
        """Assert calling ``get`` when the config is loaded doesn't reload the config."""
        self.config.loaded = True

        self.assertEqual('hunter2', self.config.get('password'))
        self.assertEqual(0, self.config.load_config.call_count)

    def test_missing(self):
        """Assert you get ``None`` when the key is missing."""
        self.assertEqual(None, self.config.get('somemissingkey'))


class BodhiConfigPopItemTests(unittest.TestCase):
    """Tests for the ``pop`` method on the :class:`BodhiConfig` class."""

    def setUp(self):
        self.config = config.BodhiConfig()
        self.config.load_config = mock.Mock()
        self.config['password'] = 'hunter2'

    def test_not_loaded(self):
        """Assert calling ``pop`` causes the config to load."""
        self.assertFalse(self.config.loaded)
        self.assertEqual('hunter2', self.config.pop('password'))
        self.config.load_config.assert_called_once()

    def test_loaded(self):
        """Assert calling ``pop`` when the config is loaded doesn't reload the config."""
        self.config.loaded = True

        self.assertEqual('hunter2', self.config.pop('password'))
        self.assertEqual(0, self.config.load_config.call_count)

    def test_removes(self):
        """Assert the configuration is removed with ``pop``."""
        self.assertEqual('hunter2', self.config.pop('password'))
        self.assertRaises(KeyError, self.config.pop, 'password')

    def test_get_missing(self):
        """Assert you still get normal dictionary errors from the config."""
        self.assertRaises(KeyError, self.config.pop, 'somemissingkey')


class BodhiConfigCopyTests(unittest.TestCase):
    """Tests for the ``copy`` method on the :class:`BodhiConfig` class."""

    def setUp(self):
        self.config = config.BodhiConfig()
        self.config.load_config = mock.Mock()
        self.config['password'] = 'hunter2'

    def test_not_loaded(self):
        """Assert calling ``copy`` causes the config to load."""
        self.assertFalse(self.config.loaded)
        self.assertEqual({'password': 'hunter2'}, self.config.copy())
        self.config.load_config.assert_called_once()

    def test_loaded(self):
        """Assert calling ``copy`` when the config is loaded doesn't reload the config."""
        self.config.loaded = True

        self.assertEqual({'password': 'hunter2'}, self.config.copy())
        self.assertEqual(0, self.config.load_config.call_count)


class BodhiConfigLoadConfig(unittest.TestCase):

    @mock.patch('bodhi.server.config.get_appsettings')
    def test_loads_defaults(self, get_appsettings):
        """Test that defaults are loaded."""
        c = config.BodhiConfig()

        c.load_config({'session.secret': 'secret', 'authtkt.secret': 'secret'})

        self.assertEqual(c['top_testers_timeframe'], 7)

    @mock.patch('bodhi.server.config.get_configfile', mock.Mock(return_value='/some/config.ini'))
    @mock.patch('bodhi.server.config.get_appsettings')
    def test_marks_loaded(self, mock_appsettings):
        c = config.BodhiConfig()
        mock_appsettings.return_value = {'password': 'hunter2', 'session.secret': 'ssshhhhh',
                                         'authtkt.secret': 'keepitsafe'}

        c.load_config()

        mock_appsettings.assert_called_once_with('/some/config.ini')
        self.assertTrue(('password', 'hunter2') in c.items())
        self.assertTrue(c.loaded)

    @mock.patch('bodhi.server.config.get_appsettings')
    def test_validates(self, get_appsettings):
        """Test that the config is validated."""
        c = config.BodhiConfig()

        with self.assertRaises(ValueError) as exc:
            c.load_config({'authtkt.secure': 'not a bool', 'session.secret': 'secret',
                           'authtkt.secret': 'secret'})

        self.assertEqual(
            str(exc.exception),
            ('Invalid config values were set: \n\tauthtkt.secure: "not a bool" cannot be '
             'interpreted as a boolean value.'))

    @mock.patch('bodhi.server.config.get_appsettings')
    def test_with_settings(self, get_appsettings):
        """Test with the optional settings parameter."""
        c = config.BodhiConfig()

        c.load_config({'wiki_url': 'test', 'session.secret': 'secret', 'authtkt.secret': 'secret'})

        self.assertEqual(c['wiki_url'], 'test')
        self.assertEqual(get_appsettings.call_count, 0)

    @mock.patch('bodhi.server.config.log.error')
    @mock.patch('os.path.exists', return_value=False)
    def test_get_config_unable_to_find_file(self, exists, log_error):
        """Test we log an error if get_configfile() doesn't find a config file"""
        config.get_configfile()

        log_error.assert_called_once_with("Unable to find configuration to load!")


class BodhiConfigLoadDefaultsTests(unittest.TestCase):
    """Test the BodhiConfig._load_defaults() method."""
    @mock.patch.dict('bodhi.server.config.BodhiConfig._defaults', {'one': {'value': 'default'}},
                     clear=True)
    def test_load_defaults(self):
        c = config.BodhiConfig()

        c._load_defaults()

        self.assertEqual(c, {'one': 'default'})


class BodhiConfigValidate(unittest.TestCase):

    def test_dogpile_expire_is_int(self):
        """The dogpile.cache.expiration_time setting should be an int."""
        c = config.BodhiConfig()
        c.load_config()
        c['dogpile.cache.expiration_time'] = '3600'

        c._validate()

        self.assertTrue(isinstance(c['dogpile.cache.expiration_time'], int))
        self.assertEqual(c['dogpile.cache.expiration_time'], 3600)

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
            self.assertEqual(type(c[k]), str)
        # And the values should match what we did above.
        self.assertEqual(c['koji_hub'], 'http://example.com/kojihub')
        self.assertEqual(c['krb_ccache'], '/tmp/krb5cc_%{uid}')
        self.assertEqual(c['krb_keytab'], '/etc/krb5.bodhi.keytab')
        self.assertEqual(c['krb_principal'], 'bodhi/bodhi@FEDORAPROJECT.ORG')

    def test_composer_paths_not_checked_for_existing(self):
        """We don't want compose specific paths to be checked for existence."""
        c = config.BodhiConfig()
        c.load_config()
        for s in ('pungi.cmd', 'compose_dir', 'compose_stage_dir'):
            c[s] = '/does/not/exist'

            # This should not raise an Exception.
            c._validate()

            self.assertEqual(c[s], '/does/not/exist')

    def test_valid_config(self):
        """A valid config should not raise Exceptions."""
        c = config.BodhiConfig()
        c.load_config({'session.secret': 'secret', 'authtkt.secret': 'secret'})

        # This should not raise an Exception
        c._validate()


class GenerateListValidatorTests(unittest.TestCase):
    """Tests the _generate_list_validator() function."""
    def test_custom_splitter(self):
        """Test with a non-default splitter."""
        result = config._generate_list_validator('|')('thing 1| thing 2')

        self.assertEqual(result, ['thing 1', 'thing 2'])
        self.assertTrue(all([isinstance(v, str) for v in result]))

    def test_custom_validator(self):
        """Test with a non-default validator."""
        result = config._generate_list_validator(validator=int)('1 23 456')

        self.assertEqual(result, [1, 23, 456])
        self.assertTrue(all([isinstance(v, int) for v in result]))

    def test_with_defaults(self):
        """Test with the default parameters."""
        result = config._generate_list_validator()('play it again sam')

        self.assertEqual(result, ['play', 'it', 'again', 'sam'])
        self.assertTrue(all([isinstance(v, str) for v in result]))

    def test_with_list(self):
        """Test with a list."""
        result = config._generate_list_validator(validator=int)(['1', '23', 456])

        self.assertEqual(result, [1, 23, 456])
        self.assertTrue(all([isinstance(v, int) for v in result]))

    def test_wrong_type(self):
        """Test with a non string, non list data type."""
        with self.assertRaises(ValueError) as exc:
            config._generate_list_validator()({'lol': 'wut'})

        self.assertEqual(str(exc.exception),
                         '"{\'lol\': \'wut\'}" cannot be interpreted as a list.')


class ValidateBoolTests(unittest.TestCase):
    """This class contains tests for the _validate_bool() function."""
    def test_bool(self):
        """Test with boolean values."""
        self.assertTrue(config._validate_bool(False) is False)
        self.assertTrue(config._validate_bool(True) is True)

    def test_other(self):
        """Test with a non-string and non-bool type."""
        with self.assertRaises(ValueError) as exc:
            config._validate_bool({'not a': 'bool'})

        self.assertEqual(str(exc.exception), "\"{'not a': 'bool'}\" is not a bool or a string.")

    def test_string_falsey(self):
        """Test with "falsey" strings."""
        for s in ('f', 'false', 'n', 'no', 'off', '0'):
            self.assertTrue(config._validate_bool(s) is False)

    def test_string_other(self):
        """Test with an ambiguous string."""
        with self.assertRaises(ValueError) as exc:
            config._validate_bool('oops typo')

        self.assertEqual(str(exc.exception),
                         '"oops typo" cannot be interpreted as a boolean value.')

    def test_string_truthy(self):
        """Test with "truthy" strings."""
        for s in ('t', 'true', 'y', 'yes', 'on', '1'):
            self.assertTrue(config._validate_bool(s) is True)


class ValidateNoneOrTests(unittest.TestCase):
    """Test the _validate_none_or() function."""
    def test_with_none(self):
        """Assert that None is allowed."""
        result = config._validate_none_or(str)(None)

        self.assertTrue(result is None)

    def test_with_string(self):
        """Assert that a string is validated and converted to unicode."""
        result = config._validate_none_or(str)('unicode?')

        self.assertEqual(result, 'unicode?')
        self.assertTrue(isinstance(result, str))


class ValidatePathTests(unittest.TestCase):
    """Test the _validate_path() function."""
    def test_path_does_not_exist(self):
        """Test with a path that does not exist."""
        with self.assertRaises(ValueError) as exc:
            config.validate_path('/does/not/exist')

        self.assertEqual(str(exc.exception), "'/does/not/exist' does not exist.")

    def test_path_is_none(self):
        """Test with a None value."""
        with self.assertRaises(ValueError) as exc:
            config.validate_path(None)

        self.assertEqual(str(exc.exception), "None does not exist.")

    def test_path_exists(self):
        """Test with a path that exists."""
        result = config.validate_path(__file__)

        self.assertEqual(result, __file__)
        self.assertTrue(isinstance(result, str))


class ValidateRstrippedStrTests(unittest.TestCase):
    """Test the _validate_rstripped_str() function."""
    def test_with_trailing_slash(self):
        """Ensure that a trailing slash is removed."""
        result = config._validate_rstripped_str('this/should/be/rstripped/')

        self.assertEqual(result, 'this/should/be/rstripped')

    def test_without_trailing_slash(self):
        """With no trailing slash, the string should be returned as is."""
        result = config._validate_rstripped_str('this/should/stay/the/same')

        self.assertEqual(result, 'this/should/stay/the/same')


class ValidateSecretTests(unittest.TestCase):
    """Test the _validate_secret() function."""
    def test_with_changeme(self):
        """Ensure that CHANGEME raises a ValueError."""
        with self.assertRaises(ValueError) as exc:
            config._validate_secret('CHANGEME')

        self.assertEqual(str(exc.exception), 'This setting must be changed from its default value.')

    def test_with_secret(self):
        """Ensure that a secret gets changed to a unicode."""
        result = config._validate_secret('secret')

        self.assertEqual(result, 'secret')
        self.assertTrue(isinstance(result, str))


class ValidateTLSURL(unittest.TestCase):
    """Test the _validate_tls_url() function."""
    def test_with_http(self):
        """Ensure that http:// URLs raise a ValueError."""
        with self.assertRaises(ValueError) as exc:
            config._validate_tls_url('http://example.com')

        self.assertEqual(str(exc.exception), 'This setting must be a URL starting with https://.')

    def test_with_https(self):
        """Ensure that https:// urls get converted to unicode."""
        result = config._validate_tls_url('https://example.com')

        self.assertEqual(result, 'https://example.com')
        self.assertTrue(isinstance(result, str))
