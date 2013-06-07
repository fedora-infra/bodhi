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
import logging

from os.path import join, expanduser
from turbogears import config

log = logging.getLogger(__name__)

## Our buildsystem session.  This could be a koji ClientSession or an instance
## of our Buildsystem class.
session = None


class Buildsystem(object):
    """
    The parent for our buildsystem.  Not only does this help us keep track of
    the functionality that we expect from our buildsystem, but it also alows
    us to create a development subclass of this object to use during development
    so we don't alter any production data.
    """
    def getBuild(self): raise NotImplementedError
    def getLatestBuilds(self): raise NotImplementedError
    def moveBuild(self): raise NotImplementedError
    def ssl_login(self): raise NotImplementedError
    def listBuildRPMs(self):raise NotImplementedError
    def listTags(self): raise NotImplementedError
    def listTagged(self): raise NotImplementedError
    def taskFinished(self): raise NotImplementedError
    def untagBuild(self): raise NotImplementedError
    def tagBuild(self): raise NotImplementedError


class DevBuildsys(Buildsystem):
    """
    A dummy buildsystem instance used during development and testing
    """

    def multiCall(self):
        pass

    def moveBuild(self, *args, **kw):
        log.debug("moveBuild(%s, %s)" % (args, kw))

    def tagBuild(self, *args, **kw):
        log.debug("tagBuild(%s, %s)" % (args, kw))

    def untagBuild(self, *args, **kw):
        log.debug("untagBuild(%s, %s)" % (args, kw))

    def ssl_login(self, *args, **kw):
        log.debug("ssl_login(%s, %s)" % (args, kw))

    def taskFinished(self, task):
        return True

    def getTaskInfo(self, task):
        return { 'state' : koji.TASK_STATES['CLOSED'] }

    def getBuild(self, build='fc7', other=False):
        if 'fc7' in build:
            data = {'build_id': 16058,
                    'completion_time': '2007-08-24 23:26:10.890319',
                    'creation_event_id': 151517,
                    'creation_time': '2007-08-24 19:38:29.422344',
                    'epoch': None,
                    'id': 16058,
                    'name': 'TurboGears',
                    'nvr': 'TurboGears-1.0.2.2-2.fc7',
                    'owner_id': 388,
                    'owner_name': 'lmacken',
                    'package_id': 8,
                    'package_name': 'TurboGears',
                    'release': '2.fc7',
                    'state': 1,
                    'tag_id': 19,
                    'tag_name': 'dist-fc7-updates-testing',
                    'task_id': 127621,
                    'version': '1.0.2.2'}
            if other:
                data['id'] = 16059
                data['nvr'] = 'TurboGears-1.0.2.2-3.fc7'
                data['release'] = '3.fc7'
            return data

        elif 'el5' in build:
            return {'build_id': 16058,
                    'completion_time': '2007-08-24 23:26:10.890319',
                    'creation_event_id': 151517,
                    'creation_time': '2007-08-24 19:38:29.422344',
                    'epoch': None,
                    'id': 16058,
                    'name': 'kernel',
                    'nvr': 'kernel-2.6.31-1.el5',
                    'owner_id': 388,
                    'owner_name': 'lmacken',
                    'package_id': 8,
                    'package_name': 'kernel',
                    'release': '1.el5',
                    'state': 1,
                    'tag_id': 19,
                    'tag_name': 'dist-5E-epel-testing-candidate',
                    'task_id': 127621,
                    'version': '2.6.31'}
        else:
            f = build.split('.')[-1].replace('fc', 'f')
            release = build.split('.')[-1]
            return {'build_id': 16058,
                    'completion_time': '2007-08-24 23:26:10.890319',
                    'creation_event_id': 151517,
                    'creation_time': '2007-08-24 19:38:29.422344',
                    'epoch': None,
                    'id': 16058,
                    'name': 'TurboGears',
                    'nvr': 'TurboGears-1.0.2.2-2.%s' % release,
                    'owner_id': 388,
                    'owner_name': 'lmacken',
                    'package_id': 8,
                    'package_name': 'TurboGears',
                    'release': '2.%s' % release,
                    'state': 1,
                    'tag_id': 19,
                    'tag_name': 'dist-%s-updates-testing' % f,
                    'task_id': 127621,
                    'version': '1.0.2.2'}

    def listBuildRPMs(self, id, *args, **kw):
        rpms = [{'arch': 'src',
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
                 'version': '1.0.2.2'},]
        if id == 16059:  # for updateinfo.xml tests
            rpms[0]['nvr'] = rpms[1]['nvr'] = 'TurboGears-1.0.2.2-3.fc7'
            rpms[0]['release'] = rpms[1]['release'] = '3.fc7'
        return rpms

    def listTags(self, build, *args, **kw):
        if 'fc7' in build:
            return [{'arches': 'i386 x86_64 ppc ppc64', 'id': 10, 'locked': True,
                     'name': 'dist-fc7-updates-candidate', 'perm': None, 'perm_id': None},
                     {'arches': 'i386 x86_64 ppc ppc64', 'id': 10, 'locked': True,
                      'name': 'dist-fc7-updates-testing', 'perm': None, 'perm_id': None},
                    {'arches': 'i386 x86_64 ppc ppc64', 'id': 5, 'locked': True,
                     'name': 'dist-fc7', 'perm': None, 'perm_id': None}]
        elif 'el5' in build:
            return [{'arches': 'i386 x86_64 ppc ppc64', 'id': 10, 'locked': True,
                     'name': 'dist-5E-epel-testing-candidate', 'perm': None, 'perm_id': None},
                     {'arches': 'i386 x86_64 ppc ppc64', 'id': 10, 'locked': True,
                      'name': 'dist-5E-epel-testing-candidate', 'perm': None, 'perm_id': None},
                    {'arches': 'i386 x86_64 ppc ppc64', 'id': 5, 'locked': True,
                     'name': 'dist-5E-epel', 'perm': None, 'perm_id': None}]
        else:
            release = build.split('.')[-1].replace('fc', 'f')
            return [{'arches': 'i386 x86_64 ppc ppc64', 'id': 10, 'locked': True,
                     'name': 'dist-%s-updates-candidate' % release, 'perm': None, 'perm_id': None},
                    {'arches': 'i386 x86_64 ppc ppc64', 'id': 5, 'locked': True,
                     'name': 'dist-%s' % release, 'perm': None, 'perm_id': None},
                    {'arches': 'i386 x86_64 ppc ppc64', 'id': 5, 'locked': True,
                     'name': 'dist-%s-updates-testing' % release, 'perm': None, 'perm_id': None}]

    def listTagged(self, tag, *args, **kw):
        return [self.getBuild(), self.getBuild(other=True)]

    def getLatestBuilds(self, *args, **kw):
        return [self.getBuild(),]


def koji_login(client=None, clientca=None, serverca=None):
    """
    Login to Koji and return the session
    """
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

    koji_session = koji.ClientSession(config.get('koji_hub'), {})
    koji_session.ssl_login(client, clientca, serverca)
    return koji_session

def get_session():
    """ Get a new buildsystem instance """
    session = None
    buildsys = config.get('buildsystem')
    if buildsys == 'koji':
        session = koji_login()
    elif buildsys == 'dev':
        session = DevBuildsys()
    return session

def _get_session():
    """
    Get our buildsystem instance.

    :deprecated: This returns a "singleton" instance, but seems to
    cause some issues in production.
    """
    global session
    if not session:
        buildsys = config.get('buildsystem')
        log.info("Creating new %s buildsystem instance" % buildsys)
        if buildsys == 'koji':
            session = koji_login()
        elif buildsys == 'dev':
            session = DevBuildsys()
    return session


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
