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
    'pyramid_beaker',
    'pyramid_debugtoolbar',
    'pyramid_tm',
    'waitress',
    'colander',
    'cornice',

    'python-openid',
    'pyramid_fas_openid',

    'sqlalchemy',
    'zope.sqlalchemy',

    'webhelpers',
    'progressbar',

    # Useful tools
    'kitchen',
    'python-fedora',

    # i18n
    'Babel',
    'lingua',

    # External resources
    'python-bugzilla',
    'simplemediawiki',
    'fedmsg',

    'Sphinx',
    ]

if sys.version_info[:3] < (2,5,0):
    requires.append('pysqlite')

setup(name='bodhi',
      version='2.0',
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
      tests_require = ['nose', 'nose-cov', 'webtest'],
      test_suite="nose.collector",
      message_extractors = { '.': [
          ('**.py', 'lingua_python', None),
          ('**.mak', 'lingua_xml', None),
      ]},
      entry_points = """\
      [paste.app_factory]
      main = bodhi:main
      [console_scripts]
      initialize_bodhi_db = bodhi.scripts.initializedb:main
      """,
      paster_plugins=['pyramid'],
      )

