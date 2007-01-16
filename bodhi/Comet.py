# $Id: Comet.py,v 1.2 2007/01/06 08:03:21 lmacken Exp $

import time
import cherrypy

class comet:

   def __init__(self, content_type):
      self.type = content_type
      self.delim = 'NextPart-' + str(time.time())
      cherrypy.response.headerMap['Content-Type'] = \
         'multipart/x-mixed-replace;boundary="%s"' % (self.delim)

   def __call__(self, func):
      def wrapper():
         for part in func():
            yield ("--%(delim)s\r\n" +
                   "Content-type: %(type)s\r\n\r\n" +
                   "%(part)s" +
                   "--%(delim)s\r\n") % {
                                           'delim' : self.delim,
                                           'part':str(part),
                                           'type':self.type
                                        }
      return wrapper
