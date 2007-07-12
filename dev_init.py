#!/usr/bin/env python
from init import load_config
from turbogears.database import PackageHub
from bodhi.exceptions import DuplicateEntryError
from bodhi.model import (User, Group, PackageUpdate, Package, Release,
                         PackageBuild)

hub = PackageHub("bodhi")
__connection__ = hub

load_config()

hub.begin()
print "Creating guest user and giving it administrator priviliges"
try:
    guest = User(user_name='guest', display_name='Bodhi Guest')
    guest.password = 'guest'
    admin = Group(group_name='releng', display_name='Bodhi administrators')
    guest.addGroup(admin)
    hub.commit()
except DuplicateEntryError:
    print "guest account already created"

package = Package(name='yum')
build = PackageBuild(nvr='yum-3.2.1-1.fc7', package=package)
update = PackageUpdate(title='yum-3.2.1-1.fc7', release=Release.select()[0],
                       submitter='bodhi', status='pending',
                       notes='This is a test update created by bodhi',
                       type='enhancement')
update.addPackageBuild(build)

print "Done!"
