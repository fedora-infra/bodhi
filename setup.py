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

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()
CHANGES = open(os.path.join(here, 'CHANGES.txt')).read()

requires = [
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

    # For the bodhi-client
    'click',

    'WebOb>=1.4.1',
    ]

if sys.version_info[:3] < (2,7,0):
    requires.append('importlib')

if sys.version_info[:3] < (2,5,0):
    requires.append('pysqlite')

setup(name='bodhi',
      version='2.1.9',
      description='bodhi',
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
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires = requires,
      tests_require = [
          'nose',
          'nose-cov',
          'webtest',
          'mock'
      ],
      test_suite="nose.collector",
      message_extractors = { '.': [
          #('**.py', 'lingua_python', None),
          #('**.mak', 'lingua_xml', None),
      ]},
      entry_points = """\
      [paste.app_factory]
      main = bodhi:main
      [console_scripts]
      initialize_bodhi_db = bodhi.scripts.initializedb:main
      bodhi = bodhi.cli:cli
      bodhi-push = bodhi.push:push
      bodhi-expire-overrides = bodhi.scripts.expire_overrides:main
      bodhi-untag-branched = bodhi.scripts.untag_branched:main
      bodhi-approve-testing = bodhi.scripts.approve_testing:main
      bodhi-manage-releases = bodhi.scripts.manage_releases:main
      [moksha.consumer]
      masher = bodhi.consumers.masher:Masher
      updates = bodhi.consumers.updates:UpdatesHandler
      """,
      paster_plugins=['pyramid'],
      )

