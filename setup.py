# The following two imports are required to shut up an
# atexit error when running tests with python 2.7
from setuptools import setup, find_packages  # noqa
import logging  # noqa
import multiprocessing  # noqa
import os  # noqa
import setuptools.command.egg_info  # noqa
import sys  # noqa


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
VERSION = '3.11.0'
# Possible options are at https://pypi.python.org/pypi?%3Aaction=list_classifiers
CLASSIFIERS = [
    'Development Status :: 5 - Production/Stable',
    'Intended Audience :: Developers',
    'Intended Audience :: System Administrators',
    'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
    'Operating System :: POSIX :: Linux',
    'Programming Language :: Python :: 2.7',
    'Topic :: System :: Software Distribution']
LICENSE = 'GPLv2+'
MAINTAINER = 'Fedora Infrastructure Team'
MAINTAINER_EMAIL = 'infrastructure@lists.fedoraproject.org'
PLATFORMS = ['Fedora', 'GNU/Linux']
URL = 'https://github.com/fedora-infra/bodhi'


setuptools.command.egg_info.manifest_maker.template = 'BODHI_MANIFEST.in'


setup(
    name='bodhi',
    version=VERSION,
    description='bodhi common package',
    long_description=README,
    classifiers=CLASSIFIERS,
    license=LICENSE,
    maintainer=MAINTAINER,
    maintainer_email=MAINTAINER_EMAIL,
    platforms=PLATFORMS,
    url=URL,
    keywords='fedora',
    packages=['bodhi'],
    include_package_data=True,
    zip_safe=False,
    install_requires=[],
    tests_require=[
        'flake8',
        'pytest',
        'pytest-cov',
        'pyyaml',
        'webtest',
        'mock',
    ],
)


setuptools.command.egg_info.manifest_maker.template = 'CLIENT_MANIFEST.in'


setup(
    name='bodhi-client',
    version=VERSION,
    description='bodhi client',
    long_description=README,
    classifiers=CLASSIFIERS,
    license=LICENSE,
    maintainer=MAINTAINER,
    maintainer_email=MAINTAINER_EMAIL,
    platforms=PLATFORMS,
    url=URL,
    keywords='fedora',
    packages=['bodhi.client'],
    include_package_data=False,
    zip_safe=False,
    install_requires=['click', 'iniparse', 'python-fedora >= 0.9.0', 'six'],
    entry_points="""\
    [console_scripts]
    bodhi = bodhi.client:cli
    """)


setuptools.command.egg_info.manifest_maker.template = 'SERVER_MANIFEST.in'
# Due to https://github.com/pypa/setuptools/issues/808, we need to include the bodhi superpackage
# and then remove it if we want find_packages() to find the bodhi.server package and its
# subpackages without including the bodhi top level package.
server_packages = find_packages(
    exclude=['bodhi.client', 'bodhi.client.*', 'bodhi.tests', 'bodhi.tests.*'])
server_packages.remove('bodhi')


setup(
    name='bodhi-server',
    version=VERSION,
    description='bodhi server',
    long_description=README,
    classifiers=CLASSIFIERS + [
        'Framework :: Pyramid',
        'Programming Language :: JavaScript',
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application"],
    license=LICENSE,
    maintainer=MAINTAINER,
    maintainer_email=MAINTAINER_EMAIL,
    platforms=PLATFORMS,
    url=URL,
    keywords='web fedora pyramid',
    packages=server_packages,
    include_package_data=True,
    zip_safe=False,
    install_requires=get_requirements(),
    message_extractors={'.': []},
    entry_points="""\
    [paste.app_factory]
    main = bodhi.server:main
    [console_scripts]
    initialize_bodhi_db = bodhi.server.scripts.initializedb:main
    bodhi-clean-old-mashes = bodhi.server.scripts.clean_old_mashes:clean_up
    bodhi-dequeue-stable = bodhi.server.scripts.dequeue_stable:dequeue_stable
    bodhi-push = bodhi.server.push:push
    bodhi-expire-overrides = bodhi.server.scripts.expire_overrides:main
    bodhi-monitor-composes = bodhi.server.scripts.monitor_composes:monitor
    bodhi-untag-branched = bodhi.server.scripts.untag_branched:main
    bodhi-approve-testing = bodhi.server.scripts.approve_testing:main
    bodhi-manage-releases = bodhi.server.scripts.manage_releases:main
    bodhi-check-policies = bodhi.server.scripts.check_policies:check
    bodhi-skopeo-lite = bodhi.server.scripts.skopeo_lite:main
    bodhi-sar = bodhi.server.scripts.sar:get_user_data
    [moksha.consumer]
    masher = bodhi.server.consumers.masher:Masher
    updates = bodhi.server.consumers.updates:UpdatesHandler
    signed = bodhi.server.consumers.signed:SignedHandler
    """,
    paster_plugins=['pyramid'])
