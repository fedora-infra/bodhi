from bodhi.models import (
    Base, DBSession, Release, Update, User, Package, Build, Bug, UpdateType,
)

def populate():
    session = DBSession()
    user = User(name=u'guest')
    session.add(user)
    release = Release(
        name=u'F17', long_name=u'Fedora 17',
        id_prefix=u'FEDORA', dist_tag=u'f17')
    session.add(release)
    pkg = Package(name=u'bodhi')
    session.add(pkg)
    build = Build(nvr=u'bodhi-2.0-1', release=release, package=pkg)
    session.add(build)
    update = Update(
        builds=[build], user=user,
        notes=u'Useful details!', release=release)
    update.type = UpdateType.bugfix
    bug = Bug(bug_id=12345)
    session.add(bug)
    update.bugs.append(bug)
    session.add(update)
    session.flush()
