import mock

from datetime import datetime, timedelta
from bodhi.server.models import (
    Base,
    Bug,
    Build,
    BuildrootOverride,
    Comment,
    CVE,
    Group,
    Package,
    Release,
    Update,
    UpdateType,
    User,
    UpdateStatus,
    UpdateRequest,
    TestCase,
)


def populate(db):
    user = User(name=u'guest')
    db.add(user)
    anonymous = User(name=u'anonymous')
    db.add(anonymous)
    provenpackager = Group(name=u'provenpackager')
    db.add(provenpackager)
    packager = Group(name=u'packager')
    db.add(packager)
    db.flush()
    user.groups.append(packager)
    release = Release(
        name=u'F17', long_name=u'Fedora 17',
        id_prefix=u'FEDORA', version=u'17',
        dist_tag=u'f17', stable_tag=u'f17-updates',
        testing_tag=u'f17-updates-testing',
        candidate_tag=u'f17-updates-candidate',
        pending_signing_tag=u'f17-updates-testing-signing',
        pending_testing_tag=u'f17-updates-testing-pending',
        pending_stable_tag=u'f17-updates-pending',
        override_tag=u'f17-override',
        branch=u'f17')
    db.add(release)
    pkg = Package(name=u'bodhi')
    db.add(pkg)
    user.packages.append(pkg)
    build = Build(nvr=u'bodhi-2.0-1.fc17', release=release, package=pkg)
    db.add(build)
    testcase = TestCase(name=u'Wat')
    db.add(testcase)
    pkg.test_cases.append(testcase)
    update = Update(
        title=u'bodhi-2.0-1.fc17',
        builds=[build], user=user,
        request=UpdateRequest.testing,
        notes=u'Useful details!', release=release,
        date_submitted=datetime(1984, 11, 02),
        requirements=u'rpmlint',
        stable_karma=3, unstable_karma=-3,
    )
    update.type = UpdateType.bugfix
    bug = Bug(bug_id=12345)
    db.add(bug)
    update.bugs.append(bug)
    cve = CVE(cve_id=u"CVE-1985-0110")
    db.add(cve)
    update.cves.append(cve)

    comment = Comment(karma=1, text=u"wow. amaze.")
    db.add(comment)
    comment.user = user
    update.comments.append(comment)
    update.karma = 1

    comment = Comment(karma=0, text=u"srsly.  pretty good.", anonymous=True)
    comment.user = anonymous
    db.add(comment)
    update.comments.append(comment)

    with mock.patch(target='uuid.uuid4', return_value='wat'):
        update.assign_alias()
    db.add(update)

    expiration_date = datetime.utcnow()
    expiration_date = expiration_date + timedelta(days=1)

    override = BuildrootOverride(build=build, submitter=user,
                                 notes=u'blah blah blah',
                                 expiration_date=expiration_date)
    db.add(override)

    update.locked = True

    db.flush()
