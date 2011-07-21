import sys
sys.stdout = sys.stderr

import __main__
__main__.__requires__ = __requires__ = 'TurboGears'
import pkg_resources
pkg_resources.require(__requires__)

import os
os.environ['PYTHON_EGG_CACHE'] = '/var/www/.python-eggs'

import atexit
import cherrypy
import cherrypy._cpwsgi
import turbogears
from fedora.tg.util import enable_csrf

from bodhi.util import load_config
load_config()

if turbogears.config.get('identity.provider') in ('sqlobjectcsrf', 'jsonfas2'):
    turbogears.startup.call_on_startup.append(enable_csrf)

from bodhi import jobs
turbogears.startup.call_on_startup.append(jobs.schedule)

import bodhi.controllers
cherrypy.root = bodhi.controllers.Root()

if cherrypy.server.state == 0:
    atexit.register(cherrypy.server.stop)
    cherrypy.server.start(init_only=True, server_class=None)

application = cherrypy._cpwsgi.wsgiApp
