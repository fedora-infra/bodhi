#!/usr/bin/python -tt
# $Id: $
#
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
This script pickles all updates/bugs/cves/comments and writes it out to disk
in the format of bodhi-pickledb-YYYYMMDD.HHMM
"""

import time
import cPickle as pickle

from init import load_config
from bodhi.model import PackageUpdate
from turbogears.database import PackageHub

hub = __connection__ = PackageHub("bodhi")

def main():
    load_config()
    updates = {}

    for update in PackageUpdate.select():
        print update.nvr
        updates['nvr'] = update.nvr
        updates['date_submitted'] = update.date_submitted
        updates['date_pushed'] = update.date_pushed
        updates['package'] = update.package.name
        updates['release'] = update.release.name
        updates['submitter'] = update.submitter
        updates['update_id'] = update.update_id
        updates['type'] = update.type
        updates['cves'] = [cve.cve_id for cve in update.cves]
        updates['bugs'] = [bug.bz_id for bug in update .bugs]
        updates['status'] = update.status
        updates['pushed'] = update.pushed
        updates['notes'] = update.notes
        updates['mail_sent'] = update.mail_sent
        updates['request'] = update.request
        updates['comments'] = [(c.timestamp, c.author, c.text) for c in update.comments]

    dump = file('bodhi-pickledb-%s' % time.strftime("%y%m%d.%H%M"), 'w')
    pickle.dump(updates, dump)
    dump.close()

if __name__ == '__main__':
    main()
