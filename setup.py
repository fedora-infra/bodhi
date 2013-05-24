# The following two imports are required to shut up an
# atexit error when running tests with python 2.7
import logging
import multiprocessing

import os
import sys

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.txt')).read()
CHANGES = open(os.path.join(here, 'CHANGES.txt')).read()

requires = [
    'pyramid',
    'pyramid_beaker',
    'pyramid_openid',
    'pyramid_debugtoolbar',
    'pyramid_tm',
    'waitress',

    'sqlalchemy',
    #'zope.sqlalchemy',

    'webhelpers',

    # Useful tools
    'kitchen',
    'python-fedora',

    # tw2
    'tw2.core',
    'tw2.dynforms',
    'tw2.forms',
    'tw2.sqla',
    'tw2.jqplugins.jqgrid',

    # i18n
    'Babel',
    'lingua',

    # External resources
    'python-bugzilla',
    ]

if sys.version_info[:3] < (2,5,0):
    requires.append('pysqlite')

setup(name='bodhi',
      version='2.0',
      description='bodhi',
      long_description=README + '\n\n' +  CHANGES,
      classifiers=[
        "Programming Language :: Python",
        "Framework :: Pylons",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        ],
      author='',
      author_email='',
      url='',
      keywords='web pylons pyramid',
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

