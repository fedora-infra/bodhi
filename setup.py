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
CHANGES = open(os.path.join(here, 'CHANGES.txt')).read()
VERSION = '2.1.9'

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
      long_description=README + '\n\n' +  CHANGES,
      classifiers=[
        "Programming Language :: Python",
        ],
      author='',
      author_email='',
      url='',
      keywords='fedora',
      packages=['bodhi'],
      include_package_data=True,
      zip_safe=False,
      install_requires = [],
      tests_require = [
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
      long_description=README + '\n\n' +  CHANGES,
      classifiers=[
        "Programming Language :: Python",
        ],
      author='',
      author_email='',
      url='',
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


setup(name='bodhi-server',
      version=VERSION,
      description='bodhi server',
      long_description=README + '\n\n' +  CHANGES,
      classifiers=[
        "Programming Language :: Python",
        "Framework :: Pyramid",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        ],
      author='',
      author_email='',
      url='',
      keywords='web fedora pyramid',
      packages=find_packages(
          exclude=['bodhi', 'bodhi.client', 'bodhi.client.*', 'bodhi.tests', 'bodhi.tests.*']),
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
      """,
      paster_plugins=['pyramid'],
      )
