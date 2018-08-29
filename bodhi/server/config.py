# -*- coding: utf-8 -*-
# Copyright © 2013-2017 Red Hat, Inc. and others.
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
"""Bodhi's configuration and configuration loading and validation mechanisms."""
from datetime import datetime
import os
import logging
import binascii

from pyramid import settings
from pyramid.paster import get_appsettings
import cryptography.fernet
import six


log = logging.getLogger('bodhi')


def get_configfile():
    """
    Return a path to a config file, if found.

    Return the path to a config file, with a heirarchy of preferential paths. It searches first
    for development.ini if found. if not found, it will return /etc/bodhi/production.ini if it
    exists. Otherwise, it returns None.

    Returns:
        basestring or None: The path of a config file, or None if no config file is found.
    """
    configfile = None
    setupdir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..')
    for cfg in (os.path.join(setupdir, 'development.ini'),
                '/etc/bodhi/production.ini'):
        if os.path.exists(cfg):
            configfile = cfg
            break
    else:
        log.error("Unable to find configuration to load!")
    return configfile


def _generate_list_validator(splitter=' ', validator=six.text_type):
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
        if isinstance(value, six.string_types):
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
    if isinstance(value, six.string_types):
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

    if not isinstance(value, six.string_types):
        raise e
    if not len(value) == 7:
        raise e
    if value[0] != '#':
        raise e
    try:
        int(value[-6:], 16)
    except ValueError:
        raise e

    return six.text_type(value)


def _validate_fernet_key(value):
    """Ensure the value is not CHANGEME, that it is a Fernet key, and convert it to a str.

    This function is used to ensure that secret values in the config have been set by the user to
    something other than the default of CHANGEME and that the value can be used as a Fernet key. It
    is converted to str before returning.

    Args:
        value (basestring): The value to be validated.
    Returns:
        str: The value.
    Raises:
        ValueError: If value is "CHANGEME" or if it cannot be used as a Fernet key.
    """
    _validate_secret(value)

    if isinstance(value, six.text_type):
        value = value.encode('utf-8')

    try:
        engine = cryptography.fernet.Fernet(value)
        # This will raise a ValueError if value is not suitable as a Fernet key.
        engine.encrypt(b'a secret test string')
    except (TypeError, binascii.Error):
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


def validate_path(value):
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

    return six.text_type(value)


def _validate_rstripped_str(value):
    """
    Ensure that value is a str that is rstripped of the / character.

    Args:
        value (six.text_type): The value to be validated and rstripped.
    Returns:
        six.text_type: The rstripped value.
    """
    value = six.text_type(value)
    return value.rstrip('/')


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

    return six.text_type(value)


def _validate_tls_url(value):
    """Ensure that the value is a string that starts with https://.

    Args:
        value (basestring): The value to be validated.
    Returns:
        unicode: The value.
    Raises:
        ValueError: If value is not a string starting with https://.
    """
    if not isinstance(value, six.string_types) or not value.startswith('https://'):
        raise ValueError('This setting must be a URL starting with https://.')

    return six.text_type(value)


class BodhiConfig(dict):
    """
    A dictionary interface to the Bodhi configuration.

    This class defines defaults for most of Bodhi's settings, and also provides validation that
    converts them to the expected types.
    """

    loaded = False

    _defaults = {
        'acl_system': {
            'value': 'dummy',
            'validator': six.text_type},
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
            'validator': six.text_type},
        'bodhi_email': {
            'value': 'updates@fedoraproject.org',
            'validator': six.text_type},
        'bodhi_password': {
            'value': None,
            'validator': _validate_none_or(six.text_type)},
        'buglink': {
            'value': 'https://bugzilla.redhat.com/show_bug.cgi?id=%s',
            'validator': six.text_type},
        'bugtracker': {
            'value': None,
            'validator': _validate_none_or(six.text_type)},
        'buildroot_limit': {
            'value': 31,
            'validator': int},
        'buildsystem': {
            'value': 'dev',
            'validator': six.text_type},
        'bz_products': {
            'value': [],
            'validator': _generate_list_validator(',')},
        'bz_server': {
            'value': 'https://bugzilla.redhat.com/xmlrpc.cgi',
            'validator': six.text_type},
        'cache_dir': {
            'value': None,
            'validator': _validate_none_or(validate_path)},
        'captcha.background_color': {
            'value': '#ffffff',
            'validator': _validate_color},
        'captcha.font_color': {
            'value': '#000000',
            'validator': _validate_color},
        'captcha.font_path': {
            'value': '/usr/share/fonts/liberation/LiberationMono-Regular.ttf',
            'validator': validate_path},
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
        'clean_old_composes': {
            'value': True,
            'validator': _validate_bool},
        'container.destination_registry': {
            'value': 'registry.fedoraproject.org',
            'validator': six.text_type},
        'container.source_registry': {
            'value': 'candidate-registry.fedoraproject.org',
            'validator': six.text_type},
        'cors_connect_src': {
            'value': 'https://*.fedoraproject.org/ wss://hub.fedoraproject.org:9939/',
            'validator': six.text_type},
        'cors_origins_ro': {
            'value': '*',
            'validator': six.text_type},
        'cors_origins_rw': {
            'value': 'https://bodhi.fedoraproject.org',
            'validator': six.text_type},
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
            'validator': _validate_none_or(six.text_type)},
        'datagrepper_url': {
            'value': 'https://apps.fedoraproject.org/datagrepper',
            'validator': six.text_type},
        'default_email_domain': {
            'value': 'fedoraproject.org',
            'validator': six.text_type},
        'disable_automatic_push_to_stable': {
            'value': (
                'Bodhi is disabling automatic push to stable due to negative karma. The '
                'maintainer may push manually if they determine that the issue is not severe.'),
            'validator': six.text_type},
        'dogpile.cache.arguments.filename': {
            'value': '/var/cache/bodhi-dogpile-cache.dbm',
            'validator': six.text_type},
        'dogpile.cache.backend': {
            'value': 'dogpile.cache.dbm',
            'validator': six.text_type},
        'dogpile.cache.expiration_time': {
            'value': 100,
            'validator': int},
        'exclude_mail': {
            'value': ['autoqa', 'taskotron'],
            'validator': _generate_list_validator()},
        'fedmenu.data_url': {
            'value': 'https://apps.fedoraproject.org/js/data.js',
            'validator': six.text_type},
        'fedmenu.url': {
            'value': 'https://apps.fedoraproject.org/fedmenu',
            'validator': six.text_type},
        'fedmsg_enabled': {
            'value': False,
            'validator': _validate_bool},
        'file_url': {
            'value': 'https://download.fedoraproject.org/pub/fedora/linux/updates',
            'validator': six.text_type},
        'fmn_url': {
            'value': 'https://apps.fedoraproject.org/notifications/',
            'validator': six.text_type},
        'important_groups': {
            'value': ['proventesters', 'provenpackager,' 'releng', 'security_respons', 'packager',
                      'bodhiadmin'],
            'validator': _generate_list_validator()},
        'initial_bug_msg': {
            'value': '%s has been submitted as an update to %s. %s',
            'validator': six.text_type},
        'greenwave_api_url': {
            'value': 'https://greenwave-web-greenwave.app.os.fedoraproject.org/api/v1.0',
            'validator': _validate_rstripped_str},
        'waiverdb_api_url': {
            'value': 'https://waiverdb-web-waiverdb.app.os.fedoraproject.org/api/v1.0',
            'validator': _validate_rstripped_str},
        'waiverdb.access_token': {
            'value': None,
            'validator': _validate_none_or(six.text_type)},
        'koji_web_url': {
            'value': 'https://koji.fedoraproject.org/koji/',
            'validator': _validate_tls_url},
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
        'legal_link': {
            'value': '',
            'validator': six.text_type},
        'libravatar_dns': {
            'value': False,
            'validator': _validate_bool},
        'libravatar_enabled': {
            'value': True,
            'validator': _validate_bool},
        'mail.templates_basepath': {
            'value': 'bodhi:server/email/templates/',
            'validator': six.text_type},
        'mako.directories': {
            'value': 'bodhi:server/templates',
            'validator': six.text_type},
        'mandatory_packager_groups': {
            'value': ['packager'],
            'validator': _generate_list_validator()},
        'mash_dir': {
            'value': None,
            'validator': _validate_none_or(six.text_type)},
        'mash_stage_dir': {
            'value': None,
            'validator': _validate_none_or(six.text_type)},
        'max_concurrent_mashes': {
            'value': 2,
            'validator': int},
        'max_update_length_for_ui': {
            'value': 30,
            'validator': int},
        'message_id_email_domain': {
            'value': 'admin.fedoraproject.org',
            'validator': six.text_type},
        'not_yet_tested_epel_msg': {
            'value': (
                'This update has not yet met the minimum testing requirements defined in the '
                '<a href="https://fedoraproject.org/wiki/EPEL_Updates_Policy">EPEL Update Policy'
                '</a>'),
            'validator': six.text_type},
        'not_yet_tested_msg': {
            'value': (
                'This update has not yet met the minimum testing requirements defined in the '
                '<a href="https://fedoraproject.org/wiki/Package_update_acceptance_criteria">'
                'Package Update Acceptance Criteria</a>'),
            'validator': six.text_type},
        'openid.provider': {
            'value': 'https://id.fedoraproject.org/openid/',
            'validator': six.text_type},
        'openid.sreg_required': {
            'value': 'email',
            'validator': six.text_type},
        'openid.success_callback': {
            'value': 'bodhi.server.security:remember_me',
            'validator': six.text_type},
        'openid.url': {
            'value': 'https://id.fedoraproject.org/',
            'validator': six.text_type},
        'openid_template': {
            'value': '{username}.id.fedoraproject.org',
            'validator': six.text_type},
        'pagure_url': {
            'value': 'https://src.fedoraproject.org/pagure/',
            'validator': _validate_tls_url},
        'pdc_url': {
            'value': 'https://pdc.fedoraproject.org/',
            'validator': _validate_tls_url},
        'pkgdb_url': {
            'value': 'https://admin.fedoraproject.org/pkgdb',
            'validator': six.text_type},
        'prefer_ssl': {
            'value': None,
            'validator': _validate_none_or(bool)},
        'privacy_link': {
            'value': '',
            'validator': six.text_type},
        'pungi.basepath': {
            'value': '/etc/bodhi',
            'validator': six.text_type},
        'pungi.cmd': {
            'value': '/usr/bin/pungi-koji',
            'validator': six.text_type},
        'pungi.conf.module': {
            'value': 'pungi.module.conf',
            'validator': six.text_type},
        'pungi.conf.rpm': {
            'value': 'pungi.rpm.conf',
            'validator': six.text_type},
        'pungi.extracmdline': {
            'value': [],
            'validator': _generate_list_validator()},
        'pungi.labeltype': {
            'value': 'Update',
            'validator': six.text_type},
        'query_wiki_test_cases': {
            'value': False,
            'validator': _validate_bool},
        'release_team_address': {
            'value': 'bodhiadmin-members@fedoraproject.org',
            'validator': six.text_type},
        'resultsdb_api_url': {
            'value': 'https://taskotron.fedoraproject.org/resultsdb_api/',
            'validator': six.text_type},
        'session.secret': {
            'value': 'CHANGEME',
            'validator': _validate_secret},
        'site_requirements': {
            'value': 'dist.rpmdeplint dist.upgradepath',
            'validator': six.text_type},
        'skopeo.cmd': {
            'value': '/usr/bin/skopeo',
            'validator': six.text_type,
        },
        'skopeo.extra_copy_flags': {
            'value': '',
            'validator': six.text_type,
        },
        'smtp_server': {
            'value': None,
            'validator': _validate_none_or(six.text_type)},
        'sqlalchemy.url': {
            'value': 'sqlite:////var/cache/bodhi.db',
            'validator': six.text_type},
        'stable_bug_msg': {
            'value': ('%s has been pushed to the %s repository. If problems still persist, please '
                      'make note of it in this bug report.'),
            'validator': six.text_type},
        'stable_from_batched_msg': {
            'value': ('This update has been dequeued from batched and is now entering stable.'),
            'validator': six.text_type},
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
            'validator': six.text_type},
        'testing_approval_msg_based_on_karma': {
            'value': ('This update has reached the stable karma threshold and can be pushed to '
                      'stable now if the maintainer wishes.'),
            'validator': six.text_type
        },
        'testing_approval_msg': {
            'value': ('This update has reached %d days in testing and can be pushed to stable now '
                      'if the maintainer wishes'),
            'validator': six.text_type},
        'testing_bug_epel_msg': {
            'value': (
                '\nSee https://fedoraproject.org/wiki/QA:Updates_Testing for\ninstructions on how '
                'to install test updates.\nYou can provide feedback for this update here: %s'),
            'validator': six.text_type},
        'testing_bug_msg': {
            'value': (
                '\nSee https://fedoraproject.org/wiki/QA:Updates_Testing for\ninstructions on how '
                'to install test updates.\nYou can provide feedback for this update here: %s'),
            'validator': six.text_type},
        'top_testers_timeframe': {
            'value': 7,
            'validator': int},
        'test_gating.required': {
            'value': False,
            'validator': _validate_bool},
        'test_gating.url': {
            'value': '',
            'validator': six.text_type},
        'updateinfo_rights': {
            'value': 'Copyright (C) {} Red Hat, Inc. and others.'.format(datetime.now().year),
            'validator': six.text_type},
        'wait_for_repo_sig': {
            'value': False,
            'validator': _validate_bool},
        'wiki_url': {
            'value': 'https://fedoraproject.org/w/api.php',
            'validator': six.text_type},
    }

    def __getitem__(self, *args, **kw):
        """Ensure the config is loaded, and then call the superclass __getitem__."""
        if not self.loaded:
            self.load_config()
        return super(BodhiConfig, self).__getitem__(*args, **kw)

    def get(self, *args, **kw):
        """Ensure the config is loaded, and then call the superclass get."""
        if not self.loaded:
            self.load_config()
        return super(BodhiConfig, self).get(*args, **kw)

    def pop(self, *args, **kw):
        """Ensure the config is loaded, and then call the superclass pop."""
        if not self.loaded:
            self.load_config()
        return super(BodhiConfig, self).pop(*args, **kw)

    def copy(self, *args, **kw):
        """Ensure the config is loaded, and then call the superclass copy."""
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
                errors.append('\t{}: {}'.format(k, six.text_type(e)))

        if errors:
            raise ValueError(
                'Invalid config values were set: \n{}'.format('\n'.join(errors)))


config = BodhiConfig()
