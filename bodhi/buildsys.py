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

import time
import koji
import atexit
import logging

from os.path import join, expanduser
from bodhi.util import get_nvr

log = logging.getLogger(__name__)

_buildsystem = None

# Cached koji session info
_koji_session = None

# URL of the koji hub
_koji_hub = None


class Buildsystem:
    """
    The parent for our buildsystem.  Not only does this help us keep track of
    the functionality that we expect from our buildsystem, but it also alows
    us to create a development subclass of this object to use during
    development so we don't alter any production data.
    """
    def getBuild(self, *args, **kw):
        raise NotImplementedError

    def getLatestBuilds(self, *args, **kw):
        raise NotImplementedError

    def moveBuild(self, *args, **kw):
        raise NotImplementedError

    def ssl_login(self, *args, **kw):
        raise NotImplementedError

    def listBuildRPMs(self, *args, **kw):
        raise NotImplementedError

    def listTags(self, *args, **kw):
        raise NotImplementedError

    def listTagged(self, *args, **kw):
        raise NotImplementedError

    def taskFinished(self, *args, **kw):
        raise NotImplementedError

    def untagBuild(self, *args, **kw):
        raise NotImplementedError


class DevBuildsys(Buildsystem):
    """
    A dummy buildsystem instance used during development and testing
    """
    def moveBuild(self, *args, **kw):
        log.debug("moveBuild(%s, %s)" % (args, kw))

    def untagBuild(self, *args, **kw):
        log.debug("untagBuild(%s, %s)" % (args, kw))

    def ssl_login(self, *args, **kw):
        log.debug("ssl_login(%s, %s)" % (args, kw))

    def logout(self, *args, **kw):
        pass

    def taskFinished(self, task):
        return True

    def getTaskInfo(self, task):
        return {'state': koji.TASK_STATES['CLOSED']}

    def getBuild(self, build):
        n, v, r = get_nvr(build)
        return {'build_id': 127983, 'tag_name': 'dist-f11-updates',
                'owner_name': 'toshio', 'package_name': n,
                'task_id': 1616247, 'creation_event_id': 1952597,
                'creation_time': '2009-08-20 03:29:55.31542', 'epoch': None,
                'tag_id': 87, 'name': n, 'completion_time':
                '2009-08-20 03:33:51.134736', 'state': 1, 'version': v,
                'release': r, 'package_id': 1256, 'owner_id': 293, 'id':
                127983, 'nvr': build}

    def listBuildRPMs(self, *args, **kw):
        return [{'arch': 'src',
                 'build_id': 6475,
                 'buildroot_id': 1883,
                 'buildtime': 1178868422,
                 'epoch': None,
                 'id': 62330,
                 'name': 'TurboGears',
                 'nvr': 'TurboGears-1.0.2.2-2.fc7',
                 'payloadhash': '6787febe92434a9be2a8f309d0e2014e',
                 'release': '2.fc7',
                 'size': 761742,
                 'version': '1.0.2.2'},
                {'arch': 'noarch',
                 'build_id': 6475,
                 'buildroot_id': 1883,
                 'buildtime': 1178868537,
                 'epoch': None,
                 'id': 62331,
                 'name': 'TurboGears',
                 'nvr': 'TurboGears-1.0.2.2-2.fc7',
                 'payloadhash': 'f3ec9bdce453816f94283a15a47cb952',
                 'release': '2.fc7',
                 'size': 1993385,
                 'version': '1.0.2.2'},
                ]

    def listTags(self, build, *args, **kw):
        if build == 'bodhi-1.0-1':  # return a testing update
            return [{
                'arches': 'i386 x86_64 ppc ppc64',
                'id': 10,
                'locked': True,
                'name': 'f17-updates-testing',
                'perm': None,
                'perm_id': None
            }]
        else:
            return [{
                'arches': 'i386 x86_64 ppc ppc64',
                'name': 'f17-updates-candidate',
                'id': 10,
                'locked': True,
                'perm': None,
                'perm_id': None
            }]

    def listTagged(self, tag, *args, **kw):
        if tag not in (
                'dist-rawhide', 'dist-fc7', 'dist-fc7-updates-candidate',
                'dist-fc7-updates-testing', 'dist-fc7-updates',
                'dist-f8', 'dist-f8-updates', 'dist-f8-updates-testing',
                'dist-fc8', 'dist-fc8-updates',
                'dist-fc8-updates-testing', 'dist-f8-updates-candidate',
                'dist-f9', 'dist-f9-updates', 'dist-f9-updates-testing',
                'dist-f9-updates-candidate'):
            raise koji.GenericError
        return [self.getBuild(), ]

    def getLatestBuilds(self, *args, **kw):
        return [{
            'build_id': 127983,
            'tag_name': 'dist-f11-updates',
            'owner_name': 'toshio',
            'package_name': 'TurboGears',
            'task_id': 1616247,
            'creation_event_id': 1952597,
            'creation_time': '2009-08-20 03:29:55.31542',
            'epoch': None,
            'tag_id': 87,
            'name': 'TurboGears',
            'completion_time': '2009-08-20 03:33:51.134736',
            'state': 1,
            'version': '1.0.8',
            'release': '7.fc11',
            'package_id': 1256,
            'owner_id': 293,
            'id': 127983,
            'nvr': 'TurboGears-1.0.8-7.fc11'
        }]


def koji_login(config, client=None, clientca=None, serverca=None):
    """
    Login to Koji and return the session
    """
    global _koji_hub, _koji_session
    if not client:
        client = config.get('client_cert')
        if not client:
            client = join(expanduser('~'), '.fedora.cert')
    if not clientca:
        clientca = config.get('clientca_cert')
        if not clientca:
            clientca = join(expanduser('~'), '.fedora-upload-ca.cert')
    if not serverca:
        serverca = config.get('serverca_cert')
        if not serverca:
            serverca = join(expanduser('~'), '.fedora-server-ca.cert')

    _koji_hub = config.get('koji_hub')
    koji_client = koji.ClientSession(_koji_hub, {})
    koji_client.ssl_login(client, clientca, serverca)
    _koji_session = koji_client.sinfo
    return _koji_session


def get_session():
    """ Get a new buildsystem instance """
    global _buildsystem
    if not _buildsystem:
        log.warning('No buildsystem configured; assuming testing')
        return DevBuildsys()
    return _buildsystem()


def close_session():
    koji = get_session()
    try:
        koji.logout()
    except Exception, e:
        log.debug('Exception while closing koji session: %s' % e)

atexit.register(close_session)


def setup_buildsystem(settings):
    global _buildsystem, _koji_session, _koji_hub
    if _buildsystem:
        return
    buildsys = settings.get('buildsystem')
    if buildsys == 'koji':
        log.debug('Using Koji Buildsystem')
        koji_login(config=settings)
        _buildsystem = lambda: koji.ClientSession(_koji_hub, sinfo=_koji_session)
    elif buildsys in ('dev', 'dummy', None):
        log.debug('Using DevBuildsys')
        _buildsystem = DevBuildsys


def wait_for_tasks(tasks, sleep=300):
    """
    Wait for a list of koji tasks to complete.  Return the first task number
    to fail, otherwise zero.
    """
    log.debug("Waiting for %d tasks to complete: %s" % (len(tasks), tasks))
    failed_tasks = []
    session = get_session()
    for task in tasks:
        if not task:
            log.debug("Skipping task: %s" % task)
            continue
        while not session.taskFinished(task):
            time.sleep(sleep)
        task_info = session.getTaskInfo(task)
        if task_info['state'] != koji.TASK_STATES['CLOSED']:
            log.error("Koji task %d failed" % task)
            failed_tasks.append(task)
    log.debug("Tasks completed successfully!")
    return failed_tasks
