# Bugzilla damage control.
# Takes the `neglected.pickle` output of find_neglected_bugs.py and closes them

import os
import pickle

if not os.path.exists('neglected.pickle'):
    raise Exception("You must first run find_neglected_bugs.py")

dump = file('neglected.pickle')
bugs = pickle.load(dump)
dump.close()

bz = Bugzilla.get_bz()
done = set()

try:
    for bug in bugs['ON_QA']:
        b = Bugzilla.byBz_id(bug)
        u = b.updates[0]
        print("Closing bug #%d" % bug)
        bz.getbug(bug).close('ERRATA', fixedin=u.builds[0].nvr, comment=b._default_message(u))
        done.add(bug)
except:
    import traceback
    traceback.print_exc()
    out = file('bugs.done', 'w')
    pickle.dump(done, out)
    out.close()

print("DONE! Closed %d ON_QA bugs" % len(done))
