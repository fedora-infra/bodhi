# A script to fix updates that were pushed to testing but were missing the bodhi comment.
# Fixed in https://github.com/fedora-infra/bodhi/commit/399f3afc24df7c8907cb3400a7c6769998a9aaba
# Fixes https://github.com/fedora-infra/bodhi/issues/414
#       https://github.com/fedora-infra/bodhi/issues/413
#
# pshell /etc/bodhi/production.ini
# execfile('fix-testing-updates.py')

from datetime import datetime
import pprint

from shelldb import db, m, request


bad = []

for up in db.query(m.Update).filter_by(status=m.UpdateStatus.testing).all():
    good = False
    for c in up.comments:
        if c.text.startswith('This update has been pushed to testing'):
            good = True
            break
    if not good:
        bad.append(up)

print('%d busted testing updates found' % len(bad))

bodhi = m.User.get(u'bodhi', db)

# for each one, get the koji tag history
k = request.koji
for up in bad:
    assert up.days_in_testing == 0, up.days_in_testing
    build = up.builds[0]
    try:
        hist = k.tagHistory(build=build.nvr)
        ts = None
        for h in hist:
            if h['tag_name'] == up.release.testing_tag:
                ts = datetime.fromtimestamp(h['create_ts'])
                print('%s was pushed to testing on %s' % (up.title, ts))

        if not ts:
            print('Cannot determine when %s was pushed to testing' % up.title)
            print(pprint.pformat(hist))
        else:
            c = m.Comment(text=u'This update has been pushed to testing',
                          user=bodhi, timestamp=ts)
            db.add(c)
            db.flush()
            up.comments.append(c)
            db.flush()

            assert up.days_in_testing != 0, up
    except Exception:
        print('Cannot find koji build for %s' % build.nvr)

# vim: ts=4 sw=4 ai expandtab
