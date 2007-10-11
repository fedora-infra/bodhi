#!/usr/bin/python

# http://fedoraproject.org/wiki/PackagingDrafts/TGApps#head-de2a8e6576be53ce2b323722cf9fb92c1469adda
__requires__='TurboGears[future]'

import pkg_resources
import turbogears
import cherrypy
cherrypy.lowercase_api = True

from os.path import exists, join, dirname
import sys

# first look on the command line for a desired config file,
# if it's not on the command line, then
# look for setup.py in this directory. If it's not there, this script is
# probably installed
if len(sys.argv) > 1:
    turbogears.update_config(configfile=sys.argv[1], 
        modulename="bodhi.config")
elif exists(join(dirname(__file__), "setup.py")):
    turbogears.update_config(configfile="dev.cfg",
        modulename="bodhi.config")
else:
    turbogears.update_config(configfile="prod.cfg",
        modulename="bodhi.config")

## Schedule our periodic tasks
from bodhi import jobs
turbogears.startup.call_on_startup.append(jobs.schedule)

## Start our CherryPy server
from bodhi.controllers import Root
turbogears.start_server(Root())
