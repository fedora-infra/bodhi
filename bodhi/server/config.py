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
import os
import logging

from pyramid import settings
from pyramid.paster import get_appsettings
import cryptography.fernet


log = logging.getLogger('bodhi')


def get_configfile():
    configfile = None
    setupdir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..')
    if configfile:
        if not os.path.exists(configfile):
            log.error("Cannot find config: %s" % configfile)
            return
    else:
        for cfg in (os.path.join(setupdir, 'development.ini'),
                    '/etc/bodhi/production.ini'):
            if os.path.exists(cfg):
                configfile = cfg
                break
        else:
            log.error("Unable to find configuration to load!")
    return configfile


def _generate_list_validator(splitter=' ', validator=unicode):
    """Return a function that takes a value and interprets it to be a list with the given splitter.

    This function generates a function that can take a string and interpret it as a list by
    splitting with the given splitter string. Each element of the resulting list is then validated
    with the given validator.

    Args:
        splitter (basestring): A string to use to split the input into a list.
        validator (function):  A function to apply to each element of the list to validate it.
    Returns:
        function: A validator function that accepts an argument to be validated.
    """
    def _validate_list(value):
        """Validate that the value is a list or can be split into a list, and validate its elements.

        This function will validate that the given value is a list, or it will use the splitter to
        turn it into a list. Once it is a list, it will use the validator on each element of the
        list.

        Args:
            value (basestring or list): The list to be validated.
        Returns:
            unicode: The interpreted list.
        Raises:
            ValueError: If validator fails on any of the list's elements.
        """
        if isinstance(value, basestring):
            value = [idx.strip() for idx in value.split(splitter) if idx.strip()]

        if not isinstance(value, list):
            raise ValueError('"{}" cannot be intepreted as a list.'.format(value))

        # Run the validator on each element of the list.
        value = [validator(v) for v in value]

        return value

    return _validate_list


def _validate_bool(value):
    """Return a bool version of value.

    This function will ensure that value is a bool, or that it is a string that can be interpreted
    as a bool. It will return a bool. If it cannot do that, it will raise ValueError.

    Args:
        value (basestring or bool): The value to be validated as a bool.
    Returns:
        bool: The boolean interpretation of value.
    Raises:
        ValueError: If value cannot be interpreted as a boolean.
    """
    if isinstance(value, basestring):
        # Recent versions of Pyramid define a settings.falsey, but version 1.5.6 does not so its
        # values have been backported here for the False case. Pyramid defines an asbool(), but it
        # will not raise any error for strings that aren't in the truthy or falsey lists, and we
        # want strict validation.
        if value.lower().strip() in settings.truthy:
            return True
        elif value.lower().strip() in ('f', 'false', 'n', 'no', 'off', '0'):
            return False
        else:
            raise ValueError('"{}" cannot be interpreted as a boolean value.'.format(value))

    if not isinstance(value, bool):
        raise ValueError('"{}" is not a bool or a string.'.format(value))

    return value


def _validate_color(value):
    """Ensure that value is a valid expression of a color, in the form #dddddd.

    Return the value if it is a valid color expression, or raise ValueError.

    Args:
        value (basestring): The color to be validated.
    Returns:
        unicode: The color.
    Raises:
        ValueError: If value is not in the form #dddddd.
    """
    e = ValueError('"{}" is not a valid color expression.'.format(value))

    if not isinstance(value, basestring):
        raise e
    if not len(value) == 7:
        raise e
    if value[0] != '#':
        raise e
    try:
        int(value[-6:], 16)
    except ValueError:
        raise e

    return unicode(value)


def _validate_fernet_key(value):
    """Ensure the value is not CHANGEME, that it is a Fernet key, and convert it to a str.

    This function is used to ensure that secret values in the config have been set by the user to
    something other than the default of CHANGEME and that the value can be used as a Fernet key. It
    is converted to unicode before returning.

    Args:
        value (basestring): The value to be validated.
    Returns:
        unicode: The value.
    Raises:
        ValueError: If value is "CHANGEME" or if it cannot be used as a Fernet key.
    """
    _validate_secret(value)

    if isinstance(value, unicode):
        value = value.encode('utf-8')

    try:
        engine = cryptography.fernet.Fernet(value)
        # This will raise a ValueError if value is not suitable as a Fernet key.
        engine.encrypt('a secret test string')
    except TypeError:
        raise ValueError('Fernet key must be 32 url-safe base64-encoded bytes.')

    return value


def _validate_none_or(validator):
    """Return a function that will ensure a value is None or passes validator.

    This function returns a function that will take a single argument, value, and will ensure
    that value is None or that it passes the given validator.

    Args:
        validator (function): A function to apply when value is not None.
    Returns:
        function: A validator function that accepts an argument to be validated.
    """
    def _validate(value):
        if value is None:
            return value

        return validator(value)

    return _validate


def _validate_path(value):
    """Ensure that value is an existing path on the local filesystem and return it.

    Use os.path.exists to ensure that value is an existing path. Return the value if it is, else
    raise ValueError.

    Args:
        value (basestring): The path to be validated.
    Returns:
        unicode: The path.
    Raises:
        ValueError: If os.path.exists returns False.
    """
    if not os.path.exists(value):
        raise ValueError('"{}" does not exist.'.format(value))

    return unicode(value)


def _validate_secret(value):
    """Ensure that the value is not CHANGEME and convert it to unicode.

    This function is used to ensure that secret values in the config have been set by the user to
    something other than the default of CHANGEME.

    Args:
        value (basestring): The value to be validated.
    Returns:
        unicode: The value.
    Raises:
        ValueError: If value is "CHANGEME".
    """
    if value == 'CHANGEME':
        raise ValueError('This setting must be changed from its default value.')

    return unicode(value)


def _validate_tls_url(value):
    """Ensure that the value is a string that starts with https://.

    Args:
        value (basestring): The value to be validated.
    Returns:
        unicode: The value.
    Raises:
        ValueError: If value is not a string starting with https://.
    """
    if not isinstance(value, basestring) or not value.startswith('https://'):
        raise ValueError('This setting must be a URL starting with https://.')

    return unicode(value)


class BodhiConfig(dict):
    loaded = False

    _defaults = {
        'acl_system': {
            'value': 'dummy',
            'validator': unicode},
        'admin_groups': {
            'value': ['proventesters', 'security_respons', 'bodhiadmin', 'sysadmin-main'],
            'validator': _generate_list_validator()},
        'admin_packager_groups': {
            'value': ['provenpackager', 'releng', 'security_respons'],
            'validator': _generate_list_validator()},
        'authtkt.secret': {
            'value': 'CHANGEME',
            'validator': _validate_secret},
        'authtkt.secure': {
            'value': True,
            'validator': _validate_bool},
        'authtkt.timeout': {
            'value': 86400,
            'validator': int},
        'badge_ids': {
            'value': [],
            'validator': _generate_list_validator('|')},
        'base_address': {
            'value': 'https://admin.fedoraproject.org/updates/',
            'validator': unicode},
        'bodhi_email': {
            'value': 'updates@fedoraproject.org',
            'validator': unicode},
        'bodhi_password': {
            'value': None,
            'validator': _validate_none_or(unicode)},
        'buglink': {
            'value': 'https://bugzilla.redhat.com/show_bug.cgi?id=%s',
            'validator': unicode},
        'bugtracker': {
            'value': None,
            'validator': _validate_none_or(unicode)},
        'buildroot_limit': {
            'value': 31,
            'validator': int},
        'buildsystem': {
            'value': 'dev',
            'validator': unicode},
        'bz_products': {
            'value': [],
            'validator': _generate_list_validator(',')},
        'bz_server': {
            'value': 'https://bugzilla.redhat.com/xmlrpc.cgi',
            'validator': unicode},
        'captcha.background_color': {
            'value': '#ffffff',
            'validator': _validate_color},
        'captcha.font_color': {
            'value': '#000000',
            'validator': _validate_color},
        'captcha.font_path': {
            'value': '/usr/share/fonts/liberation/LiberationMono-Regular.ttf',
            'validator': _validate_path},
        'captcha.font_size': {
            'value': 36,
            'validator': int},
        'captcha.image_height': {
            'value': 80,
            'validator': int},
        'captcha.image_width': {
            'value': 300,
            'validator': int},
        'captcha.padding': {
            'value': 5,
            'validator': int},
        'captcha.secret': {
            'value': None,
            'validator': _validate_none_or(_validate_fernet_key)},
        'captcha.ttl': {
            'value': 300,
            'validator': int},
        'ci.required': {
            'value': False,
            'validator': _validate_bool},
        'ci.url': {
            'value': '',
            'validator': unicode},
        'compose_atomic_trees': {
            'value': False,
            'validator': _validate_bool},
        'comps_dir': {
            'value': os.path.join(os.path.dirname(__file__), '..', '..', 'masher', 'comps'),
            'validator': unicode},
        'comps_url': {
            'value': 'https://git.fedorahosted.org/comps.git',
            'validator': _validate_tls_url},
        'cors_connect_src': {
            'value': 'https://*.fedoraproject.org/ wss://hub.fedoraproject.org:9939/',
            'validator': unicode},
        'cors_origins_ro': {
            'value': '*',
            'validator': unicode},
        'cors_origins_rw': {
            'value': 'https://bodhi.fedoraproject.org',
            'validator': unicode},
        'critpath_pkgs': {
            'value': [],
            'validator': _generate_list_validator()},
        'critpath.min_karma': {
            'value': 2,
            'validator': int},
        'critpath.num_admin_approvals': {
            'value': 2,
            'validator': int},
        'critpath.stable_after_days_without_negative_karma': {
            'value': 14,
            'validator': int},
        'critpath.type': {
            'value': None,
            'validator': _validate_none_or(unicode)},
        'datagrepper_url': {
            'value': 'https://apps.fedoraproject.org/datagrepper',
            'validator': unicode},
        'default_email_domain': {
            'value': 'fedoraproject.org',
            'validator': unicode},
        'disable_automatic_push_to_stable': {
            'value': (
                'Bodhi is disabling automatic push to stable due to negative karma. The '
                'maintainer may push manually if they determine that the issue is not severe.'),
            'validator': unicode},
        'dogpile.cache.arguments.filename': {
            'value': '/var/cache/bodhi-dogpile-cache.dbm',
            'validator': unicode},
        'dogpile.cache.backend': {
            'value': 'dogpile.cache.dbm',
            'validator': unicode},
        'dogpile.cache.expiration_time': {
            'value': '100',
            'validator': unicode},
        'exclude_mail': {
            'value': ['autoqa', 'taskotron'],
            'validator': _generate_list_validator()},
        'fedmenu.data_url': {
            'value': 'https://apps.fedoraproject.org/js/data.js',
            'validator': unicode},
        'fedmenu.url': {
            'value': 'https://apps.fedoraproject.org/fedmenu',
            'validator': unicode},
        'fedmsg_enabled': {
            'value': False,
            'validator': _validate_bool},
        'file_url': {
            'value': 'https://download.fedoraproject.org/pub/fedora/linux/updates',
            'validator': unicode},
        'fmn_url': {
            'value': 'https://apps.fedoraproject.org/notifications/',
            'validator': unicode},
        'important_groups': {
            'value': ['proventesters', 'provenpackager,' 'releng', 'security_respons', 'packager',
                      'bodhiadmin'],
            'validator': _generate_list_validator()},
        'initial_bug_msg': {
            'value': '%s has been submitted as an update to %s. %s',
            'validator': unicode},
        'koji_hub': {
            'value': 'https://koji.stg.fedoraproject.org/kojihub',
            'validator': str},
        'krb_ccache': {
            'value': None,
            'validator': _validate_none_or(str)},
        'krb_keytab': {
            'value': None,
            'validator': _validate_none_or(str)},
        'krb_principal': {
            'value': None,
            'validator': _validate_none_or(str)},
        'libravatar_dns': {
            'value': False,
            'validator': _validate_bool},
        'libravatar_enabled': {
            'value': True,
            'validator': _validate_bool},
        'mako.directories': {
            'value': 'bodhi:server/templates',
            'validator': unicode},
        'mandatory_packager_groups': {
            'value': ['packager'],
            'validator': _generate_list_validator()},
        'mash_conf': {
            'value': '/etc/mash/mash.conf',
            'validator': unicode},
        'mash_dir': {
            'value': None,
            'validator': _validate_none_or(_validate_path)},
        'mash_stage_dir': {
            'value': None,
            'validator': _validate_none_or(_validate_path)},
        'max_update_length_for_ui': {
            'value': 30,
            'validator': int},
        'message_id_email_domain': {
            'value': 'admin.fedoraproject.org',
            'validator': unicode},
        'not_yet_tested_epel_msg': {
            'value': (
                'This update has not yet met the minimum testing requirements defined in the '
                '<a href="https://fedoraproject.org/wiki/EPEL_Updates_Policy">EPEL Update Policy'
                '</a>'),
            'validator': unicode},
        'not_yet_tested_msg': {
            'value': (
                'This update has not yet met the minimum testing requirements defined in the '
                '<a href="https://fedoraproject.org/wiki/Package_update_acceptance_criteria">'
                'Package Update Acceptance Criteria</a>'),
            'validator': unicode},
        'openid.provider': {
            'value': 'https://id.fedoraproject.org/openid/',
            'validator': unicode},
        'openid.sreg_required': {
            'value': 'email',
            'validator': unicode},
        'openid.success_callback': {
            'value': 'bodhi.server.security:remember_me',
            'validator': unicode},
        'openid.url': {
            'value': 'https://id.fedoraproject.org/',
            'validator': unicode},
        'openid_template': {
            'value': '{username}.id.fedoraproject.org',
            'validator': unicode},
        'pagure_url': {
            'value': 'https://src.fedoraproject.org/pagure/',
            'validator': _validate_tls_url},
        'pdc_url': {
            'value': 'https://pdc.fedoraproject.org/',
            'validator': _validate_tls_url},
        'pkgdb_url': {
            'value': 'https://admin.fedoraproject.org/pkgdb',
            'validator': unicode},
        'pkgtags_url': {
            'value': '',
            'validator': unicode},
        'query_wiki_test_cases': {
            'value': False,
            'validator': _validate_bool},
        'release_team_address': {
            'value': 'bodhiadmin-members@fedoraproject.org',
            'validator': unicode},
        'resultsdb_api_url': {
            'value': 'https://taskotron.fedoraproject.org/resultsdb_api/',
            'validator': unicode},
        'session.secret': {
            'value': 'CHANGEME',
            'validator': _validate_secret},
        'site_requirements': {
            'value': 'dist.rpmdeplint dist.upgradepath',
            'validator': unicode},
        'smtp_server': {
            'value': None,
            'validator': _validate_none_or(unicode)},
        'sqlalchemy.url': {
            'value': 'sqlite:////var/cache/bodhi.db',
            'validator': unicode},
        'stable_bug_msg': {
            'value': ('%s has been pushed to the %s repository. If problems still persist, please '
                      'make note of it in this bug report.'),
            'validator': unicode},
        'stacks_enabled': {
            'value': False,
            'validator': _validate_bool},
        'stats_blacklist': {
            'value': ['bodhi', 'anonymous', 'autoqa', 'taskotron'],
            'validator': _generate_list_validator()},
        'system_users': {
            'value': ['bodhi', 'autoqa', 'taskotron'],
            'validator': _generate_list_validator()},
        'test_case_base_url': {
            'value': 'https://fedoraproject.org/wiki/',
            'validator': unicode},
        'testing_approval_msg_based_on_karma': {
            'value': ('This update has reached the stable karma threshold and can be pushed to '
                      'stable now if the maintainer wishes.'),
            'validator': unicode
        },
        'testing_approval_msg': {
            'value': ('This update has reached %d days in testing and can be pushed to stable now '
                      'if the maintainer wishes'),
            'validator': unicode},
        'testing_bug_epel_msg': {
            'value': (
                '\nSee https://fedoraproject.org/wiki/QA:Updates_Testing for\ninstructions on how '
                'to install test updates.\nYou can provide feedback for this update here: %s'),
            'validator': unicode},
        'testing_bug_msg': {
            'value': (
                '\nSee https://fedoraproject.org/wiki/QA:Updates_Testing for\ninstructions on how '
                'to install test updates.\nYou can provide feedback for this update here: %s'),
            'validator': unicode},
        'top_testers_timeframe': {
            'value': 7,
            'validator': int},
        'updateinfo_rights': {
            'value': 'Copyright (C) {} Red Hat, Inc. and others.'.format(datetime.now().year),
            'validator': unicode},
        'wiki_url': {
            'value': 'https://fedoraproject.org/w/api.php',
            'validator': unicode},
    }

    def __getitem__(self, *args, **kw):
        if not self.loaded:
            self.load_config()
        return super(BodhiConfig, self).__getitem__(*args, **kw)

    def get(self, *args, **kw):
        if not self.loaded:
            self.load_config()
        return super(BodhiConfig, self).get(*args, **kw)

    def pop(self, *args, **kw):
        if not self.loaded:
            self.load_config()
        return super(BodhiConfig, self).pop(*args, **kw)

    def copy(self, *args, **kw):
        if not self.loaded:
            self.load_config()
        return super(BodhiConfig, self).copy(*args, **kw)

    def load_config(self, settings=None):
        """
        Load the configuration either from the config file, or from the given settings.

        args:
            settings (dict): If given, the settings are pulled from this dictionary. Otherwise, the
                config file is used.
        """
        self._load_defaults()
        configfile = get_configfile()
        if settings:
            self.update(settings)
        else:
            self.update(get_appsettings(configfile))
        self.loaded = True
        self._validate()

    def _load_defaults(self):
        """Iterate over self._defaults and set all default values on self."""
        for k, v in self._defaults.items():
            self[k] = v['value']

    def _validate(self):
        """Run the validators found in self._defaults on all the corresponding values."""
        errors = []
        for k in self._defaults.keys():
            try:
                self[k] = self._defaults[k]['validator'](self[k])
            except ValueError as e:
                errors.append('\t{}: {}'.format(k, unicode(e)))

        if errors:
            raise ValueError(
                'Invalid config values were set: \n{}'.format('\n'.join(errors)))


config = BodhiConfig()
