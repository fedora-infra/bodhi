import os
import sys

from pyramid.paster import get_app, setup_logging

sys.stdout = sys.stderr

os.environ['PYTHON_EGG_CACHE'] = '/var/www/.python-eggs'

ini_path = '/etc/bodhi/production.ini'
setup_logging(ini_path)

application = get_app(ini_path, 'main')
