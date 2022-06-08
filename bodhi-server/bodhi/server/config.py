# Copyright © 2013-2019 Red Hat, Inc. and others.
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
import logging
import os
import typing

from pyramid import settings
from pyramid.paster import get_appsettings


log = logging.getLogger('bodhi')


def get_configfile() -> typing.Optional[str]:
    """
    Return a path to a config file, if found.

    Return the path to a config file, with a hierarchy of preferential paths. It searches first
    for development.ini if found. If not found, it will return /etc/bodhi/production.ini if it
    exists. Otherwise, it returns None.

    Returns:
        The path of a config file, or None if no config file is found.
    """
    configfile = None
    setupdir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..')
    possible_configs = [os.path.join(setupdir, 'development.ini'), '/etc/bodhi/production.ini']
    if "BODHI_CONFIG" in os.environ:
        possible_configs.insert(0, os.environ["BODHI_CONFIG"])
    for cfg in possible_configs:
        if os.path.exists(cfg):
            configfile = cfg
            break
    else:
        log.error("Unable to find configuration to load!")
    return configfile


def _generate_dict_validator(value: str) -> dict:
    """Return a dict version of value.

    This function accept a string with comma separated tuples in the form `key:value`
    and ensure it can be correctly imported as a dict. It will return a dict.
    If it cannot do that, it will raise ValueError.

    Args:
        value: The value to be validated as a dict.
    Returns:
        The dict interpretation of value.
    Raises:
        ValueError: If value cannot be interpreted as a dict.
    """
    if isinstance(value, str):
        values_list = [idx.strip() for idx in value.split(',') if idx.strip()]
        dictvalue = dict()
        for v in values_list:
            try:
                k, v = v.split(':')
                dictvalue[k.strip()] = v.strip()
            except Exception:
                raise ValueError(f'"{value}" cannot be interpreted as a dict.')
        value = dictvalue

    if not isinstance(value, dict):
        raise ValueError(f'"{value}" cannot be interpreted as a dict.')

    return value


def _generate_list_validator(
        splitter: str = ' ', validator: typing.Callable[[typing.Any], typing.Any] = str) \
        -> typing.Callable[[typing.Union[str, typing.List]], typing.Any]:
    """Return a function that takes a value and interprets it to be a list with the given splitter.

    This function generates a function that can take a string and interpret it as a list by
    splitting with the given splitter string. Each element of the resulting list is then validated
    with the given validator.

    Args:
        splitter: A string to use to split the input into a list.
        validator:  A function to apply to each element of the list to validate it.
    Returns:
        A validator function that accepts an argument to be validated.
    """
    def _validate_list(value: typing.Union[str, typing.List]) -> typing.List:
        """Validate that the value is a list or can be split into a list, and validate its elements.

        This function will validate that the given value is a list, or it will use the splitter to
        turn it into a list. Once it is a list, it will use the validator on each element of the
        list.

        Args:
            value: The list to be validated.
        Returns:
            The interpreted list.
        Raises:
            ValueError: If validator fails on any of the list's elements.
        """
        if isinstance(value, str):
            value = [idx.strip() for idx in value.split(splitter) if idx.strip()]

        if not isinstance(value, list):
            raise ValueError('"{}" cannot be interpreted as a list.'.format(value))

        # Run the validator on each element of the list.
        value = [validator(v) for v in value]

        return value

    return _validate_list


def _validate_bool(value: typing.Union[str, bool]) -> bool:
    """Return a bool version of value.

    This function will ensure that value is a bool, or that it is a string that can be interpreted
    as a bool. It will return a bool. If it cannot do that, it will raise ValueError.

    Args:
        value: The value to be validated as a bool.
    Returns:
        The boolean interpretation of value.
    Raises:
        ValueError: If value cannot be interpreted as a boolean.
    """
    if isinstance(value, str):
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


def _validate_none_or(validator: typing.Callable[[typing.Any], typing.Any]) \
        -> typing.Callable[[typing.Any], typing.Any]:
    """Return a function that will ensure a value is None or passes validator.

    This function returns a function that will take a single argument, value, and will ensure
    that value is None or that it passes the given validator.

    Args:
        validator: A function to apply when value is not None.
    Returns:
        A validator function that accepts an argument to be validated.
    """
    def _validate(value: typing.Any) -> typing.Any:
        if value is None:
            return value

        return validator(value)

    return _validate


def validate_path(value: str) -> str:
    """Ensure that value is an existing path on the local filesystem and return it.

    Use os.path.exists to ensure that value is an existing path. Return the value if it is, else
    raise ValueError.

    Args:
        value: The path to be validated.
    Returns:
        The path.
    Raises:
        ValueError: If os.path.exists returns False.
    """
    if value is None or not os.path.exists(value):
        raise ValueError(f'{value!r} does not exist.')

    return str(value)


def _validate_rstripped_str(value: str) -> str:
    """
    Ensure that value is a str that is rstripped of the / character.

    Args:
        value: The value to be validated and rstripped.
    Returns:
        The rstripped value.
    """
    value = str(value)
    return value.rstrip('/')


def _validate_secret(value: str) -> str:
    """Ensure that the value is not CHANGEME and convert it to a string.

    This function is used to ensure that secret values in the config have been set by the user to
    something other than the default of CHANGEME.

    Args:
        value: The value to be validated.
    Returns:
        The value.
    Raises:
        ValueError: If value is "CHANGEME".
    """
    if value == 'CHANGEME':
        raise ValueError('This setting must be changed from its default value.')

    return str(value)


def _validate_tls_url(value: str) -> str:
    """Ensure that the value is a string that starts with https://.

    Args:
        value: The value to be validated.
    Returns:
        The value.
    Raises:
        ValueError: If value is not a string starting with https://.
    """
    if not isinstance(value, str) or not value.startswith('https://'):
        raise ValueError('This setting must be a URL starting with https://.')

    return str(value)


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
            'validator': str},
        'acl_dummy_committer': {
            'value': None,
            'validator': _validate_none_or(str)},
        'admin_groups': {
            # Defined in and tied to the Fedora Account System (limited to 16 characters)
            'value': ['proventesters', 'security_respons', 'bodhiadmin', 'sysadmin-main'],
            'validator': _generate_list_validator()},
        'admin_packager_groups': {
            # Defined in and tied to the Fedora Account System (limited to 16 characters)
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
        'automatic_updates_blacklist': {
            # List of users to not create automatic updates from
            'value': ['releng'],
            'validator': _generate_list_validator()},
        'base_address': {
            'value': 'https://admin.fedoraproject.org/updates/',
            'validator': str},
        'bodhi_email': {
            'value': 'updates@fedoraproject.org',
            'validator': str},
        'bodhi_password': {
            'value': None,
            'validator': _validate_none_or(str)},
        'buglink': {
            'value': 'https://bugzilla.redhat.com/show_bug.cgi?id=%s',
            'validator': str},
        'bugtracker': {
            'value': None,
            'validator': _validate_none_or(str)},
        'bugzilla_api_key': {
            'value': None,
            'validator': _validate_none_or(str)},
        'buildroot_limit': {
            'value': 31,
            'validator': int},
        'buildsystem': {
            'value': 'dev',
            'validator': str},
        'bz_exclude_rels': {
            'value': [],
            'validator': _generate_list_validator(',')},
        'bz_products': {
            'value': ['Fedora', 'Fedora EPEL', 'Fedora Modules'],
            'validator': _generate_list_validator(',')},
        'bz_regex': {
            'value': (r'(?:fix(?:es)?|close(?:s)?|resolve(?:s)?)(?:\:)?\s'
                      r'(?:fedora|epel|rh(?:bz)?)#(\d{5,})'),
            'validator': str},
        'bz_server': {
            'value': 'https://bugzilla.redhat.com/xmlrpc.cgi',
            'validator': str},
        'bz_server_rest': {
            'value': 'https://bugzilla.redhat.com/rest/',
            'validator': str},
        'cache_dir': {
            'value': None,
            'validator': _validate_none_or(validate_path)},
        'celery_config': {
            'value': '/etc/bodhi/celeryconfig.py',
            'validator': str},
        'check_signed_builds_delay': {
            'value': 2,
            'validator': int},
        'clean_old_composes': {
            'value': True,
            'validator': _validate_bool},
        'container.destination_registry': {
            'value': 'registry.fedoraproject.org',
            'validator': str},
        'container.source_registry': {
            'value': 'candidate-registry.fedoraproject.org',
            'validator': str},
        'cors_connect_src': {
            'value': 'https://*.fedoraproject.org/ wss://hub.fedoraproject.org:9939/',
            'validator': str},
        'cors_origins_ro': {
            'value': '*',
            'validator': str},
        'cors_origins_rw': {
            'value': 'https://bodhi.fedoraproject.org',
            'validator': str},
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
            'validator': _validate_none_or(str)},
        'default_email_domain': {
            'value': 'fedoraproject.org',
            'validator': str},
        'disable_automatic_push_to_stable': {
            'value': (
                'Bodhi is disabling automatic push to stable due to negative karma. The '
                'maintainer may push manually if they determine that the issue is not severe.'),
            'validator': str},
        'dogpile.cache.arguments.filename': {
            'value': '/var/cache/bodhi-dogpile-cache.dbm',
            'validator': str},
        'dogpile.cache.backend': {
            'value': 'dogpile.cache.dbm',
            'validator': str},
        'dogpile.cache.expiration_time': {
            'value': 100,
            'validator': int},
        'exclude_mail': {
            'value': ['autoqa', 'taskotron'],
            'validator': _generate_list_validator()},
        'file_url': {
            'value': 'https://download.fedoraproject.org/pub/fedora/linux/updates',
            'validator': str},
        'fmn_url': {
            'value': 'https://apps.fedoraproject.org/notifications/',
            'validator': str},
        'important_groups': {
            # Defined in and tied to the Fedora Account System (limited to 16 characters)
            'value': ['proventesters', 'provenpackager', 'releng', 'security_respons', 'packager',
                      'bodhiadmin'],
            'validator': _generate_list_validator()},
        'initial_bug_msg': {
            'value': '%s has been submitted as an update to %s. %s',
            'validator': str},
        'greenwave_api_url': {
            'value': 'https://greenwave-web-greenwave.app.os.fedoraproject.org/api/v1.0',
            'validator': _validate_rstripped_str},
        'greenwave_batch_size': {
            'value': 8,
            'validator': int},
        'waiverdb_api_url': {
            'value': 'https://waiverdb-web-waiverdb.app.os.fedoraproject.org/api/v1.0',
            'validator': _validate_rstripped_str},
        'waiverdb.access_token': {
            'value': None,
            'validator': _validate_none_or(str)},
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
            'validator': str},
        'libravatar_dns': {
            'value': False,
            'validator': _validate_bool},
        'libravatar_enabled': {
            'value': True,
            'validator': _validate_bool},
        'libravatar_prefer_tls': {
            'value': True,
            'validator': bool},
        'mail.templates_basepath': {
            'value': 'bodhi.server:email/templates/',
            'validator': str},
        'mako.directories': {
            'value': 'bodhi.server:templates',
            'validator': str},
        'mandatory_packager_groups': {
            'value': ['packager'],
            'validator': _generate_list_validator()},
        'compose_dir': {
            'value': None,
            'validator': _validate_none_or(str)},
        'compose_stage_dir': {
            'value': None,
            'validator': _validate_none_or(str)},
        'max_concurrent_composes': {
            'value': 2,
            'validator': int},
        'message_id_email_domain': {
            'value': 'admin.fedoraproject.org',
            'validator': str},
        'not_yet_tested_epel_msg': {
            'value': (
                'This update has not yet met the minimum testing requirements defined in the '
                '<a href="https://fedoraproject.org/wiki/EPEL_Updates_Policy">EPEL Update Policy'
                '</a>'),
            'validator': str},
        'not_yet_tested_msg': {
            'value': (
                'This update has not yet met the minimum testing requirements defined in the '
                '<a href="https://fedoraproject.org/wiki/Package_update_acceptance_criteria">'
                'Package Update Acceptance Criteria</a>'),
            'validator': str},
        'openid.provider': {
            'value': 'https://id.fedoraproject.org/openid/',
            'validator': str},
        'openid.sreg_required': {
            'value': 'email nickname',
            'validator': str},
        'openid.success_callback': {
            'value': 'bodhi.server.auth.utils:remember_me',
            'validator': str},
        'openid.url': {
            'value': 'https://id.fedoraproject.org/',
            'validator': str},
        'openid_template': {
            'value': '{username}.id.fedoraproject.org',
            'validator': str},
        'oidc.fedora.client_id': {
            'value': '',
            'validator': str},
        'oidc.fedora.client_secret': {
            'value': '',
            'validator': str},
        'oidc.fedora.server_metadata_url': {
            'value': 'https://id.fedoraproject.org/openidc/.well-known/openid-configuration',
            'validator': str},
        'pagure_namespaces': {
            'value': ('rpm:rpms, module:modules, container:container, flatpak:flatpaks'),
            'validator': _generate_dict_validator},
        'pagure_flatpak_main_branch': {
            'value': 'stable',
            'validator': str},
        'pagure_module_main_branch': {
            'value': 'master',
            'validator': str},
        'pagure_url': {
            'value': 'https://src.fedoraproject.org/pagure/',
            'validator': _validate_tls_url},
        'pdc_url': {
            'value': 'https://pdc.fedoraproject.org/',
            'validator': _validate_tls_url},
        'privacy_link': {
            'value': '',
            'validator': str},
        'pungi.basepath': {
            'value': '/etc/bodhi',
            'validator': str},
        'pungi.cmd': {
            'value': '/usr/bin/pungi-koji',
            'validator': str},
        'pungi.conf.module': {
            'value': 'pungi.module.conf',
            'validator': str},
        'pungi.conf.rpm': {
            'value': 'pungi.rpm.conf',
            'validator': str},
        'pungi.extracmdline': {
            'value': [],
            'validator': _generate_list_validator()},
        'pungi.labeltype': {
            'value': 'Update',
            'validator': str},
        'query_wiki_test_cases': {
            'value': False,
            'validator': _validate_bool},
        'release_team_address': {
            'value': 'bodhiadmin-members@fedoraproject.org',
            'validator': str},
        'resultsdb_api_url': {
            'value': 'https://taskotron.fedoraproject.org/resultsdb_api/',
            'validator': str},
        'session.secret': {
            'value': 'CHANGEME',
            'validator': _validate_secret},
        'site_requirements': {
            'value': 'dist.rpmdeplint',
            'validator': str},
        'skopeo.cmd': {
            'value': '/usr/bin/skopeo',
            'validator': str,
        },
        'skopeo.extra_copy_flags': {
            'value': '',
            'validator': str,
        },
        'smtp_server': {
            'value': None,
            'validator': _validate_none_or(str)},
        'sqlalchemy.url': {
            'value': 'postgresql://localhost/bodhi',
            'validator': str},
        'stable_bug_msg': {
            'value': ('{update_alias} has been pushed to the {repo} repository.\n'
                      'If problem still persists, please make note of it in this bug report.'),
            'validator': str},
        'stats_blacklist': {
            'value': ['bodhi', 'anonymous', 'autoqa', 'taskotron'],
            'validator': _generate_list_validator()},
        'system_users': {
            'value': ['bodhi', 'autoqa', 'taskotron'],
            'validator': _generate_list_validator()},
        'test_case_base_url': {
            'value': 'https://fedoraproject.org/wiki/',
            'validator': str},
        'testing_approval_msg': {
            'value': ('This update can be pushed to stable now if the maintainer wishes'),
            'validator': str},
        'testing_bug_epel_msg': {
            'value': (
                '{update_alias} has been pushed to the {repo} repository.\n'
                '{install_instructions}\n'
                'You can provide feedback for this update here: {update_url}\n\n'
                'See also https://fedoraproject.org/wiki/QA:Updates_Testing for more '
                'information on how to test updates.'),
            'validator': str},
        'testing_bug_msg': {
            'value': (
                '{update_alias} has been pushed to the {repo} repository.\n'
                '{install_instructions}\n'
                'You can provide feedback for this update here: {update_url}\n\n'
                'See also https://fedoraproject.org/wiki/QA:Updates_Testing for more '
                'information on how to test updates.'),
            'validator': str},
        'top_testers_timeframe': {
            'value': 7,
            'validator': int},
        'test_gating.required': {
            'value': False,
            'validator': _validate_bool},
        'test_gating.url': {
            'value': '',
            'validator': str},
        'updateinfo_rights': {
            'value': 'Copyright (C) {} Red Hat, Inc. and others.'.format(datetime.now().year),
            'validator': str},
        'wait_for_repo_sig': {
            'value': False,
            'validator': _validate_bool},
        'warm_cache_on_start': {
            'value': True,
            'validator': _validate_bool},
        'wiki_url': {
            'value': 'https://fedoraproject.org/w/api.php',
            'validator': str},
    }

    def __getitem__(self, key: typing.Hashable) -> typing.Any:
        """Ensure the config is loaded, and then call the superclass __getitem__."""
        if not self.loaded:
            self.load_config()
        return super(BodhiConfig, self).__getitem__(key)

    def get(self, *args, **kw) -> typing.Any:
        """Ensure the config is loaded, and then call the superclass get."""
        if not self.loaded:
            self.load_config()
        return super(BodhiConfig, self).get(*args, **kw)

    def pop(self, *args, **kw) -> typing.Any:
        """Ensure the config is loaded, and then call the superclass pop."""
        if not self.loaded:
            self.load_config()
        return super(BodhiConfig, self).pop(*args, **kw)

    def copy(self) -> typing.Any:
        """Ensure the config is loaded, and then call the superclass copy."""
        if not self.loaded:
            self.load_config()
        return super(BodhiConfig, self).copy()

    def load_config(self, settings: typing.Mapping = None):
        """
        Load the configuration either from the config file, or from the given settings.

        args:
            settings: If given, the settings are pulled from this dictionary. Otherwise, the
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

    def clear(self):
        """Restore the configuration to its original blank state."""
        super().clear()
        self.loaded = False

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
                errors.append('\t{}: {}'.format(k, str(e)))

        if errors:
            raise ValueError(
                'Invalid config values were set: \n{}'.format('\n'.join(errors)))


config = BodhiConfig()
