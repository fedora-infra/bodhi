# $Id: $

##
## Monkeypatch CherryPy's DecodingFilter to fix the issue when someone
## POSTs a request after their session times out.  This filter will prevent
## the decoding from happening twice.
##
## Taken from http://trac.turbogears.org/ticket/1022#comment:4
##

import cherrypy
from cherrypy.filters.basefilter import BaseFilter

class BodhiDecodingFilter(BaseFilter):
    """Automatically decodes request parameters (except uploads)."""

    def before_main(self):
        conf = cherrypy.config.get
        if not conf('decoding_filter.on', False):
            return
        if getattr(cherrypy.request, "_decoding_attempted", False):
            return
        cherrypy.request._decoding_attempted = True

from cherrypy.filters.decodingfilter import DecodingFilter
DecodingFilter.before_main = BodhiDecodingFilter().before_main
