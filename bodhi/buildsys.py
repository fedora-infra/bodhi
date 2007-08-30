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
    def listTags(self): raise NotImeplementedError
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
                'name': 'kernel',
                'nvr': 'kernel-2.6.22.5-71.fc7',
                'owner_id': 388,
                'owner_name': 'linville',
                'package_id': 8,
                'package_name': 'kernel',
                'release': '71.fc7',
                'state': 1,
                'tag_id': 19,
                'tag_name': 'dist-fc7-updates-testing',
                'task_id': 127621,
                'version': '2.6.22.5'}

    def listBuildRPMs(self, *args, **kw):
        return [{ 'arch': 'i386',
                  'build_id': 16510,
                  'buildroot_id': 43070,
                  'buildtime': 1188242015,
                  'epoch': None,
                  'id': 182477,
                  'name': 'pyxattr',
                  'nvr': 'pyxattr-0.2.2-1.fc7',
                  'payloadhash': '4939b8f20d862674572ac59a17498a39',
                  'release': '1.fc7',
                  'size': 11633,
                  'version': '0.2.2'},]

    def listTags(self, *args, **kw):
        return ('dist-fc7-updates',
                'dist-fc7-updates-testing',
                'dist-fc7-updates-candidate')

    def listTagged(self, *args, **kw):
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
