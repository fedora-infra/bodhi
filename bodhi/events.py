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

from pyramid.events import NewRequest
from pyramid.events import subscriber

from bodhi import log
import bodhi.notifications

## Optionally use this to debug the number of transaction/data managers in the
## _managers_map.  Things look fine here, but we could enable this later if we
## want to inspect stuff.
#@subscriber(NewRequest)
#def fedmsg_manager_debugger(event):
#    log.debug("fedmsg_manager_debugger %r" % bodhi.notifications._managers_map)
