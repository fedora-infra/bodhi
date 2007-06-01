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

import rpm
import time
import koji
import logging
import turbomail

from os.path import join, basename
from bodhi.util import sha1sum, rpm_fileheader
from bodhi.exceptions import RPMNotFound
from turbogears import config
from turbomail import MailNotEnabledException

log = logging.getLogger(__name__)

##
## All of the email messages that bodhi is going to be sending around, not
## including the update notifications.
##
## Right now this is a bit scary; the 'fields' field represents all of the 
## update fields in the body of the message that need to be expanded.
##
## TODO: we might want to think about pulling this stuff out into a separate
## configuration file (using ConfigObj?)
##
messages = {

    'new' : {
        'subject' : '[Fedora Update] [new] %(package)s',
        'body'    : """\
%(email)s has submitted a new update for %(release)s\n\n%(updatestr)s
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
%(email)s has deleted the %(package)s update for %(release)s\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'package'   : x.nvr,
                        'email'     : x.submitter,
                        'release'   : x.release.long_name,
                        'updatestr' : str(x)
                    }
        },

    'edited' : {
        'subject' : '[Fedora Update] [edited] %(package)s',
        'body'    : """\
%(email)s has edited the %(package)s update for %(release)s\n\n%(updatestr)s
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
%(package)s has been successfully pushed for %(release)s.\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'package'   : x.nvr,
                        'release'   : x.release.long_name,
                        'updatestr' : str(x)
                    }
    },

    'push' : {
        'subject' : '[Fedora Update] [push] %(package)s',
        'body'    : """\
%(submitter)s has requested the pushing of the following update:\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'submitter' : x.submitter,
                        'updatestr' : str(x)
                    }
    },

    'unpush' : {
        'subject' : '[Fedora Update] [unpush] %(package)s',
        'body'    : """\
%(submitter)s has requested the unpushing of the following update:\n\n%(updatestr)s
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
%(submitter)s has revoked the request of the following update:\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'submitter' : x.submitter,
                        'updatestr' : str(x)
                    }
        },

    'move' : {
        'subject' : '[Fedora Update] [move] %(package)s',
        'body'    : """\
%(submitter)s has requested the moving of the following update from Testing to Final:\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'submitter' : x.submitter,
                        'updatestr' : str(x)
                    }
    },

    'moved' : {
        'subject' : '[Fedora Update] [moved] %(package)s',
        'body'    : """\
The following update has been moved from Testing to Final:\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'updatestr' : str(x)
                    }
        },

    'comment' : {
        'subject' : '[Fedora Update] [comment] %(package)s',
        'body'    : """\
The following comment has been added to your %(package)s update:

%(comment)s
""",
        'fields' : lambda x: {
                        'package' : x.nvr,
                        'comment' : x.comments[-1]
                    }
    }
}

## TODO: subject isn't necessary?
errata_template = """\
--------------------------------------------------------------------------------
Fedora%(testing)s Update Notification
%(update_id)s
%(date)s
--------------------------------------------------------------------------------

Name        : %(name)s
Product     : %(product)s
Version     : %(version)s
Release     : %(release)s
Summary     : %(summary)s
Description :
%(description)s

--------------------------------------------------------------------------------
%(notes)s%(changelog)s%(references)sUpdated packages:

%(filelist)s

This update can be installed with the 'yum' update program.  Use 'yum update
package-name' at the command line.  For more information, refer to 'Managing
Software with yum,' available at http://docs.fedoraproject.org/yum/.
--------------------------------------------------------------------------------
"""

def get_template(update):
    h = update.get_rpm_header()
    line = str('-' * 80) + '\n'
    info = {}
    info['date'] = str(update.date_pushed)
    info['name'] = h[rpm.RPMTAG_NAME]
    info['summary'] = h[rpm.RPMTAG_SUMMARY]
    info['version'] = h[rpm.RPMTAG_VERSION]
    info['release'] = h[rpm.RPMTAG_RELEASE]
    info['testing'] = update.status == 'testing' and ' Test' or ''
    info['subject'] = "%s%s%s Update: %s" % (
            update.type == 'security' and '[SECURITY] ' or '',
            update.release.long_name, info['testing'], update.nvr)
    info['update_id'] = update.update_id
    info['description'] = h[rpm.RPMTAG_DESCRIPTION]
    #info['updatepath'] = update.get_repo()
    info['product'] = update.release.long_name
    info['notes'] = ""
    if update.notes and len(update.notes):
        info['notes'] = "Update Information:\n\n%s\n" % update.notes
        info['notes'] += line

    # Build the list of SHA1SUMs and packages
    filelist = []
    #for arch in update.filelist.keys():
    #    for pkg in update.filelist[arch]:
    #        filelist.append("%s  %s" % (sha1sum(pkg), join(arch,
    #                        pkg.find('debuginfo') != -1 and 'debug' or '',
    #                        basename(pkg))))
    #info['filelist'] = '\n'.join(filelist)

    from bodhi.buildsys import get_session
    koji_session = get_session()
    for pkg in koji_session.listBuildRPMs(update.nvr):
        filename = "%s.%s.rpm" % (pkg['nvr'], pkg['arch'])
        path = join(config.get('build_dir'), info['name'], info['version'],
                    info['release'], pkg['arch'])
        filelist.append("%s %s" % (sha1sum(join(path, filename)), filename))
    info['filelist'] = '\n'.join(filelist)

    # Add this updates referenced Bugzillas and CVEs
    info['references'] = ""
    if len(update.bugs) or len(update.cves):
        info['references'] = "References:\n\n"
        for bug in update.bugs:
            info['references'] += "  Bug #%d - %s\n" % (bug.bz_id,
                                                        bug.get_url())
        for cve in update.cves:
            info['references'] += "  %s - %s\n" % (cve.cve_id, cve.get_url())
        info['references'] += line

    # Find the most recent update for this package, other than this one
    lastpkg = update.get_latest()
    log.debug("lastpkg = %s" % lastpkg)

    # Grab the RPM header of the previous update, and generate a ChangeLog
    info['changelog'] = ""
    if lastpkg:
        try:
            oldh = rpm_fileheader(lastpkg)
            oldtime = oldh[rpm.RPMTAG_CHANGELOGTIME]
            text = oldh[rpm.RPMTAG_CHANGELOGTEXT]
            del oldh
            if not text:
                oldtime = 0
            elif len(text) != 1:
                oldtime = oldtime[0]
            info['changelog'] = "ChangeLog:\n\n%s%s" % \
                    (str(update.get_changelog(oldtime)), line)
        except RPMNotFound:
            log.error("Cannot find 'latest' RPM for generating ChangeLog: %s" %
                      lastpkg)

    for (key, value) in info.items():
        info[key] = koji.fixEncoding(value)

    return (info['subject'], errata_template % info)

def send(to, msg_type, update):
    """ Send an update notification email to a given recipient """
    bodhi = config.get('bodhi_email')
    if not bodhi:
        log.warning("bodhi_email not defined in app.cfg; unable to send mail")
        return

    message = turbomail.Message(bodhi, to, messages[msg_type]['subject'] %
                                { 'package' : update.nvr })
    message.plain = messages[msg_type]['body'] % \
                    messages[msg_type]['fields'](update)
    try:
        turbomail.enqueue(message)
        log.debug("Sending mail: %s" % message.plain)
    except MailNotEnabledException:
        log.warning("TurboMail is not enabled!")

def send_admin(msg_type, update):
    """ Send an update notification to the admins/release team. """
    send(config.get('release_team_address'), msg_type, update)
