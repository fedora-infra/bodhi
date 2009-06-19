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
import logging
import turbomail

from textwrap import wrap
from turbogears import config, identity

from bodhi.util import rpm_fileheader, to_unicode
from bodhi.exceptions import RPMNotFound

log = logging.getLogger(__name__)

##
## All of the email messages that bodhi is going to be sending around.
##
messages = {

    'new' : {
        'body'    : u"""\
%(email)s has submitted a new update for %(release)s\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'email'     : identity.current.user_name,
                        'release'   : x.release.long_name,
                        'updatestr' : unicode(x)
                    }
        },

    'deleted' : {
        'body'    : u"""\
%(email)s has deleted the %(package)s update for %(release)s\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'package'   : x.title,
                        'email'     : identity.current.user_name,
                        'release'   : '%s %s' % (x.release.long_name, x.status),
                        'updatestr' : unicode(x)
                    }
        },

    'edited' : {
        'body'    : u"""\
%(email)s has edited the %(package)s update for %(release)s\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'package'   : x.title,
                        'email'     : identity.current.user_name,
                        'release'   : '%s %s' % (x.release.long_name, x.status),
                        'updatestr' : unicode(x)
                    }
        },

    'pushed' : {
        'body'    : u"""\
%(package)s has been successfully pushed for %(release)s.\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'package'   : x.title,
                        'release'   : '%s %s' % (x.release.long_name, x.status),
                        'updatestr' : unicode(x)
                    }
    },

    'testing' : {
        'body'    : u"""\
%(submitter)s has requested the pushing of the following update to testing:\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'submitter' : identity.current.user_name,
                        'updatestr' : unicode(x)
                    }
    },

    'unpush' : {
        'body'    : u"""\
%(submitter)s has requested the unpushing of the following update:\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'submitter' : identity.current.user_name,
                        'updatestr' : unicode(x)
                    }
    },

    'obsolete' : {
        'body'    : u"""\
%(submitter)s has obsoleted the following update:\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'submitter' : identity.current.user_name,
                        'updatestr' : unicode(x)
                    }
    },

    'unpushed' : {
        'body'    : u"""\
The following update has been unpushed\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'updatestr' : unicode(x)
                    }
    },

    'revoke' : {
        'body'    : u"""\
%(submitter)s has revoked the request of the following update:\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'submitter' : identity.current.user_name,
                        'updatestr' : unicode(x)
                    }
        },

    'stable' : {
        'body'    : u"""\
%(submitter)s has requested the pushing of the following update stable:\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'submitter' : identity.current.user_name,
                        'updatestr' : unicode(x)
                    }
    },

    'moved' : {
        'body'    : u"""\
The following update has been moved from Testing to Stable:\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'updatestr' : unicode(x)
                    }
    },

    'stablekarma' : {
        'body'    : u"""\
The following update has reached a karma of %(karma)d and is being automatically
marked as stable.\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'karma'     : x.karma,
                        'updatestr' : unicode(x) 
                    }
    },

    'unstable' : {
        'body'    : u"""\
The following update has reached a karma of %(karma)d and is being automatically
marked as unstable.  This update will be unpushed from the repository.\n\n%(updatestr)s
""",
        'fields'  : lambda x: {
                        'karma'     : x.karma,
                        'updatestr' : unicode(x) 
                    }
    },

    'comment' : {
        'body'    : u"""\
The following comment has been added to the %(package)s update:

%(comment)s

To reply to this comment, please visit the URL at the bottom of this mail

%(updatestr)s
""",
        'fields' : lambda x: {
                        'package'   : x.title,
                        'comment'   : x.get_comments()[-1],
                        'updatestr' : unicode(x)
                   }
    },

    'old_testing' : {
        'body'    : u"""\
The update for %(package)s has been in 'testing' status for over 2 weeks.
This update can be marked as stable after it achieves a karma of %(stablekarma)d
or by clicking 'Push to Stable'.

This is just a courtesy nagmail.  Updates may reside in the testing repository
for more than 2 weeks if you deem it necessary.

You can submit this update to be pushed to the stable repository by going to
the following URL:

    http://admin.fedoraproject.org/updates/request/stable/%(package)s

or by running the following command with the bodhi-client:

    bodhi -R stable %(package)s

%(updatestr)s
""",
        'fields' : lambda x: {
                        'package'     : x.title,
                        'stablekarma' : x.builds[0].package.stable_karma,
                        'updatestr'   : unicode(x)
                   }
    },

    'security' : {
        'body'    : u"""\
%(submitter)s has submitted the following update.

%(updatestr)s

To approve this update and request that it be pushed to stable, you can use 
the link below:

    http://admin.fedoraproject.org/updates/approve/%(package)s
""",
        'fields'  : lambda x: {
                        'package'   : x.title,
                        'submitter' : identity.current.user_name,
                        'updatestr' : unicode(x)
                    }
    },

}

fedora_errata_template = u"""\
--------------------------------------------------------------------------------
Fedora%(testing)s Update Notification
%(updateid)s
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
%(notes)s%(changelog)s%(references)s
This update can be installed with the "yum" update program.  Use 
su -c 'yum%(yum_repository)s update %(name)s' at the command line.
For more information, refer to "Managing Software with yum",
available at http://docs.fedoraproject.org/yum/.

All packages are signed with the Fedora Project GPG key.  More details on the
GPG keys used by the Fedora Project can be found at
http://fedoraproject.org/keys
--------------------------------------------------------------------------------
"""

fedora-epel_errata_template = u"""\
--------------------------------------------------------------------------------
Fedora EPEL%(testing)s Update Notification
%(updateid)s
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
%(notes)s%(changelog)s%(references)s
This update can be installed with the "yum" update programs.  Use
su -c 'yum%(yum_repository)s update %(name)s' at the command line.
For more information, refer to "Managing Software with yum",
available at http://docs.fedoraproject.org/yum/.

All packages are signed with the Fedora EPEL GPG key.  More details on the
GPG keys used by the Fedora Project can be found at
https://fedoraproject.org/keys
--------------------------------------------------------------------------------
"""

maillist_template = u"""\
================================================================================
 %(name)s-%(version)s-%(release)s (%(updateid)s)
 %(summary)s
--------------------------------------------------------------------------------
%(notes)s%(changelog)s%(references)s
"""


def get_template(update, use_template=fedora_errata_template):
    """
    Build the update notice for a given update.
    @param use_template: the template to generate this notice with
    """
    line = unicode('-' * 80) + '\n'
    templates = []

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
            if update.release.name in ('F9', 'F8'):
                info['yum_repository'] = ' --enablerepo=updates-testing-newkey'
            else:
                info['yum_repository'] = ' --enablerepo=updates-testing'
        else:
            info['testing'] = ''
            info['yum_repository'] = ''

        info['subject'] = u"%s%s%s Update: %s" % (
                update.type == 'security' and '[SECURITY] ' or '',
                update.release.long_name, info['testing'], build.nvr)
        info['updateid'] = update.updateid
        info['description'] = h[rpm.RPMTAG_DESCRIPTION]
        info['product'] = update.release.long_name
        info['notes'] = ""
        if update.notes and len(update.notes):
            info['notes'] = u"Update Information:\n\n%s\n" % \
                    '\n'.join(wrap(update.notes, width=80))
            info['notes'] += line

        # Add this updates referenced Bugzillas and CVEs
        i = 1
        info['references'] = ""
        if len(update.bugs) or len(update.cves):
            info['references'] = u"References:\n\n"
            parent = True in [bug.parent for bug in update.bugs]
            for bug in update.bugs:
                # Don't show any tracker bugs for security updates
                if update.type == 'security':
                    # If there is a parent bug, don't show trackers
                    if parent and not bug.parent:
                        log.debug("Skipping tracker bug %s" % bug)
                        continue
                title = (bug.title != 'Unable to fetch title' and
                         bug.title != 'Invalid bug number') and \
                        ' - %s' % bug.title or ''
                info['references'] += u"  [ %d ] Bug #%d%s\n        %s\n" % \
                                      (i, bug.bz_id, title, bug.get_url())
                i += 1
            for cve in update.cves:
                info['references'] += u"  [ %d ] %s\n        %s\n" % \
                                      (i, cve.cve_id, cve.get_url())
                i += 1
            info['references'] += line

        # Find the most recent update for this package, other than this one
        lastpkg = build.get_latest()
        log.debug("lastpkg = %s" % lastpkg)

        # Grab the RPM header of the previous update, and generate a ChangeLog
        info['changelog'] = u""
        try:
            oldh = rpm_fileheader(lastpkg)
            oldtime = oldh[rpm.RPMTAG_CHANGELOGTIME]
            text = oldh[rpm.RPMTAG_CHANGELOGTEXT]
            del oldh
            if not text:
                oldtime = 0
            elif len(text) != 1:
                oldtime = oldtime[0]
            info['changelog'] = u"ChangeLog:\n\n%s%s" % \
                    (to_unicode(build.get_changelog(oldtime)), line)
        except RPMNotFound:
            log.error("Cannot find 'latest' RPM for generating ChangeLog: %s" %
                      lastpkg)
        except Exception, e:
            log.error("Unknown exception thrown during ChangeLog generation: %s"
                      % str(e))

        try:
            templates.append((info['subject'], use_template % info))
        except UnicodeDecodeError:
            # We can't trust the strings we get from RPM
            log.debug("UnicodeDecodeError! Will try again after decoding")
            for (key, value) in info.items():
                if value: info[key] = to_unicode(value)
            templates.append((info['subject'], use_template % info))

    return templates

def send_mail(sender, to, subject, body):
    from turbomail import MailNotEnabledException
    message = turbomail.Message(sender, to, subject)
    message.plain = body
    try:
        #log.debug("Sending mail: %s" % message.plain)
        turbomail.enqueue(message)
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
    if type(to) not in (list, set, tuple):
        to = [to]
    for person in to:
        send_mail(sender, person, '[Fedora Update] [%s] %s' % (msg_type,
                  update.title), messages[msg_type]['body'] % 
                  messages[msg_type]['fields'](update))

def send_releng(subject, body):
    """ Send the Release Engineering team a message """
    send_mail(config.get('bodhi_email'), config.get('release_team_address'),
              subject, body)

def send_admin(msg_type, update, sender=None):
    """ Send an update notification to the admins/release team. """
    send(config.get('release_team_address'), msg_type, update, sender)
