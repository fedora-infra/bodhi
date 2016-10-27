import __main__
__requires__ = __main__.__requires__ = 'WebOb>=1.4.1'
import pkg_resources

# The following two imports are required to shut up an
# atexit error when running tests with python 2.7
import logging
import multiprocessing

import os
import sys

from setuptools import setup, find_packages
import setuptools.command.egg_info


here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()
VERSION = '2.3.1'
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

server_requires = [
    'pyramid',
    'pyramid_mako',
    'pyramid_debugtoolbar',
    'pyramid_tm',
    'waitress',
    'colander',
    'cornice',

    'python-openid',
    'pyramid_fas_openid',
    'packagedb-cli',

    'sqlalchemy',
    'zope.sqlalchemy',

    'webhelpers',
    'progressbar',

    'bunch',

    # for captchas
    'cryptography',
    'Pillow',

    # Useful tools
    'kitchen',
    'python-fedora',
    'pylibravatar',
    'pyDNS',
    'dogpile.cache',
    'arrow',
    'markdown',

    # i18n, that we're not actually doing yet.
    #'Babel',
    #'lingua',

    # External resources
    'python-bugzilla',
    'simplemediawiki',

    # "python setup.py test" needs one of fedmsg's setup.py extra_requires
    'fedmsg[consumers]',
    # The masher needs fedmsg-atomic-composer
    'fedmsg-atomic-composer >= 2016.3',

    'Sphinx',

    'WebOb>=1.4.1',
    ]

if sys.version_info[:3] < (2,7,0):
    server_requires.append('importlib')

if sys.version_info[:3] < (2,5,0):
    server_requires.append('pysqlite')


setuptools.command.egg_info.manifest_maker.template = 'BODHI_MANIFEST.in'


setup(name='bodhi',
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
      install_requires = [],
      tests_require = [
          'flake8',
          'nose',
          'nose-cov',
          'webtest',
          'mock'
      ],
      test_suite="nose.collector",
      )


setuptools.command.egg_info.manifest_maker.template = 'CLIENT_MANIFEST.in'


setup(name='bodhi-client',
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
      install_requires = ['click'],
      entry_points = """\
      [console_scripts]
      bodhi = bodhi.client:cli
      """,
      )


setuptools.command.egg_info.manifest_maker.template = 'SERVER_MANIFEST.in'
# Due to https://github.com/pypa/setuptools/issues/808, we need to include the bodhi superpackage
# and then remove it if we want find_packages() to find the bodhi.server package and its
# subpackages without including the bodhi top level package.
server_packages = find_packages(
    exclude=['bodhi.client', 'bodhi.client.*', 'bodhi.tests', 'bodhi.tests.*'])
server_packages.remove('bodhi')


setup(name='bodhi-server',
      version=VERSION,
      description='bodhi server',
      long_description=README,
      classifiers=CLASSIFIERS + [
        "Framework :: Pyramid",
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
#      script_args=sys.argv.extend(['--template', 'TEST']),
      zip_safe=False,
      install_requires = server_requires,
      message_extractors = { '.': [
          #('**.py', 'lingua_python', None),
          #('**.mak', 'lingua_xml', None),
      ]},
      entry_points = """\
      [paste.app_factory]
      main = bodhi.server:main
      [console_scripts]
      initialize_bodhi_db = bodhi.server.scripts.initializedb:main
      bodhi-push = bodhi.server.push:push
      bodhi-expire-overrides = bodhi.server.scripts.expire_overrides:main
      bodhi-untag-branched = bodhi.server.scripts.untag_branched:main
      bodhi-approve-testing = bodhi.server.scripts.approve_testing:main
      bodhi-manage-releases = bodhi.server.scripts.manage_releases:main
      [moksha.consumer]
      masher = bodhi.server.consumers.masher:Masher
      updates = bodhi.server.consumers.updates:UpdatesHandler
      signed = bodhi.server.consumers.signed:SignedHandler
      """,
      paster_plugins=['pyramid'],
      )
