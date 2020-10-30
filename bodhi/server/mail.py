# Copyright 2007-2019 Red Hat, Inc. and others.
#
# This file is part of Bodhi.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.
"""A collection of utilities for sending e-mail to Bodhi users."""
from textwrap import wrap
import os
import smtplib
import typing

from bodhi.server import log
from bodhi.server.config import config
from bodhi.server.util import get_rpm_header, get_absolute_path

if typing.TYPE_CHECKING:  # pragma: no cover
    from bodhi.server.models import Update  # noqa: 401


#
# All of the email messages that bodhi is going to be sending around.
#
MESSAGES = {

    'new': {
        'body': """\
%(email)s has submitted a new update for %(release)s\n\n%(updatestr)s
""",
        'fields': lambda agent, x: {
            'email': agent,
            'release': x.release.long_name,
            'updatestr': str(x)
        }
    },

    'deleted': {
        'body': """\
%(email)s has deleted the %(package)s update for %(release)s\n\n%(updatestr)s
""",
        'fields': lambda agent, x: {
            'package': x.title,
            'email': agent,
            'release': '%s %s' % (x.release.long_name, x.status),
            'updatestr': str(x)
        }
    },

    'edited': {
        'body': """\
%(email)s has edited the %(package)s update for %(release)s\n\n%(updatestr)s
""",
        'fields': lambda agent, x: {
            'package': x.title,
            'email': agent,
            'release': '%s %s' % (x.release.long_name, x.status),
            'updatestr': str(x)
        }
    },

    'pushed': {
        'body': """\
%(package)s has been successfully pushed for %(release)s.\n\n%(updatestr)s
""",
        'fields': lambda agent, x: {
            'package': x.title,
            'release': '%s %s' % (x.release.long_name, x.status),
            'updatestr': str(x)
        }
    },

    'testing': {
        'body': """\
%(submitter)s has requested the pushing of the following update to testing:\n
%(updatestr)s
""",
        'fields': lambda agent, x: {
            'submitter': agent,
            'updatestr': str(x)
        }
    },

    'unpush': {
        'body': """\
%(submitter)s has requested the unpushing of the following update:\n
%(updatestr)s
""",
        'fields': lambda agent, x: {
            'submitter': agent,
            'updatestr': str(x)
        }
    },

    'obsolete': {
        'body': """\
%(submitter)s has obsoleted the following update:\n\n%(updatestr)s
""",
        'fields': lambda agent, x: {
            'submitter': agent,
            'updatestr': str(x)
        }
    },

    'unpushed': {
        'body': """\
The following update has been unpushed\n\n%(updatestr)s
""",
        'fields': lambda agent, x: {
            'updatestr': str(x)
        }
    },

    'revoke': {
        'body': """\
%(submitter)s has revoked the request of the following update:\n\n%(updatestr)s
""",
        'fields': lambda agent, x: {
            'submitter': agent,
            'updatestr': str(x)
        }
    },

    'stable': {
        'body': """\
%(submitter)s has requested the pushing of the following update stable:\n
%(updatestr)s
""",
        'fields': lambda agent, x: {
            'submitter': agent,
            'updatestr': str(x)
        }
    },

    'moved': {
        'body': """\
The following update has been moved from Testing to Stable:\n\n%(updatestr)s
""",
        'fields': lambda agent, x: {
            'updatestr': str(x)
        }
    },

    'stablekarma': {
        'body': """\
The following update has reached a karma of %(karma)d and is being
automatically marked as stable.\n
%(updatestr)s
""",
        'fields': lambda agent, x: {
            'karma': x.karma,
            'updatestr': str(x)
        }
    },

    'unstable': {
        'body': """\
The following update has reached a karma of %(karma)d and is being
automatically marked as unstable. This update will be unpushed from the
repository.\n
%(updatestr)s
""",
        'fields': lambda agent, x: {
            'karma': x.karma,
            'updatestr': str(x)
        }
    },

    'comment': {
        'body': """\
The following comment has been added to the %(package)s update:

%(comment)s

To reply to this comment, please visit the URL at the bottom of this mail

%(updatestr)s
""",
        'fields': lambda agent, x: {
            'package': x.title,
            'comment': x.comments[-1],
            'updatestr': str(x)
        }
    },

    'old_testing': {
        'body': """\
The update for %(package)s has been in 'testing' status for over 2 weeks.
This update can be marked as stable after it achieves a karma of
%(stablekarma)d or by clicking 'Push to Stable'.

This is just a courtesy nagmail.  Updates may reside in the testing repository
for more than 2 weeks if you deem it necessary.

You can submit this update to be pushed to the stable repository by going to
the following URL:

    https://admin.fedoraproject.org/updates/request/stable/%(package)s

or by running the following command with the bodhi-client:

    bodhi -R stable %(package)s

%(updatestr)s
""",
        'fields': lambda agent, x: {
            'package': x.title,
            'stablekarma': x.stable_karma,
            'updatestr': str(x)
        }
    },

    'security': {
        'body': """\
%(submitter)s has submitted the following update.

%(updatestr)s

To approve this update and request that it be pushed to stable, you can use the
link below:

    https://admin.fedoraproject.org/updates/approve/%(package)s
""",
        'fields': lambda agent, x: {
            'package': x.title,
            'submitter': agent,
            'updatestr': str(x)
        }
    },

}


def read_template(name: str) -> str:
    """
    Read template text from file.

    Args:
        name: The name of the email template stored in 'release' table in database.
    Returns:
        The text read from the file.
    """
    location = config.get('mail.templates_basepath')
    directory = get_absolute_path(location)
    file_name = "%s.tpl" % (name)
    template_path = os.path.join(directory, file_name)

    if os.path.exists(template_path):
        try:
            with open(template_path) as template_file:
                return template_file.read()
        except IOError as e:
            log.error("Unable to read template file: %s" % (template_path))
            log.error("IO Error[%s]: %s" % (e.errno, e.strerror))
    else:
        log.error("Path does not exist: %s" % (template_path))


def get_template(update: 'Update', use_template: str = 'fedora_errata_template') -> list:
    """
    Build the update notice for a given update.

    Args:
        update: The update to generate a template about.
        use_template: The name of the variable in bodhi.server.mail that references the
            template to generate this notice with.
    Returns:
        A list of templates for the given update.
    """
    from bodhi.server.models import UpdateStatus, UpdateType
    use_template = read_template(use_template)
    line = str('-' * 80) + '\n'
    templates = []

    for build in update.builds:
        h = get_rpm_header(build.nvr)
        info = {}
        info['date'] = str(update.date_pushed)
        info['name'] = h['name']
        info['summary'] = h['summary']
        info['version'] = h['version']
        info['release'] = h['release']
        info['url'] = h['url']
        if update.status is UpdateStatus.testing:
            info['testing'] = ' Test'
            info['yum_repository'] = ' --enablerepo=updates-testing'
        else:
            info['testing'] = ''
            info['yum_repository'] = ''

        info['subject'] = "%s%s%s Update: %s" % (
            update.type is UpdateType.security and '[SECURITY] ' or '',
            update.release.long_name, info['testing'], build.nvr)
        info['updateid'] = update.alias
        info['description'] = h['description']
        info['product'] = update.release.long_name
        info['notes'] = ""
        if update.notes and len(update.notes):
            info['notes'] = "Update Information:\n\n%s\n" % \
                '\n'.join(wrap(update.notes, width=80))
            info['notes'] += line

        # Add this update's referenced Bugzillas
        i = 1
        info['references'] = ""
        if update.bugs:
            info['references'] = "References:\n\n"
            parent = True in [bug.parent for bug in update.bugs]
            for bug in update.bugs:
                # Don't show any tracker bugs for security updates
                if update.type is UpdateType.security:
                    # If there is a parent bug, don't show trackers
                    if parent and not bug.parent:
                        log.debug("Skipping tracker bug %s" % bug)
                        continue
                title = (
                    bug.title != 'Unable to fetch title' and bug.title != 'Invalid bug number') \
                    and ' - %s' % bug.title or ''
                info['references'] += "  [ %d ] Bug #%d%s\n        %s\n" % \
                                      (i, bug.bug_id, title, bug.url)
                i += 1
            info['references'] += line

        # generate a ChangeLog
        info['changelog'] = ""
        changelog = build.get_changelog(lastupdate=True)
        if changelog is not None:
            info['changelog'] = "ChangeLog:\n\n%s%s" % \
                (changelog, line)

        templates.append((info['subject'], use_template % info))

    return templates


def _send_mail(from_addr: str, to_addr: str, body: str) -> None:
    """
    Send emails with smtplib. This is a lower level function than send_e-mail().

    Args:
        from_addr: The e-mail address to use in the envelope from field.
        to_addr: The e-mail address to use in the envelope to field.
        body: The body of the e-mail.
    """
    smtp_server = config.get('smtp_server')
    if not smtp_server:
        log.info('Not sending email: No smtp_server defined')
        return
    smtp = None
    try:
        log.debug('Connecting to %s', smtp_server)
        smtp = smtplib.SMTP(smtp_server)
        smtp.sendmail(from_addr, [to_addr], body.encode('utf-8'))
    except smtplib.SMTPRecipientsRefused as e:
        log.warning('"recipient refused" for %r, %r' % (to_addr, e))
    except Exception:
        log.exception('Unable to send mail')
    finally:
        if smtp:
            smtp.quit()


def send_mail(from_addr: str, to_addr: str, subject: str, body_text: str,
              headers: typing.Optional[dict] = None) -> None:
    """
    Send an e-mail.

    Args:
        from_addr: The address to use in the From: header.
        to_addr: The address to send the e-mail to.
        subject: The subject of the e-mail.
        body_text: The body of the e-mail to be sent.
        headers: A mapping of header fields to values to be included in the e-mail,
            if not None.
    """
    if not from_addr:
        from_addr = config.get('bodhi_email')
    if not from_addr:
        log.warning('Unable to send mail: bodhi_email not defined in the config')
        return
    if to_addr in config.get('exclude_mail'):
        return

    msg = [f'From: {from_addr}', f'To: {to_addr}']
    if headers:
        for key, value in headers.items():
            msg.append(f'{key}: {value}')
    msg.append(f"X-Bodhi: {config.get('default_email_domain')}")
    msg += [f'Subject: {subject}', '', body_text]
    body = '\r\n'.join(msg)

    log.info('Sending mail to %s: %s', to_addr, subject)
    _send_mail(from_addr, to_addr, body)


def send(to: typing.Iterable[str], msg_type: str, update: 'Update',
         sender: typing.Optional[str] = None, agent: str = 'bodhi') -> None:
    """
    Send an update notification email to a given recipient.

    Args:
        to: An iterable strs of e-mail addresses to send an update e-mail to.
        msg_type: The message template to use. Should be one of the keys in the
            MESSAGES template.
        update: The Update we are mailing people about.
        sender: The address to use in the From: header. If None, the
            "bodhi_email" setting will be used as the From: header.
        agent: The username that performed the action that generated this e-mail.
    """
    critpath = getattr(update, 'critpath', False) and '[CRITPATH] ' or ''
    headers = {}

    if msg_type != 'buildroot_override':
        headers = {
            "X-Bodhi-Update-Type": update.type.description,
            "X-Bodhi-Update-Release": update.release.name,
            "X-Bodhi-Update-Status": update.status.description,
            "X-Bodhi-Update-Builds": ",".join([b.nvr for b in update.builds]),
            "X-Bodhi-Update-Title": update.get_title(nvr=True, beautify=True),
            "X-Bodhi-Update-Pushed": update.pushed,
            "X-Bodhi-Update-Submitter": update.user.name,
        }
        if update.request:
            headers["X-Bodhi-Update-Request"] = update.request.description
        initial_message_id = "<bodhi-update-%s-%s-%s@%s>" % (
            update.id, update.user.name, update.release.name,
            config.get('message_id_email_domain'))

        if msg_type == 'new':
            headers["Message-ID"] = initial_message_id
        else:
            headers["References"] = initial_message_id
            headers["In-Reply-To"] = initial_message_id

    subject_template = '[Fedora Update] %s[%s] %s'
    for person in to:
        subject = subject_template % (critpath, msg_type, update.get_title(nvr=True, beautify=True))
        fields = MESSAGES[msg_type]['fields'](agent, update)
        body = MESSAGES[msg_type]['body'] % fields
        send_mail(sender, person, subject, body, headers=headers)


def send_releng(subject: str, body: str) -> None:
    """
    Send the Release Engineering team a message.

    Args:
        subject: The subject of the e-mail.
        body: The body of the e-mail.
    """
    send_mail(config.get('bodhi_email'), config.get('release_team_address'),
              subject, body)
