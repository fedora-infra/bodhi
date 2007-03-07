# $Id: mail.py,v 1.4 2007/01/08 06:07:07 lmacken Exp $
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

import re
import turbomail
from turbogears import config

release_team = config.get('release_team_address')
from_addr = config.get('from_address')

##
## All of the email messages that bodhi is going to be sending around, not
## including the update notifications.
##
## Right now this is a bit scary; the 'fields' field represents all of the 
## update fields in the body of the message that need to be expanded.
##
## TODO: we might want to think about pulling this stuff out into a separate
## configurationf file (using ConfigObj?)
##
messages = {
    'new' : {
        'subject' : '[Fedora Update] [new] %(package)s',
        'body'    : """\
%(email)s has submitted a new update for %(release)s

%(updatestr)s
""",
        'fields'  : lambda x: {
                        'email'     : x.submitter,
                        'release'   : x.release.long_name,
                        'updatestr' : str(x)
                    }
        },

    'deleted' : {
        'subject' : '[Fedora Update] [deleted] %(package)s',
        'body'    : """\
%(email)s has deleted the %(package)s update for %(release)s
""",
        'fields'  : lambda x: {
                        'package'   : x.nvr,
                        'email'     : x.submitter,
                        'release'   : x.release.long_name
                    }
        },

    'edited' : {
        'subject' : '[Fedora Update] [edited] %(package)s',
        'body'    : """\
%(email)s has edited the %(package)s update for %(release)s

%(updatestr)s
""",
        'fields'  : lambda x: {
                        'package'   : x.nvr,
                        'email'     : x.submitter,
                        'release'   : x.release.long_name,
                        'updatestr' : str(x)
                    }
        },

    'pushed' : {
        'subject' : '[Fedora Update] [pushed] %(package)s',
        'body'    : """\
%(package)s has been successfully pushed for %(release)s.
""",
        'fields'  : lambda x: {
                        'package' : x.nvr,
                        'release' : x.release.long_name
                    }
    },

    'push' : {
        'subject' : '[Fedora Update] [push] %(package)s',
        'body'    : """\
%(submitter)s has requested the pushing of the following update:\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'submitter' : x.submitter,
                        'updatestr' : str(x)
                    }
    },

    'unpush' : {
        'subject' : '[Fedora Update] [unpush] %(package)s',
        'body'    : """\
%(submitter)s has requested the unpushing of the following update:\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'submitter' : x.submitter,
                        'updatestr' : str(x)
                    }
    },

    'unpushed' : {
        'subject' : '[Fedora Update] [unpushed] %(package)s',
        'body'    : """\
The following update has been unpushed\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'updatestr' : str(x)
                    }
    },

    'revoke' : {
        'subject' : '[Fedora Update] [revoked] %(package)s',
        'body'    : """\
%(submitter)s has revoked the pushing of the following update:\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'submitter' : x.submitter,
                        'updatestr' : str(x)
                    }
        },

    'moved' : {
        'subject' : '[Fedora Update] [moved] %(package)s',
        'body'    : """\
The following update has been moved from Testing to Final:\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'updatestr' : str(x)
                    }
        }
}

def send(to, msg_type, update):
    """ Send an update notification email to a given recipient """
    message = turbomail.Message(from_addr, to, messages[msg_type]['subject'] %
                                {'package': update.nvr})
    message.plain = messages[msg_type]['body'] % \
                    messages[msg_type]['fields'](update)
    # TODO: uncomment me when we have the password situation figured out
    # and can actually auth for outgoing mail
    #turbomail.enqueue(message)

def send_admin(msg_type, update):
    """ Send an update notification to the admins/release team. """
    send(release_team, msg_type, update)
