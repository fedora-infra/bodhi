import __main__
__requires__ = __main__.__requires__ = 'WebOb>=1.4.1'  # Force forward-compat packages on epel7
import pkg_resources

import sys
sys.stdout = sys.stderr

import os
os.environ['PYTHON_EGG_CACHE'] = '/var/www/.python-eggs'

from pyramid.paster import get_app, setup_logging
ini_path = '/etc/bodhi/production.ini'
setup_logging(ini_path)

application = get_app(ini_path, 'main')
