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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import os
import logging
import textwrap
import warnings
import requests

from fedora.client import OpenIdBaseClient, FedoraClientError, BaseClient
import fedora.client.openidproxyclient

__version__ = '2.0.0'
log = logging.getLogger(__name__)

BASE_URL = 'https://admin.fedoraproject.org/updates/'
STG_BASE_URL = 'https://admin.stg.fedoraproject.org/updates/'
STG_OPENID_API = 'https://id.stg.fedoraproject.org/api/v1/'


class BodhiClientException(FedoraClientError):
    pass


def BodhiClient(base_url=BASE_URL, staging=False, **kwargs):
    if staging:
        log.info('Using bodhi2 STAGING environment')
        base_url = STG_BASE_URL
        fedora.client.openidproxyclient.FEDORA_OPENID_API = STG_OPENID_API

    log.debug('Querying bodhi API version')
    api_url = base_url + 'api_version'
    response = requests.head(api_url)
    if response.status_code == 200:
        print('Bodhi 2 detected')
        return Bodhi2Client(base_url=base_url, staging=staging, **kwargs)
    else:
        print('Bodhi 1 detected')
        return Bodhi1Client(base_url, **kwargs)


class Bodhi2Client(OpenIdBaseClient):

    def __init__(self, base_url=BASE_URL, username=None, password=None,
                 staging=False, **kwargs):
        if staging:
            log.info('Using bodhi2 STAGING environment')
            base_url = STG_BASE_URL
            fedora.client.openidproxyclient.FEDORA_OPENID_API = STG_OPENID_API
        super(Bodhi2Client, self).__init__(base_url, login_url=base_url +
                                          'login', debug=True, **kwargs)

        if username and password:
            self.login(username, password)
            self.username = username

    def save(self, **kwargs):
        """ Save an update.

        This entails either creating a new update, or editing an existing one.
        To edit an existing update, you must specify the update title in
        the ``edited`` keyword argument.

        :kwarg builds: A list of koji builds for this update.
        :kwarg type: The type of this update: ``security``, ``bugfix``,
            ``enhancement``, and ``newpackage``.
        :kwarg bugs: A list of Red Hat Bugzilla ID's associated with this
            update.
        :kwarg notes: Details as to why this update exists.
        :kwarg request: Request for this update to change state, either to
            ``testing``, ``stable``, ``unpush``, ``obsolete`` or None.
        :kwarg close_bugs: Close bugs when update is stable
        :kwarg suggest: Suggest that the user reboot or logout after update.
            (``reboot``, ``logout``)
        :kwarg inheritance: Follow koji build inheritance, which may result in
            this update being pushed out to additional releases.
        :kwarg autokarma: Allow bodhi to automatically change the state of this
            update based on the ``karma`` from user feedback.  It will
            push your update to ``stable`` once it reaches the ``stable_karma``
            and unpush your update when reaching ``unstable_karma``.
        :kwarg stable_karma: The upper threshold for marking an update as
            ``stable``.
        :kwarg unstable_karma: The lower threshold for unpushing an update.
        :kwarg edited: The update title of the existing update that we are
            editing.
        :kwarg severity: The severity of this update (``urgent``, ``high``,
            ``medium``, ``low``)
        :kwarg requirements: A list of required Taskotron tests that must pass
            for this update to reach stable. (``depcheck``, ``upgradepath``,
            ``rpmlint``)
        :kwarg require_bugs: A boolean to require that all of the bugs in your
            update have been confirmed by testers.
        :kwarg require_testcases: A boolean to require that this update passes
            all test cases before reaching stable.

        """
        kwargs['csrf_token'] = self.csrf()
        if 'type_' in kwargs:
            # backwards compat
            warnings.warn('Parameter "type_" is deprecated. Please use "type" instead.')
            kwargs['type'] = kwargs['type_']
        return self.send_request('updates/', verb='POST', auth=True,
                                 data=kwargs)

    def request(self, update, request):
        """ Request an update state change.

        :arg update: The title of the update
        :arg request: The request (``testing``, ``stable``, ``obsolete``,
                                   ``unpush``, ``revoke``)
        """
        return self.send_request('updates/{}/request'.format(update),
                                 verb='POST', auth=True,
                                 data={'update': update, 'request': request,
                                       'csrf_token': self.csrf()})

    def delete(self, update):
        warnings.warn('Deleting updates has been disabled in Bodhi2. '
                      'This API call will unpush the update instead. '
                      'Please use `set_request(update, "unpush")` instead')
        self.request(update, 'unpush')

    def query(self, **kwargs):
        if 'limit' in kwargs:  # bodhi1 compat
            kwargs['rows_per_page'] = kwargs['limit']
            del(kwargs['limit'])
        return self.send_request('updates', verb='GET', params=kwargs)

    def comment(self, update, comment, karma=0, email=None):
        """ Add a comment to an update.

        :arg update: The title of the update comment on.
        :arg comment: The text of the comment.
        :kwarg karma: The karma of this comment (-1, 0, 1)
        :kwarg email: Whether or not to trigger email notifications

        """
        return self.send_request('comments/', verb='POST', auth=True,
                data={'update': update, 'text': comment,
                      'karma': karma, 'email': email,
                      'csrf_token': self.csrf()})

    def csrf(self, **kwargs):
        return self.send_request('csrf', verb='GET',
                                 params=kwargs).json()['csrf_token']

    def parse_file(self, input_file):
        """ Parse an update template file.

        :arg input_file: The filename of the update template.

        Returns an array of dictionaries of parsed update values which
        can be directly passed to the ``save`` method.

        """
        from ConfigParser import SafeConfigParser

        if not os.path.exists(input_file):
            raise ValueError("No such file or directory: %s" % input_file)

        config = SafeConfigParser()
        read = config.read(input_file)

        if len(read) != 1 or read[0] != input_file:
            raise ValueError("Invalid input file: %s" % input_file)

        updates = []

        for section in config.sections():
            update = {
                'builds': section, 'bugs': config.get(section, 'bugs'),
                'close_bugs': config.getboolean(section, 'close_bugs'),
                'type': config.get(section, 'type'),
                'request': config.get(section, 'request'),
                'severity': config.get(section, 'severity'),
                'notes': config.get(section, 'notes'),
                'autokarma': config.get(section, 'autokarma'),
                'stable_karma': config.get(section, 'stable_karma'),
                'unstable_karma': config.get(section, 'unstable_karma'),
                'suggest': config.get(section, 'suggest'),
                }

            updates.append(update)

        return updates

    def latest_builds(self, package):
        return self.send_request('latest_builds', params={'package': package})

    def testable(self):
        """ Get a list of installed testing updates.

        This method is a generate that yields packages that you currently
        have installed that you have yet to test and provide feedback for.

        """
        import dnf
        base = dnf.Base()
        sack = base.fill_sack(load_system_repo=True)
        query = sack.query()
        installed = query.installed()
        with open('/etc/fedora-release', 'r') as f:
            fedora = f.readlines()[0].split()[2]
        tag = 'f%s-updates-testing' % fedora
        builds = self.get_koji_session(
            login=False).listTagged(tag, latest=True)
        for build in builds:
            pkgs = installed.filter(name=build['name'], version=build['version'],
                                    release=build['release']).run()
            if len(pkgs):
                update_list = self.query(builds=build['nvr'])['updates']
                for update in update_list:
                    yield update

    def update_str(self, update, minimal=False):
        """ Return a string representation of a given update dictionary.

        :arg update: An update dictionary, acquired by the ``list`` method.
        :kwarg minimal: Return a minimal one-line representation of the update.

        """
        if isinstance(update, basestring):
            return update
        if minimal:
            val = ""
            date = update['date_pushed'] and update['date_pushed'].split()[0] \
                or update['date_submitted'].split()[0]
            val += ' %-43s  %-11s  %-8s  %10s ' % (update['builds'][0]['nvr'],
                                                   update['type'],
                                                   update['status'], date)
            for build in update['builds'][1:]:
                val += '\n %s' % build['nvr']
            return val
        val = "%s\n%s\n%s\n" % ('=' * 80, '\n'.join(
            textwrap.wrap(update['title'].replace(',', ', '), width=80,
                          initial_indent=' '*5, subsequent_indent=' '*5)), '=' * 80)
        if update['alias']:
            val += "  Update ID: %s\n" % update['alias']
        val += """    Release: %s
     Status: %s
       Type: %s
      Karma: %d""" % (update['release']['long_name'], update['status'],
                      update['type'], update['karma'])
        if update['request'] is not None:
            val += "\n    Request: %s" % update['request']
        if len(update['bugs']):
            bugs = ''
            i = 0
            for bug in update['bugs']:
                bugstr = '%s%s - %s\n' % (i and ' ' * 11 + ': ' or '',
                                          bug['bug_id'], bug['title'])
                bugs += '\n'.join(textwrap.wrap(bugstr, width=67,
                                                subsequent_indent=' '*11+': ')) + '\n'
                i += 1
            bugs = bugs[:-1]
            val += "\n       Bugs: %s" % bugs
        if update['notes']:
            notes = textwrap.wrap(update['notes'], width=67,
                                  subsequent_indent=' ' * 11 + ': ')
            val += "\n      Notes: %s" % '\n'.join(notes)
        val += """
  Submitter: %s
  Submitted: %s\n""" % (update['user']['name'], update['date_submitted'])
        if len(update['comments']):
            val += "   Comments: "
            comments = []
            for comment in update['comments']:
                if comment['anonymous']:
                    anonymous = " (unauthenticated)"
                else:
                    anonymous = ""
                comments.append("%s%s%s - %s (karma %s)" % (' ' * 13,
                                comment['user']['name'], anonymous,
                                comment['timestamp'], comment['karma']))
                if comment['text']:
                    text = textwrap.wrap(comment['text'], initial_indent=' ' * 13,
                                         subsequent_indent=' ' * 13, width=67)
                    comments.append('\n'.join(text))
            val += '\n'.join(comments).lstrip() + '\n'
        if update['alias']:
            val += "\n  %s\n" % ('%s%s/%s' % (self.base_url,
                                              update['release']['name'],
                                              update['alias']))
        else:
            val += "\n  %s\n" % ('%s%s' % (self.base_url, update['title']))
        return val

    def get_releases(self, **kwargs):
        """ Return a list of bodhi releases.

        This method returns a dictionary in the following format::

            {"releases": [
                {"dist_tag": "dist-f12", "id_prefix": "FEDORA",
                 "locked": false, "name": "F12", "long_name": "Fedora 12"}]}
        """
        return self.send_request('releases', params=kwargs)

    def get_koji_session(self, login=True):
        """ Return an authenticated koji session """
        import koji
        from iniparse.compat import ConfigParser
        config = ConfigParser()
        if os.path.exists(os.path.join(os.path.expanduser('~'), '.koji', 'config')):
            config.readfp(open(os.path.join(os.path.expanduser('~'), '.koji', 'config')))
        else:
            config.readfp(open('/etc/koji.conf'))
        cert = os.path.expanduser(config.get('koji', 'cert'))
        ca = os.path.expanduser(config.get('koji', 'ca'))
        serverca = os.path.expanduser(config.get('koji', 'serverca'))
        session = koji.ClientSession(config.get('koji', 'server'))
        if login:
            session.ssl_login(cert=cert, ca=ca, serverca=serverca)
        return session

    koji_session = property(fget=get_koji_session)

    def candidates(self):
        """ Get a list list of update candidates.

        This method is a generator that returns a list of koji builds that
        could potentially be pushed as updates.
        """
        if not self.username:
            raise BodhiClientException('You must specify a username')
        builds = []
        data = self.get_releases().json()
        koji = self.get_koji_session(login=False)
        for release in data['releases']:
            try:
                for build in koji.listTagged(release['candidate_tag'], latest=True):
                    if build['owner_name'] == self.username:
                        builds.append(build)
            except:
                pass
        return builds
