import sys
sys.path.append('/usr/local/turbogears/mysite')
sys.stdout = sys.stderr

# We only need this if we are using any eggs
#import os
#os.environ['PYTHON_EGG_CACHE'] = '/usr/local/turbogears/python-eggs'

import atexit
import cherrypy
import cherrypy._cpwsgi
import turbogears

turbogears.update_config(configfile="bodhi.cfg", modulename="bodhi.config")
turbogears.config.update({'global': {'server.environment': 'production'}})
turbogears.config.update({'global': {'autoreload.on': False}})
turbogears.config.update({'global': {'server.log_to_screen': False}})
turbogears.config.update({'global': {'server.webpath': '/updates'}})

import bodhi.controllers

cherrypy.root = bodhi.controllers.Root()

if cherrypy.server.state == 0:
    atexit.register(cherrypy.server.stop)
    cherrypy.server.start(init_only=True, server_class=None)

def application(environ, start_response):
    environ['SCRIPT_NAME'] = ''
    return cherrypy._cpwsgi.wsgiApp(environ, start_response)
