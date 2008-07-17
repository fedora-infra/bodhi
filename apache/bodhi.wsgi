import sys
sys.stdout = sys.stderr
import pkg_resources
pkg_resources.require("CherryPy<3.0")

import atexit
import cherrypy
import cherrypy._cpwsgi
import turbogears

from bodhi.util import load_config
load_config()

turbogears.config.update({'global': {'server.environment': 'production'}})
turbogears.config.update({'global': {'autoreload.on': False}})
turbogears.config.update({'global': {'server.log_to_screen': False}})
turbogears.config.update({'global': {'server.webpath': '/updates'}})

from bodhi import jobs
turbogears.startup.call_on_startup.append(jobs.schedule)

import bodhi.controllers
cherrypy.root = bodhi.controllers.Root()

if cherrypy.server.state == 0:
    atexit.register(cherrypy.server.stop)
    cherrypy.server.start(init_only=True, server_class=None)

application = cherrypy._cpwsgi.wsgiApp

## Apparently this is needed if we are using a server.webpath, 
# but I seem to get lots of 404's when using it compared to without...
#def application(environ, start_response):
#    environ['SCRIPT_NAME'] = ''
#    return cherrypy._cpwsgi.wsgiApp(environ, start_response)
