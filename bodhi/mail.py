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
import koji
import logging
import turbomail

from os.path import join
from turbomail import MailNotEnabledException
from turbogears import config, identity

from bodhi.util import sha1sum, rpm_fileheader
from bodhi.exceptions import RPMNotFound

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
        'body'    : """\
%(email)s has submitted a new update for %(release)s\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'email'     : identity.current.user_name,
                        'release'   : x.release.long_name,
                        'updatestr' : str(x)
                    }
        },

    'deleted' : {
        'body'    : """\
%(email)s has deleted the %(package)s update for %(release)s\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'package'   : x.title,
                        'email'     : identity.current.user_name,
                        'release'   : '%s %s' % (x.release.long_name, x.status),
                        'updatestr' : str(x)
                    }
        },

    'edited' : {
        'body'    : """\
%(email)s has edited the %(package)s update for %(release)s\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'package'   : x.title,
                        'email'     : identity.current.user_name,
                        'release'   : '%s %s' % (x.release.long_name, x.status),
                        'updatestr' : str(x)
                    }
        },

    'pushed' : {
        'body'    : """\
%(package)s has been successfully pushed for %(release)s.\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'package'   : x.title,
                        'release'   : '%s %s' % (x.release.long_name, x.status),
                        'updatestr' : str(x)
                    }
    },

    'push' : {
        'body'    : """\
%(submitter)s has requested the pushing of the following update:\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'submitter' : identity.current.user_name,
                        'updatestr' : str(x)
                    }
    },

    'unpush' : {
        'body'    : """\
%(submitter)s has requested the unpushing of the following update:\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'submitter' : identity.current.user_name,
                        'updatestr' : str(x)
                    }
    },

    'unpushed' : {
        'body'    : """\
The following update has been unpushed\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'updatestr' : str(x)
                    }
    },

    'revoke' : {
        'body'    : """\
%(submitter)s has revoked the request of the following update:\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'submitter' : identity.current.user_name,
                        'updatestr' : str(x)
                    }
        },

    'move' : {
        'body'    : """\
%(submitter)s has requested the moving of the following update from Testing to Stable:\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'submitter' : identity.current.user_name,
                        'updatestr' : str(x)
                    }
    },

    'moved' : {
        'body'    : """\
The following update has been moved from Testing to Stable:\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'updatestr' : str(x)
                    }
    },

    'stablekarma' : {
        'body'    : """\
The following update has reached a karma of %(karma)d and is being automatically
marked as stable.\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'karma'     : x.karma,
                        'updatestr' : str(x) 
                    }
    },

    'comment' : {
        'body'    : """\
The following comment has been added to the %(package)s update:

%(comment)s

To reply to this comment, please visit the URL at the bottom of this mail

%(updatestr)s
""",
        'fields' : lambda x: {
                        'package'   : x.title,
                        'comment'   : x.comments[-1],
                        'updatestr' : str(x)
                   }
    },

    'old_testing' : {
        'body'    : """\
The update for %(package)s has been in 'testing' status for over 2 weeks.
This update can be marked as stable after it achieves a karma of %(stablekarma)d
or by clicking 'Push to Stable'.

This is just a courtesy nagmail.  Updates may reside in the testing repository
for more than 2 weeks if you deem it necessary.

You can submit this update to be pushed to the stable repository by going to
the following URL:

    http://admin.fedoraproject.org/updates/move/%(package)s

%(updatestr)s
""",
        'fields' : lambda x: {
                        'package'     : x.title,
                        'stablekarma' : config.get('stable_karma', 3),
                        'updatestr'   : str(x)
                   }
    }

}

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
URL         : %(url)s
Summary     : %(summary)s
Description :
%(description)s

--------------------------------------------------------------------------------
%(notes)s%(changelog)s%(references)sUpdated packages:

%(filelist)s

This update can be installed with the "yum" update program.  Use 
su -c 'yum%(yum_repository)s update %(name)s' 
at the command line.  For more information, refer to "Managing Software
with yum", available at http://docs.fedoraproject.org/yum/.
--------------------------------------------------------------------------------
"""

def get_template(update):
    from bodhi.buildsys import get_session
    line = str('-' * 80) + '\n'
    templates = []
    koji_session = get_session()

    for build in update.builds:
        h = build.get_rpm_header()
        info = {}
        info['date'] = str(update.date_pushed)
        info['name'] = h[rpm.RPMTAG_NAME]
        info['summary'] = h[rpm.RPMTAG_SUMMARY]
        info['version'] = h[rpm.RPMTAG_VERSION]
        info['release'] = h[rpm.RPMTAG_RELEASE]
        info['url']     = h[rpm.RPMTAG_URL]
        if update.status == 'testing':
            info['testing'] = ' Test'
            info['yum_repository'] = ' --enablerepo=updates-testing'
        else:
            info['testing'] = ''
            info['yum_repository'] = ''
        
        info['subject'] = "%s%s%s Update: %s" % (
                update.type == 'security' and '[SECURITY] ' or '',
                update.release.long_name, info['testing'], build.nvr)
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
        for pkg in koji_session.listBuildRPMs(build.nvr):
            filename = "%s.%s.rpm" % (pkg['nvr'], pkg['arch'])
            path = join(config.get('build_dir'), info['name'], info['version'],
                        info['release'], pkg['arch'])
            filelist.append("%s %s" % (sha1sum(join(path, filename)), filename))
        info['filelist'] = '\n'.join(filelist)

        # Add this updates referenced Bugzillas and CVEs
        i = 1
        info['references'] = ""
        if len(update.bugs) or len(update.cves):
            info['references'] = "References:\n\n"
            for bug in update.bugs:
                title = (bug.title != 'Unable to fetch title' and
                         bug.title != 'Invalid bug number') and \
                        ' - %s' % bug.title or ''
                info['references'] += "  [ %d ] Bug #%d%s\n        %s\n" % \
                                      (i, bug.bz_id, title, bug.get_url())
                i += 1
            for cve in update.cves:
                info['references'] += "  [ %d ] %s\n        %s\n" % \
                                      (i, cve.cve_id, cve.get_url())
                i += 1
            info['references'] += line

        # Find the most recent update for this package, other than this one
        lastpkg = build.get_latest()
        log.debug("lastpkg = %s" % lastpkg)

        # Grab the RPM header of the previous update, and generate a ChangeLog
        info['changelog'] = ""
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
                    (str(build.get_changelog(oldtime)), line)
        except RPMNotFound:
            log.error("Cannot find 'latest' RPM for generating ChangeLog: %s" %
                      lastpkg)
        except Exception, e:
            log.error("Unknown exception thrown during ChangeLog generation: %s"
                      % str(e))

        for (key, value) in info.items():
            if value:
                info[key] = value.decode('utf8')

        templates.append((info['subject'], errata_template % info))

    return templates

def send_mail(sender, to, subject, body):
    message = turbomail.Message(sender, to, subject)
    message.plain = body
    try:
        turbomail.enqueue(message)
        log.debug("Sending mail: %s" % message.plain)
    except MailNotEnabledException:
        log.warning("TurboMail is not enabled!")
    except Exception, e:
        log.error("Exception thrown when trying to send mail: %s" % str(e))

def send(to, msg_type, update, sender=None):
    """ Send an update notification email to a given recipient """
    if not sender:
        sender = config.get('bodhi_email')
    if not sender:
        log.warning("bodhi_email not defined in app.cfg; unable to send mail")
        return
    send_mail(sender, to, '[Fedora Update] [%s] %s' % (msg_type, update.title),
              messages[msg_type]['body'] % messages[msg_type]['fields'](update))

def send_releng(subject, body):
    """ Send the Release Engineering team a message """
    send_mail(config.get('bodhi_email'), config.get('release_team_address'),
              subject, body)

def send_admin(msg_type, update, sender=None):
    """ Send an update notification to the admins/release team. """
    send(config.get('release_team_address'), msg_type, update, sender)
