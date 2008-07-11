# -*- coding: utf-8 -*-
#
# Copyright © 2008 Red Hat, Inc. All rights reserved.
#
# This copyrighted material is made available to anyone wishing to use, modify,
# copy, or redistribute it subject to the terms and conditions of the GNU
# General Public License v.2.  This program is distributed in the hope that it
# will be useful, but WITHOUT ANY WARRANTY expressed or implied, including the
# implied warranties of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.  You should have
# received a copy of the GNU General Public License along with this program;
# if not, write to the Free Software Foundation, Inc., 51 Franklin Street,
# Fifth Floor, Boston, MA 02110-1301, USA. Any Red Hat trademarks that are
# incorporated in the source code or documentation are not subject to the GNU
# General Public License and may only be used or replicated with the express
# permission of Red Hat, Inc.
#
# Author(s): Luke Macken <lmacken@redhat.com>
#
""" This module contains functions called from console script entry points. """

import sys
#import pkg_resources
#__requires__='TurboGears[future]'
#pkg_resources.require("TurboGears")

import turbogears
import cherrypy

from bodhi.util import load_config

cherrypy.lowercase_api = True

class ConfigurationError(Exception):
    pass

def start():
    '''Start the CherryPy application server.'''
    if len(sys.argv) > 1:
        load_config(sys.argv[1])
    else:
        load_config()

    ## Schedule our periodic tasks
    from bodhi import jobs
    turbogears.startup.call_on_startup.append(jobs.schedule)

    from bodhi.controllers import Root
    turbogears.start_server(Root())
