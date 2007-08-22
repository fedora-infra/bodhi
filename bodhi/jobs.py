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

"""
    This module is for functions that are to be executed on a regular basis
    using the TurboGears scheduler.
"""

import logging

from turbogears import scheduler

log = logging.getLogger(__name__)

def clean_repo():
    log.debug("hello world")

def schedule():
    """ Schedule our periodic tasks """

    scheduler.add_interval_task(action=clean_repo,
                                taskname='Repository Cleanup',
                                initialdelay=0,
                                interval=10)
