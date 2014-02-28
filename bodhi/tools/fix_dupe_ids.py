#!/usr/bin/python -tt
"""
This is a nasty hack to fix updates with duplicate ids.
"""

import os
import time
import cPickle

from datetime import datetime
from pprint import pprint
from turbogears.database import PackageHub
from bodhi.util import load_config
from bodhi.model import PackageUpdate, Release
from sqlobject import AND

hub = PackageHub("bodhi")
__connection__ = hub

def main():
    load_config()
    hub.begin()

    print "Finding updates with duplicate IDs..."
    if os.path.exists('dupes.pickle'):
        out = file('dupes.pickle')
        dupes = cPickle.load(out)
        out.close()
        highest_fedora = int(file('highest_fedora').read())
        highest_epel = int(file('highest_epel').read())
    else:
        dupes = set()
        highest_fedora = 0
        highest_epel = 0

        for update in PackageUpdate.select(PackageUpdate.q.updateid!=None):
            if '-2010-' in update.updateid:
                if update.release.id_prefix == 'FEDORA':
                    if update.updateid_int > highest_fedora:
                        highest_fedora = update.updateid_int
                else:
                    if update.updateid_int > highest_epel:
                        highest_epel = update.updateid_int

            updates = PackageUpdate.select(
                    AND(PackageUpdate.q.updateid == update.updateid,
                        PackageUpdate.q.title != update.title))
            if updates.count():
                # Maybe TODO?: ensure these dupes have a date_pushed less tahn update?!
                # this way, the new ID is based on the oldest update
                for u in updates:
                    dupes.add(u.title)

        out = file('dupes.pickle', 'w')
        cPickle.dump(dupes, out)
        out.close()
        print "Wrote dupes.pickle"

        file('highest_fedora', 'w').write(str(highest_fedora))
        file('highest_epel', 'w').write(str(highest_epel))

    # verify what we really found the highest IDs
    assert PackageUpdate.select(PackageUpdate.q.updateid=='FEDORA-2010-%d' % (highest_fedora + 1)).count() == 0
    assert PackageUpdate.select(PackageUpdate.q.updateid=='FEDORA-EPEL-2010-%d' % (highest_epel + 1)).count() == 0

    # Should be 740?
    print "%d dupes" % len(dupes)

    print "Highest FEDORA ID:", highest_fedora
    print "Highest FEDORA-EPEL ID:", highest_epel

    # Reassign the update IDs on all of our dupes
    for dupe in dupes:
        up = PackageUpdate.byTitle(dupe)
        #print "%s *was* %s" % (up.title, up.updateid)
        up.updateid = None

        # TODO: save & restore this value after new id assignment?!
        #up.date_pushed = None

    # Tweak the date_pushed to on the updates with the highest IDs
    PackageUpdate.select(PackageUpdate.q.updateid=='FEDORA-2010-%d' % highest_fedora).date_pushed = datetime.now()
    PackageUpdate.select(PackageUpdate.q.updateid=='FEDORA-EPEL-2010-%d' % highest_epel).date_pushed = datetime.now()

    #hub.commit()

    for dupe in dupes:
        up = PackageUpdate.byTitle(dupe)
        up.assign_id()
        ups = PackageUpdate.select(PackageUpdate.q.updateid == up.updateid)
        if ups.count() == 1:
            print "Still a dupe!!"
            for update in ups:
                if update.title == up.title:
                    continue
                else:
                    if update.title in dupes:
                        print "%s in dupes, yet shares an updateid %s" % (
                                update.title, update.updateid)
                    else:
                        print "%s is not in dupes, but dupes %s" % (
                                update.title, updateid)

    print "Checking to ensure we have no more dupes..."
    dupes = set()
    for update in PackageUpdate.select(PackageUpdate.q.updateid != None):
        updates = PackageUpdate.select(
                AND(PackageUpdate.q.updateid == update.updateid,
                    PackageUpdate.q.title != update.title))
        if updates.count():
            dupes.add(update.title)
    print "%d dupes (should be 0)" % len(dupes)

if __name__ == '__main__':
    main()
