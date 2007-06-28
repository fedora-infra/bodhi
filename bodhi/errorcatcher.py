# $Id: $

import logging
import StringIO
import traceback
import turbomail

import cherrypy
from turbogears import config, controllers, identity

__all__ = ['ErrorCatcher']

log = logging.getLogger("turbogears.controllers")

ERROR_MAIL_TMPL = """\
----------URL----------

%(url)s

----------DATA:----------

%(data)s
"""

from cherrypy.filters.basefilter import BaseFilter

#class ErrorCatcher(controllers.RootController):
class ErrorCatcher(BaseFilter):
    """Base class for RootControllers that catches errors in production mode.

    Sends an email to the admin, when an error occurs. Does not send email
    on 404 errors unless the 'error_catcher.send_email_on_404' configuration
    option is set to True.

    For email sending to work, at least the configuration options
    'error_catcher.sender_email' and 'error_catcher.admin_email' must be
    set to valid email addresses.

    See docstring for method 'send_exception_email' for more email related
    configuration information.
    """

    _error_codes = {
        None: u'General Error',
        400: u'400 - Bad Request',
        401: u'401 - Unauthorized',
        403: u'403 - Forbidden',
        404: u'404 - Not Found',
        500: u'500 - Internal Server Error',
        501: u'501 - Not Implemented',
        502: u'502 - Bad Gateway',
    }
    _error_templates = {
        None: '.templates.unhandled_exception',
        404: '.templates.404_exception',
    }
    admin_group_name = 'admin'
    output_format = 'html'
    content_type = 'text/html'

    def __init__(self, *args, **kw):
        super(ErrorCatcher, self).__init__(*args, **kw)
        self.sender_email = config.get('bodhi_email')
        self.admin_email = config.get('bodhi_email')

    def cp_on_http_error(self, status, message):
        """Handle HTTP errors by sending an error page and email."""

        try:
            cherrypy._cputil._cp_on_http_error(status, message)
            error_msg = self.get_error_message(status, message)
            url = "%s %s" % (cherrypy.request.method, cherrypy.request.path)
            log.exception("CherryPy %s error (%s) for request '%s'", status,
              error_msg, url)

            if status != 404:
                buf = StringIO.StringIO()
                traceback.print_exc(file=buf)
                details = buf.getvalue()
                buf.close()
            else:
                details = '404 error'

            data = dict(
                status = status,
                message = message,
                error_msg = error_msg,
                admin = identity.in_group(self.admin_group_name),
                url = url,
                details = details,
            )

            if status != 404 or config.get('error_catcher.send_email_on_404'):
                try:
                    self.send_exception_email(status, url, details)
                    data['email_sent'] = True
                except Exception, exc:
                    log.exception('Error email failed: %s', exc)
                    data['email_sent'] = False
            else:
                data['email_sent'] = False

            self.send_error_page(status, data)
        # don't catch SystemExit
        except StandardError, exc:
            log.exception('Error handler failed: %s', exc)

    # Hook in error handler for production only
    if config.get('server.environment') == 'production':
        _cp_on_http_error = cp_on_http_error

    def send_error_page(self, status, data):
        """Send error page using matching template from self._error_templates.
        """

        body = controllers._process_output(
            data,
            self._error_templates.get(status, self._error_templates.get(None)),
            self.output_format,
            self.content_type,
            None
        )
        cherrypy.response.headers['Content-Length'] = len(body)
        cherrypy.response.body = body

    def send_exception_email(self, status, url, data):
        """ Send an email with the error info to the admin. """

        if not self.sender_email or not  self.admin_email:
            log.exception('Configuration error: could not send error'
              'because sender and/or admin email address is not set.')
            raise RuntimeError

        subject =  '%d ERROR on the Server' % status
        text = ERROR_MAIL_TMPL % dict(url=url, data=data)

        if config.get('mail.on'):
            msg = turbomail.Message(self.sender_email, self.admin_email, subject)
            msg.plain = text
            turbomail.enqueue(msg)

    def get_error_message(self, status, default=None):
        """Return string error for HTTP status code."""

        return self._error_codes.get(status, default or self._error_codes[None])
