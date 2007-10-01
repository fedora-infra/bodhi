# $Id: $
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

import koji
import logging

from time import sleep
from os.path import join, expanduser
from turbogears import config

log = logging.getLogger(__name__)

## Our buildsystem session.  This could be a koji ClientSession or an instance
## of our Buildsystem class.
session = None

class Buildsystem:
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


class DevBuildsys(Buildsystem):
    """
    A dummy buildsystem instance used during development
    """
    def moveBuild(self, *args, **kw):
        log.debug("moveBuild(%s, %s)" % (args, kw))

    def ssl_login(self, *args, **kw):
        log.debug("moveBuild(%s, %s)" % (args, kw))

    def taskFinished(self, task):
        return True

    def getTaskInfo(self, task):
        return { 'state' : koji.TASK_STATES['CLOSED'] }

    def getBuild(self, *args, **kw):
        return {'build_id': 16058,
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
                 'version': '1.0.2.2'},]

    def listTags(self, *args, **kw):
        return [{'arches': 'i386 x86_64 ppc ppc64', 'id': 10, 'locked': True,
                 'name': 'dist-fc7-updates-candidate', 'perm': None, 'perm_id': None},
                {'arches': 'i386 x86_64 ppc ppc64', 'id': 5, 'locked': True,
                 'name': 'dist-fc7', 'perm': None, 'perm_id': None}]

    def listTagged(self, tag, *args, **kw):
        if tag not in ('dist-fc7', 'dist-fc7-updates-candidate',
                       'dist-fc7-updates-testing', 'dist-fc7-updates'):
            raise koji.GenericError
        return [self.getBuild(),]

    def getLatestBuilds(self, *args, **kw):
        return [self.getBuild(),]

def koji_login(client=join(expanduser('~'), '.fedora.cert'),
               clientca=join(expanduser('~'), '.fedora-upload-ca.cert'),
               serverca=join(expanduser('~'), '.fedora-server-ca.cert')):
    """
    Login to Koji and return the session
    """
    koji_session = koji.ClientSession(config.get('koji_hub'), {})
    koji_session.ssl_login(client, clientca, serverca)
    return koji_session

def get_session():
    """
    Get our buildsystem instance.
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

def wait_for_tasks(tasks):
    """
    Wait for a list of koji tasks to complete.  Return the first task number
    to fail, otherwise zero.
    """
    log.debug("Waiting for tasks to complete: %s" % tasks)
    for task in tasks:
        while not session.taskFinished(task):
            sleep(2)
        task_info = session.getTaskInfo(task)
        if task_info['state'] != koji.TASK_STATES['CLOSED']:
            log.error("Koji task %d failed" % task)
            return task
    return 0
