import sys
sys.stdout = sys.stderr
import pkg_resources
pkg_resources.require("CherryPy<3.0")

import os
os.environ['PYTHON_EGG_CACHE'] = '/var/www/.python-eggs'

import atexit
import cherrypy
import cherrypy._cpwsgi
import turbogears
from fedora.tg.util import enable_csrf

from bodhi.util import load_config
load_config()

turbogears.config.update({'global': {'server.environment': 'production'}})
turbogears.config.update({'global': {'autoreload.on': False}})
turbogears.config.update({'global': {'server.log_to_screen': False}})
#turbogears.config.update({'global': {'server.webpath': None}})

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
