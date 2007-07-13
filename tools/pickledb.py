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
    updates = []

    for update in PackageUpdate.select():
        print update.nvr
        data = {}
        data['nvr'] = update.nvr
        data['date_submitted'] = update.date_submitted
        data['date_pushed'] = update.date_pushed
        data['package'] = update.package.name
        data['release'] = update.release.name
        data['submitter'] = update.submitter
        data['update_id'] = update.update_id
        data['type'] = update.type
        data['cves'] = [cve.cve_id for cve in update.cves]
        data['bugs'] = [bug.bz_id for bug in update .bugs]
        data['status'] = update.status
        data['pushed'] = update.pushed
        data['notes'] = update.notes
        data['mail_sent'] = update.mail_sent
        data['request'] = update.request
        data['comments'] = [(c.timestamp, c.author, c.text) for c in update.comments]
        updates.append(data)

    dump = file('bodhi-pickledb-%s' % time.strftime("%y%m%d.%H%M"), 'w')
    pickle.dump(updates, dump)
    dump.close()

if __name__ == '__main__':
    main()
