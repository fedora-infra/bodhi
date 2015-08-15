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

from fedora.client import OpenIdBaseClient, FedoraClientError
import fedora.client.openidproxyclient

__version__ = '2.0.0'
log = logging.getLogger(__name__)

BASE_URL = 'https://admin.fedoraproject.org/updates/'
STG_BASE_URL = 'https://admin.stg.fedoraproject.org/updates/'
STG_OPENID_API = 'https://id.stg.fedoraproject.org/api/v1/'


class BodhiClientException(FedoraClientError):
    pass


class BodhiClient(OpenIdBaseClient):

    def __init__(self, base_url=BASE_URL, username=None, password=None,
                 staging=False, **kwargs):
        if staging:
            log.info('Using bodhi2 STAGING environment')
            base_url = STG_BASE_URL
            fedora.client.openidproxyclient.FEDORA_OPENID_API = STG_OPENID_API
        super(BodhiClient, self).__init__(base_url, login_url=base_url +
                                          'login', debug=True, **kwargs)

        if username and password:
            self.login(username, password)
            self.username = username

    def new(self, **kwargs):
        kwargs['csrf_token'] = self.csrf()
        if 'type_' in kwargs:
            # backwards compat
            warnings.warn('Parameter "type_" is deprecated. Please use "type" instead.')
            kwargs['type'] = kwargs['type_']
        return self.send_request('updates/', verb='POST', auth=True,
                                 data=kwargs)

    save = new  # backwards compat

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
        warnings.warn('This method has not been ported. Please file a bug if you need this')
        raise NotImplementedError

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
