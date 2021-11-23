from multiprocessing import Process
import os

from setuptools import setup, find_packages
import setuptools.command.egg_info

from bodhi import __version__ as VERSION


def get_requirements(requirements_file='requirements.txt'):
    """
    Get the contents of a file listing the requirements.

    Args:
        requirements_file (str): path to a requirements file

    Returns:
        list: the list of requirements, or an empty list if
              `requirements_file` could not be opened or read
    """
    lines = open(requirements_file).readlines()
    dependencies = []
    for line in lines:
        maybe_dep = line.strip()
        if maybe_dep.startswith('#'):
            # Skip pure comment lines
            continue
        if maybe_dep.startswith('git+'):
            # VCS reference for dev purposes, expect a trailing comment
            # with the normal requirement
            __, __, maybe_dep = maybe_dep.rpartition('#')
        else:
            # Ignore any trailing comment
            maybe_dep, __, __ = maybe_dep.partition('#')
        # Remove any whitespace and assume non-empty results are dependencies
        maybe_dep = maybe_dep.strip()
        if maybe_dep:
            dependencies.append(maybe_dep)
    return dependencies


here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()


# Possible options are at https://pypi.python.org/pypi?%3Aaction=list_classifiers
CLASSIFIERS = [
    'Development Status :: 5 - Production/Stable',
    'Intended Audience :: Developers',
    'Intended Audience :: System Administrators',
    'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
    'Operating System :: POSIX :: Linux',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.7',
    'Topic :: System :: Software Distribution']
LICENSE = 'GPLv2+'
MAINTAINER = 'Fedora Infrastructure Team'
MAINTAINER_EMAIL = 'infrastructure@lists.fedoraproject.org'
PLATFORMS = ['Fedora', 'GNU/Linux']
URL = 'https://github.com/fedora-infra/bodhi'

server_pkgs = find_packages(
    include=['bodhi.server', 'bodhi.server.*'],
)

base_setup = {
    'version': VERSION,
    'long_description': README,
    'classifiers': CLASSIFIERS,
    'license': LICENSE,
    'maintainer': MAINTAINER,
    'maintainer_email': MAINTAINER_EMAIL,
    'platforms': PLATFORMS,
    'url': URL,
    'zip_safe': False,
}


server_setup = {
    'manifest': 'SERVER_MANIFEST.in',
    'name': 'bodhi-server',
    'description': 'bodhi server',
    'classifiers': (
        CLASSIFIERS + [
            'Framework :: Pyramid',
            'Programming Language :: JavaScript',
            "Topic :: Internet :: WWW/HTTP",
            "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        ]
    ),
    'keywords': ['web', 'fedora', 'pyramid'],
    'packages': server_pkgs,
    'include_package_data': True,
    'install_requires': get_requirements(),
    'message_extractors': {'.': []},
    'entry_points': '''
        [paste.app_factory]
        main = bodhi.server:main
        [console_scripts]
        initialize_bodhi_db = bodhi.server.scripts.initializedb:main
        bodhi-push = bodhi.server.push:push
        bodhi-untag-branched = bodhi.server.scripts.untag_branched:main
        bodhi-skopeo-lite = bodhi.server.scripts.skopeo_lite:main
        bodhi-sar = bodhi.server.scripts.sar:get_user_data
        bodhi-shell = bodhi.server.scripts.bshell:get_bodhi_shell
        bodhi-clean-old-composes = bodhi.server.scripts.compat:clean_old_composes
        bodhi-expire-overrides = bodhi.server.scripts.compat:expire_overrides
        bodhi-approve-testing = bodhi.server.scripts.compat:approve_testing
        bodhi-check-policies = bodhi.server.scripts.compat:check_policies
    ''',
    'paster_plugins': ['pyramid'],
}

for s in [server_setup]:
    setuptools.command.egg_info.manifest_maker.template = s.pop('manifest')
    p = Process(target=setup, kwargs={**base_setup, **s})
    p.start()
    p.join()
