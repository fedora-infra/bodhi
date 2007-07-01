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

# Our singleton koji ClientSession
session = None

def get_session():
    """
    Get a singleton Koji ClientSession instance
    """
    global session
    if not session:
        session = login()
    return session

def login(client=join(expanduser('~'), '.fedora.cert'),
          clientca=join(expanduser('~'), '.fedora-upload-ca.cert'),
          serverca=join(expanduser('~'), '.fedora-server-ca.cert')):
    """
    Login to Koji and return the session
    """
    koji_session = koji.ClientSession(config.get('koji_hub'), {})
    koji_session.ssl_login(client, clientca, serverca)
    return koji_session

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
